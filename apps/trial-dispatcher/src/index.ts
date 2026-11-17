// PrePost trial dispatcher: a Cron-triggered Worker (Pages has no cron) bound to the
// same D1 database and R2 bucket as the site's trial functions.
//
// Every minute:
//   1. reap abandoned uploads, fail anything unscored after 72 h, drop expired results
//   2. poll in-flight RunPod jobs (fallback for the webhook) and expire lost leases
//   3. if clips are queued and no batch is in flight: workersMax = 1 and submit ALL
//      queued clips at once, so one warm worker (idleTimeout ~120 s) scores them
//      back to back with the weights already loaded
//   4. if nothing is queued or in flight: workersMax = 0
import { randomToken, signedBlobUrl, webhookUrl } from '../../web/lib/trial/crypto'
import type { DispatcherEnv } from '../../web/lib/trial/env'
import {
  activityKey,
  failJob,
  finalizeJob,
  LIMITS,
  settleTerminal,
  TERMINAL_RUNPOD,
  unsettledJobs,
  uploadKey,
  type JobRow,
} from '../../web/lib/trial/jobs'
import { cancelJob, jobStatus, setWorkersMax, submitJob } from '../../web/lib/trial/runpod'

const MIN = 60_000
const errMsg = (err: unknown) => (err instanceof Error ? err.message : String(err))

/** Run `fn` for one job; a failure is logged and the tick carries on with the rest. */
async function each(log: string[], what: string, jobs: JobRow[], fn: (j: JobRow) => Promise<void>): Promise<void> {
  for (const j of jobs) {
    try {
      await fn(j)
    } catch (err) {
      log.push(`${what} ${j.id} failed: ${errMsg(err)}`)
    }
  }
}
const URL_TTL_S = 4 * 3600
/** Re-assert workersMax = 0 at least this often, in case something else changed it. */
const REASSERT_OFF_MS = 10 * MIN

interface Ctx {
  waitUntil(p: Promise<unknown>): void
}

async function getState(env: DispatcherEnv, key: string): Promise<{ value: string; updated_at: number } | null> {
  return env.TRIAL_DB.prepare('SELECT value, updated_at FROM trial_state WHERE key = ?').bind(key).first()
}

async function setState(env: DispatcherEnv, key: string, value: string): Promise<void> {
  await env.TRIAL_DB.prepare(
    `INSERT INTO trial_state (key, value, updated_at) VALUES (?, ?, ?)
     ON CONFLICT (key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at`,
  )
    .bind(key, value, Date.now())
    .run()
}

/** Tick lock: one dispatcher pass at a time, self-expiring after 5 minutes. */
async function acquireLock(env: DispatcherEnv, owner: string): Promise<boolean> {
  const now = Date.now()
  const r = await env.TRIAL_DB.prepare(
    `INSERT INTO trial_state (key, value, updated_at) VALUES ('lock', ?1, ?2)
     ON CONFLICT (key) DO UPDATE SET value = ?1, updated_at = ?2 WHERE trial_state.updated_at < ?3`,
  )
    .bind(owner, now, now - 5 * MIN)
    .run()
  return r.meta.changes === 1
}

async function releaseLock(env: DispatcherEnv, owner: string): Promise<void> {
  await env.TRIAL_DB.prepare(`UPDATE trial_state SET updated_at = 0 WHERE key = 'lock' AND value = ?`).bind(owner).run()
}

async function scale(env: DispatcherEnv, want: 0 | 1, log: string[]): Promise<void> {
  const cur = await getState(env, 'workers_max')
  const stale = !cur || Date.now() - cur.updated_at > REASSERT_OFF_MS
  // Turning on always calls RunPod (once per batch); turning off is re-asserted every 10 min.
  if (want === 0 && cur?.value === '0' && !stale) return
  await setWorkersMax(env, want)
  await setState(env, 'workers_max', String(want))
  log.push(`workersMax=${want}`)
}

async function housekeeping(env: DispatcherEnv, log: string[]): Promise<void> {
  const db = env.TRIAL_DB
  const now = Date.now()

  // Uploads that never finished storing (the uploader saw an error): no use consumed.
  const stuck = await db
    .prepare(`SELECT * FROM jobs WHERE status = 'uploading' AND created_at < ?`)
    .bind(now - 15 * MIN)
    .all<JobRow>()
  await each(log, 'reap', stuck.results, async (j) => {
    await env.TRIAL_BUCKET.delete(uploadKey(j))
    await db.prepare(`DELETE FROM jobs WHERE id = ? AND status = 'uploading'`).bind(j.id).run()
    log.push(`reaped upload ${j.id}`)
  })

  // Promise on the upload page: the video is deleted after 72 h at most.
  const old = await db
    .prepare(`SELECT * FROM jobs WHERE status IN ('queued', 'submitted', 'running') AND created_at < ?`)
    .bind(now - LIMITS.uploadMaxHours * 60 * MIN)
    .all<JobRow>()
  await each(log, 'expire', old.results, async (j) => {
    if (j.runpod_job_id) await cancelJob(env, j.runpod_job_id)
    await failJob(env, j, 'expired: not scored within 72 hours')
    log.push(`expired ${j.id}`)
  })

  // Terminal rows whose R2 cleanup or email didn't finish (R2 or Resend failed earlier).
  await each(log, 'settle', await unsettledJobs(env), async (j) => {
    await settleTerminal(env, j)
    log.push(`settled ${j.id}`)
  })

  // Results are kept 30 days.
  const expired = await db
    .prepare(`SELECT * FROM jobs WHERE status = 'complete' AND expires_at < ?`)
    .bind(now)
    .all<JobRow>()
  await each(log, 'result-expiry', expired.results, async (j) => {
    await env.TRIAL_BUCKET.delete([activityKey(j.id), uploadKey(j)])
    await db.prepare('DELETE FROM jobs WHERE id = ?').bind(j.id).run()
    log.push(`result expired ${j.id}`)
  })
  // Failed/deleted rows only matter for invite use counts (invites last 30 days).
  // Only settled ones go, so nothing they point at is left behind in R2.
  await db
    .prepare(`DELETE FROM jobs WHERE status IN ('failed', 'deleted') AND cleaned = 1 AND created_at < ?`)
    .bind(now - 31 * 24 * 60 * MIN)
    .run()
}

