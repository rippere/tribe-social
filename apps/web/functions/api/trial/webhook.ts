// POST /api/trial/webhook?job=<id>&a=<attempt>&sig=<hmac> — RunPod's completion callback.
// The signature binds the job id and attempt, so only the dispatcher's own URLs work.
// The body is never trusted: it only tells us to look. The result is read back from
// RunPod's /status for the RunPod job id recorded on the row. RunPod retries a non-200
// twice, 10 s apart; the dispatcher's /status poll is the fallback, and finalizeJob is
// idempotent, so double delivery is harmless.
import { hmacVerify, webhookMessage } from '../../../lib/trial/crypto'
import type { PagesEnv } from '../../../lib/trial/env'
import { json } from '../../../lib/trial/http'
import { finalizeJob, type JobRow } from '../../../lib/trial/jobs'
import { jobStatus } from '../../../lib/trial/runpod'

export const onRequestPost = async ({ request, env }: { request: Request; env: PagesEnv }) => {
  const url = new URL(request.url)
  const id = url.searchParams.get('job') ?? ''
  const attempt = Number(url.searchParams.get('a') ?? 'NaN')
  const sig = url.searchParams.get('sig') ?? ''
  if (!env.TRIAL_SIGNING_KEY || !id || !Number.isInteger(attempt)) return json({ error: 'bad request' }, 400)
  if (!(await hmacVerify(env.TRIAL_SIGNING_KEY, webhookMessage(id, attempt), sig))) return json({ error: 'forbidden' }, 403)

  const job = await env.TRIAL_DB.prepare('SELECT * FROM jobs WHERE id = ?').bind(id).first<JobRow>()
  if (!job || job.attempts !== attempt || !job.runpod_job_id) return json({ ok: true, outcome: 'stale' })
  if (!env.RUNPOD_API_KEY) return json({ ok: true, outcome: 'deferred-to-poll' })
  let rp
  try {
    rp = await jobStatus(env, job.runpod_job_id)
  } catch {
    return json({ ok: true, outcome: 'deferred-to-poll' })
  }
  if (!rp) return json({ ok: true, outcome: 'deferred-to-poll' })
  return json({ ok: true, outcome: await finalizeJob(env, job, rp) })
}
