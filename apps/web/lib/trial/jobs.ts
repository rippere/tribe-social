// Trial job store (D1) and the one completion path, shared by the RunPod webhook
// (functions/api/trial/webhook.ts) and the dispatcher's /status poll fallback.

import type { TrialEnv } from './env'
import { sendResultFailed, sendResultReady } from './email'
import { buildTrialResult, isHandlerOutput } from './result'

export const LIMITS = {
  maxBytes: 50 * 1024 * 1024,
  maxSeconds: 60,
  /** Handler-side guard: TRIBE emits ~1 frame per second, allow container rounding. */
  handlerMaxSeconds: 75,
  usesPerInvite: 3,
  activePerInvite: 1,
  queueCap: 10,
  /** 1 try + 2 retries. */
  maxAttempts: 3,
  resultDays: 30,
  /** An upload is deleted after this even if it was never scored. */
  uploadMaxHours: 72,
  /** A submitted/running job with no result after this is presumed lost. */
  leaseMinutes: 40,
} as const

export const ACTIVE = ['uploading', 'queued', 'submitted', 'running'] as const
export type JobStatus = (typeof ACTIVE)[number] | 'complete' | 'failed' | 'deleted'

export interface JobRow {
  id: string
  token_hash: string
  token: string | null
  invite_hash: string
  email: string
  site: string
  ext: 'mp4' | 'mov'
  size_bytes: number
  duration_s: number | null
  status: JobStatus
  attempts: number
  runpod_job_id: string | null
  lease_until: number | null
  created_at: number
  submitted_at: number | null
  started_at: number | null
  completed_at: number | null
  delay_ms: number | null
  execution_ms: number | null
  cold_start: number | null
  error: string | null
  result_json: string | null
  has_activity: number
  expires_at: number | null
  notified_at: number | null
}

export const uploadKey = (j: Pick<JobRow, 'id' | 'ext'>) => `uploads/${j.id}.${j.ext}`
export const activityKey = (id: string) => `results/${id}/activity.bin`
export const resultUrl = (site: string, token: string) => `${site}/trial/result#${token}`

/** RunPod's job record, as returned by /status and POSTed to the webhook. */
export interface RunpodJob {
  id: string
  status: 'IN_QUEUE' | 'IN_PROGRESS' | 'COMPLETED' | 'FAILED' | 'CANCELLED' | 'TIMED_OUT' | string
  output?: unknown
  error?: unknown
  delayTime?: number
  executionTime?: number
}

export const TERMINAL_RUNPOD = new Set(['COMPLETED', 'FAILED', 'CANCELLED', 'TIMED_OUT'])

function errorText(rp: RunpodJob): string {
  const o = rp.output as { error?: unknown } | undefined
  const raw = o && typeof o === 'object' && 'error' in o ? o.error : rp.error ?? rp.status
  const s = typeof raw === 'string' ? raw : JSON.stringify(raw)
  return (s || 'unknown error').slice(0, 1000)
}

/** Plain-language reason for the uploader. Internal detail stays in the D1 row. */
function publicReason(err: string): string {
  if (err.includes('limit is')) return 'The clip is longer than 60 seconds.'
  if (err.startsWith('expired')) return 'The clip was not scored within 72 hours, so it was deleted unscored.'
  if (err.startsWith('[fatal]')) return 'The video could not be read. Try exporting it again as an MP4.'
  return 'The scoring server failed on this clip more than once.'
}

async function sendTerminalEmail(env: TrialEnv, job: JobRow, ok: boolean, reason?: string): Promise<void> {
  if (!job.token || job.notified_at) return
  const sent = ok
    ? await sendResultReady(env, job.email, resultUrl(job.site, job.token), job.id)
    : await sendResultFailed(env, job.email, job.id, reason ?? 'unknown')
  // Drop the plaintext token once the link has gone out; only its hash remains.
  if (sent) {
    await env.TRIAL_DB.prepare('UPDATE jobs SET token = NULL, notified_at = ? WHERE id = ?').bind(Date.now(), job.id).run()
  }
}

export type FinalizeOutcome = 'complete' | 'retry' | 'failed' | 'ignored'

/**
 * Record a terminal RunPod result for `job`. Idempotent: only the attempt whose
 * RunPod id is still on the row, and only while the row is in flight, is applied.
 */