async function pollInFlight(env: DispatcherEnv, log: string[]): Promise<void> {
  const db = env.TRIAL_DB
  const inflight = await db
    .prepare(`SELECT * FROM jobs WHERE status IN ('submitted', 'running') AND runpod_job_id IS NOT NULL`)
    .all<JobRow>()
  await each(log, 'poll', inflight.results, async (j) => {
    const rpId = j.runpod_job_id as string
    const rp = await jobStatus(env, rpId)
    if (rp === null) {
      // RunPod forgot the job (TTL): count it as a failed attempt.
      log.push(`${j.id} ${await finalizeJob(env, j, { id: rpId, status: 'FAILED', error: 'job vanished from RunPod' })}`)
      return
    }
    if (TERMINAL_RUNPOD.has(rp.status)) {
      log.push(`${j.id} ${rp.status} -> ${await finalizeJob(env, j, rp)}`)
      return
    }
    if (j.lease_until && Date.now() > j.lease_until) {
      await cancelJob(env, rpId)
      const outcome = await finalizeJob(env, j, { id: rpId, status: 'TIMED_OUT', error: 'lease expired' })
      log.push(`${j.id} lease expired -> ${outcome}`)
      return
    }
    if (rp.status === 'IN_PROGRESS' && j.status === 'submitted') {
      await db
        .prepare(`UPDATE jobs SET status = 'running', started_at = ? WHERE id = ? AND status = 'submitted' AND runpod_job_id = ?`)
        .bind(Date.now(), j.id, rpId)
        .run()
      log.push(`${j.id} running`)
    }
  })
}

async function dispatch(env: DispatcherEnv, log: string[]): Promise<void> {
  const db = env.TRIAL_DB
  const counts = await db
    .prepare(
      `SELECT SUM(status = 'queued') AS queued, SUM(status IN ('submitted', 'running')) AS inflight
       FROM jobs WHERE status IN ('queued', 'submitted', 'running')`,
    )
    .first<{ queued: number | null; inflight: number | null }>()
  const queued = counts?.queued ?? 0
  const inflight = counts?.inflight ?? 0

  if (queued === 0 && inflight === 0) return scale(env, 0, log)
  if (queued === 0 || inflight > 0) return // the current batch finishes first
  if (!env.TRIAL_SIGNING_KEY) throw new Error('TRIAL_SIGNING_KEY is not set')

  await scale(env, 1, log)
  const batch = await db
    .prepare(`SELECT * FROM jobs WHERE status = 'queued' ORDER BY created_at LIMIT ?`)
    .bind(LIMITS.queueCap)
    .all<JobRow>()
  const now = Date.now()
  let i = 0
  for (const j of batch.results) {
    const attempt = j.attempts + 1
    try {
      const rpId = await submitJob(
        env,
        {
          video_url: await signedBlobUrl(j.site, env.TRIAL_SIGNING_KEY, 'GET', uploadKey(j), URL_TTL_S),
          activity_put_url: await signedBlobUrl(j.site, env.TRIAL_SIGNING_KEY, 'PUT', activityKey(j.id), URL_TTL_S, attempt),
          filename: `${j.id}.${j.ext}`,
          max_seconds: LIMITS.handlerMaxSeconds,
        },
        await webhookUrl(j.site, env.TRIAL_SIGNING_KEY, j.id, attempt),
      )
      // Later clips in the batch wait for the ones ahead of them on the single worker.
      const lease = now + (LIMITS.leaseMinutes + i * 15) * MIN
      await db
        .prepare(
          `UPDATE jobs SET status = 'submitted', runpod_job_id = ?, attempts = ?, submitted_at = ?, lease_until = ?
           WHERE id = ? AND status = 'queued'`,
        )
        .bind(rpId, attempt, now, lease, j.id)
        .run()
      log.push(`submitted ${j.id} (attempt ${attempt}) as ${rpId}`)
      i++
    } catch (err) {
      log.push(`submit failed ${j.id}: ${err instanceof Error ? err.message : String(err)}`)
    }
  }
}

export async function tick(env: DispatcherEnv): Promise<string[]> {
  const owner = randomToken(8)
  const log: string[] = []
  if (!(await acquireLock(env, owner))) return ['locked']
  try {
    // Each phase runs even if an earlier one threw, so scale(0) in dispatch() is
    // never skipped by an unrelated failure.
    const phases = [
      ['housekeeping', housekeeping],
      ['poll', pollInFlight],
      ['dispatch', dispatch],
    ] as const
    for (const [name, phase] of phases) {
      try {
        await phase(env, log)
      } catch (err) {
        log.push(`${name} error: ${errMsg(err)}`)
      }
    }
  } finally {
    await releaseLock(env, owner)
  }
  if (log.length) console.log(`[dispatcher] ${log.join(' | ')}`)
  return log
}

export default {
  async scheduled(_event: unknown, env: DispatcherEnv, ctx: Ctx): Promise<void> {
    ctx.waitUntil(tick(env))
  },
  async fetch(): Promise<Response> {
    return new Response('Not found', { status: 404 })
  },
}
