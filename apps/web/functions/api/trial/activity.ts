// GET /api/trial/activity (Authorization: Bearer <token>) → uint8 [frames × 20484]
// cortex activity for the result page's CortexBrain view (research/export_cortex.py encoding).
import type { PagesEnv } from '../../../lib/trial/env'
import { bearer, jobByToken, notFound } from '../../../lib/trial/http'
import { activityKey } from '../../../lib/trial/jobs'

export const onRequestGet = async ({ request, env }: { request: Request; env: PagesEnv }) => {
  const token = bearer(request)
  if (!token) return notFound()
  const job = await jobByToken(env, token)
  if (!job || job.status !== 'complete' || !job.has_activity || (job.expires_at ?? 0) < Date.now()) return notFound()
  const obj = await env.TRIAL_BUCKET.get(activityKey(job.id))
  if (!obj) return notFound()
  return new Response(obj.body, {
    headers: { 'content-type': 'application/octet-stream', 'cache-control': 'private, no-store' },
  })
}