export async function finalizeJob(env: TrialEnv, job: JobRow, rp: RunpodJob): Promise<FinalizeOutcome> {
  if (!TERMINAL_RUNPOD.has(rp.status)) return 'ignored'
  if (job.runpod_job_id !== rp.id || (job.status !== 'submitted' && job.status !== 'running')) {
    // Late result for a deleted or superseded attempt: make sure nothing it wrote survives.
    if (job.status === 'deleted') await env.TRIAL_BUCKET.delete(activityKey(job.id))
    return 'ignored'
  }
  const db = env.TRIAL_DB
  const now = Date.now()
  const out = rp.output as Record<string, unknown> | undefined
  const handlerError = out && typeof out === 'object' && 'error' in out

  if (rp.status === 'COMPLETED' && !handlerError && isHandlerOutput(out)) {
    const hasActivity = !!out.activity?.uploaded && !!(await env.TRIAL_BUCKET.head(activityKey(job.id)))
    const result = buildTrialResult(job.id, out, hasActivity)
    const cold = out.timings?.cold_start === true ? 1 : out.timings?.cold_start === false ? 0 : null
    const res = await db
      .prepare(
        `UPDATE jobs SET status = 'complete', result_json = ?, has_activity = ?, completed_at = ?,
           delay_ms = ?, execution_ms = ?, cold_start = ?, lease_until = NULL, error = NULL,
           expires_at = ?, started_at = COALESCE(started_at, ?)
         WHERE id = ? AND runpod_job_id = ? AND status IN ('submitted', 'running')`,
      )
      .bind(
        JSON.stringify(result),
        hasActivity ? 1 : 0,
        now,
        rp.delayTime ?? null,
        rp.executionTime ?? null,
        cold,
        now + LIMITS.resultDays * 86400_000,
        now - (rp.executionTime ?? 0),
        job.id,
        rp.id,
      )
      .run()
    if (res.meta.changes !== 1) return 'ignored'
    await env.TRIAL_BUCKET.delete(uploadKey(job))
    await sendTerminalEmail(env, job, true)
    return 'complete'
  }

  const err = rp.status === 'COMPLETED' && !handlerError ? 'handler returned no usable output' : errorText(rp)
  const fatal = err.startsWith('[fatal]')
  if (!fatal && job.attempts < LIMITS.maxAttempts) {
    const res = await db
      .prepare(
        `UPDATE jobs SET status = 'queued', runpod_job_id = NULL, lease_until = NULL, error = ?
         WHERE id = ? AND runpod_job_id = ? AND status IN ('submitted', 'running')`,
      )
      .bind(err, job.id, rp.id)
      .run()
    return res.meta.changes === 1 ? 'retry' : 'ignored'
  }
  const res = await db
    .prepare(
      `UPDATE jobs SET status = 'failed', lease_until = NULL, error = ?, completed_at = ?,
         delay_ms = ?, execution_ms = ?
       WHERE id = ? AND runpod_job_id = ? AND status IN ('submitted', 'running')`,
    )
    .bind(err, now, rp.delayTime ?? null, rp.executionTime ?? null, job.id, rp.id)
    .run()
  if (res.meta.changes !== 1) return 'ignored'
  await env.TRIAL_BUCKET.delete([uploadKey(job), activityKey(job.id)])
  await sendTerminalEmail(env, job, false, publicReason(err))
  return 'failed'
}

/** Fail a job outside a RunPod result (lost lease with retries spent, 72 h expiry). */
export async function failJob(env: TrialEnv, job: JobRow, err: string): Promise<void> {
  const res = await env.TRIAL_DB.prepare(
    `UPDATE jobs SET status = 'failed', lease_until = NULL, error = ?, completed_at = ?
     WHERE id = ? AND status IN ('uploading', 'queued', 'submitted', 'running')`,
  )
    .bind(err, Date.now(), job.id)
    .run()
  if (res.meta.changes !== 1) return
  await env.TRIAL_BUCKET.delete([uploadKey(job), activityKey(job.id)])
  await sendTerminalEmail(env, job, false, publicReason(err))
}

// ── Queue position and ETA (from observed timings) ───────────────────────────

const DEFAULT_COLD_MS = 5 * 60_000
const DEFAULT_EXEC_MS = 5 * 60_000
const DISPATCH_TICK_MS = 60_000

export interface QueueInfo {
  position: number // 1 = next / being scored
  eta_s: number
  basis: { exec_ms: number; cold_ms: number; samples: number }
}

export async function queueInfo(env: TrialEnv, job: JobRow): Promise<QueueInfo> {
  const db = env.TRIAL_DB
  const [timing, cold, ahead, active] = await Promise.all([
    db
      .prepare(
        `SELECT AVG(execution_ms) AS exec_ms, COUNT(*) AS n FROM
           (SELECT execution_ms FROM jobs WHERE execution_ms IS NOT NULL AND status IN ('complete', 'deleted')
            ORDER BY completed_at DESC LIMIT 20)`,
      )
      .first<{ exec_ms: number | null; n: number }>(),
    db
      .prepare(
        `SELECT AVG(delay_ms) AS cold_ms FROM
           (SELECT delay_ms FROM jobs WHERE cold_start = 1 AND delay_ms IS NOT NULL ORDER BY completed_at DESC LIMIT 10)`,
      )
      .first<{ cold_ms: number | null }>(),
    db
      .prepare(
        `SELECT COUNT(*) AS n FROM jobs WHERE status IN ('queued', 'submitted', 'running') AND created_at < ? AND id != ?`,
      )
      .bind(job.created_at, job.id)
      .first<{ n: number }>(),
    db
      .prepare(`SELECT COUNT(*) AS n, SUM(status = 'running') AS running FROM jobs WHERE status IN ('submitted', 'running')`)
      .first<{ n: number; running: number | null }>(),
  ])
  const exec = timing?.exec_ms ?? DEFAULT_EXEC_MS
  const coldMs = cold?.cold_ms ?? DEFAULT_COLD_MS
  const n = ahead?.n ?? 0
  const now = Date.now()
  let eta: number
  if (job.status === 'running') {
    eta = Math.max(30_000, exec - (now - (job.started_at ?? now)))
  } else if (job.status === 'submitted') {
    const warm = (active?.running ?? 0) > 0
    eta = (warm ? 0 : coldMs) + (n + 1) * exec
  } else {
    // Waits for the current batch (if any) to finish, then the next dispatcher tick.
    const batch = active?.n ?? 0
    eta = DISPATCH_TICK_MS + (batch > 0 ? batch * exec : coldMs) + Math.max(1, n - batch + 1) * exec
  }
  return { position: n + 1, eta_s: Math.round(eta / 1000), basis: { exec_ms: Math.round(exec), cold_ms: Math.round(coldMs), samples: timing?.n ?? 0 } }
}
