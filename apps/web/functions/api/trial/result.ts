// GET    /api/trial/result  (Authorization: Bearer <token>) → status, queue position, ETA, result
// DELETE /api/trial/result  (same auth) → deletes the result and anything left of the upload
// An unknown token, a deleted result or an expired one is a plain 404.
import type { PagesEnv } from '../../../lib/trial/env'
import { bearer, jobByToken, json, notFound } from '../../../lib/trial/http'
import { activityKey, ACTIVE, queueInfo, uploadKey } from '../../../lib/trial/jobs'
import { CLAIM } from '../../../lib/trial/claim'

const STATUS_LABEL: Record<string, string> = {
  uploading: 'Uploading',
  queued: 'Waiting for the GPU',
  submitted: 'Sent to the GPU',
  running: 'Scoring',
  complete: 'Done',
  failed: 'Could not score',
}

export const onRequestGet = async ({ request, env }: { request: Request; env: PagesEnv }) => {
  const token = bearer(request)
  if (!token) return notFound()
  const job = await jobByToken(env, token)
  if (!job || job.status === 'deleted' || (job.expires_at && job.expires_at < Date.now())) return notFound()

  const base = {
    status: job.status,
    label: STATUS_LABEL[job.status] ?? job.status,
    created_at: job.created_at,
    duration_s: job.duration_s,
    claim: CLAIM,
  }
  if ((ACTIVE as readonly string[]).includes(job.status)) {
    return json({ ...base, queue: await queueInfo(env, job), attempts: job.attempts })
  }
  if (job.status === 'failed') {
    return json({ ...base, error: 'The clip could not be scored. The video has been deleted.' })
  }
  return json({
    ...base,
    completed_at: job.completed_at,
    expires_at: job.expires_at,
    timings: { delay_ms: job.delay_ms, execution_ms: job.execution_ms, cold_start: job.cold_start === 1 },
    result: job.result_json ? JSON.parse(job.result_json) : null,
  })
}

export const onRequestDelete = async ({ request, env }: { request: Request; env: PagesEnv }) => {
  const token = bearer(request)
  if (!token) return notFound()
  const job = await jobByToken(env, token)
  if (!job || job.status === 'deleted') return notFound()
  // The row stays (scrubbed) so the upload still counts against the invite; an
  // in-flight RunPod job finishing later is ignored by finalizeJob, which also
  // removes anything it wrote.
  await env.TRIAL_DB.prepare(
    `UPDATE jobs SET status = 'deleted', result_json = NULL, token = NULL, has_activity = 0, lease_until = NULL
     WHERE id = ?`,
  )
    .bind(job.id)
    .run()
  await env.TRIAL_BUCKET.delete([uploadKey(job), activityKey(job.id)])
  return json({ ok: true, deleted: true })
}
