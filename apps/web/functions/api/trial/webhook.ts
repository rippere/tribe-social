// POST /api/trial/webhook?job=<id>&a=<attempt>&sig=<hmac> — RunPod's completion callback.
// The signature binds the job id and attempt, so only the dispatcher's own URLs work.
// RunPod retries a non-200 twice, 10 s apart; the dispatcher's /status poll is the
// fallback, and finalizeJob is idempotent, so double delivery is harmless.
import { hmacVerify, webhookMessage } from '../../../lib/trial/crypto'
import type { PagesEnv, WaitUntil } from '../../../lib/trial/env'
import { json } from '../../../lib/trial/http'
import { finalizeJob, type JobRow, type RunpodJob } from '../../../lib/trial/jobs'

export const onRequestPost = async ({ request, env }: { request: Request; env: PagesEnv; waitUntil: WaitUntil }) => {
  const url = new URL(request.url)
  const id = url.searchParams.get('job') ?? ''
  const attempt = Number(url.searchParams.get('a') ?? 'NaN')
  const sig = url.searchParams.get('sig') ?? ''
  if (!env.TRIAL_SIGNING_KEY || !id || !Number.isInteger(attempt)) return json({ error: 'bad request' }, 400)
  if (!(await hmacVerify(env.TRIAL_SIGNING_KEY, webhookMessage(id, attempt), sig))) return json({ error: 'forbidden' }, 403)

  let rp: RunpodJob
  try {
    rp = (await request.json()) as RunpodJob
  } catch {
    return json({ error: 'bad body' }, 400)
  }
  const job = await env.TRIAL_DB.prepare('SELECT * FROM jobs WHERE id = ?').bind(id).first<JobRow>()
  if (!job) return json({ ok: true, outcome: 'unknown-job' })
  const outcome = await finalizeJob(env, job, rp)
  return json({ ok: true, outcome })
}
