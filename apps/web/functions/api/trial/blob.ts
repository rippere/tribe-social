// GET/PUT /api/trial/blob?key=…&m=…&exp=…&sig=… — signed, expiring R2 access for the GPU
// worker (R2 bindings can't mint S3 presigned URLs). The signature binds method, key
// and expiry. GET serves uploads/<id>.<ext>; PUT accepts only results/<id>/activity.bin.
import { blobMessage, hmacVerify } from '../../../lib/trial/crypto'
import type { PagesEnv } from '../../../lib/trial/env'

const GET_KEY = /^uploads\/[A-Za-z0-9_-]{22}\.(mp4|mov)$/
const PUT_KEY = /^results\/[A-Za-z0-9_-]{22}\/activity\.bin$/
const MAX_ACTIVITY_BYTES = 8 * 1024 * 1024 // 75 frames × 20484 ≈ 1.5 MB; generous cap

async function authorize(
  request: Request,
  env: PagesEnv,
  method: 'GET' | 'PUT',
): Promise<{ key: string; attempt: number } | Response> {
  const q = new URL(request.url).searchParams
  const key = q.get('key') ?? ''
  const exp = Number(q.get('exp') ?? 'NaN')
  const attempt = Number(q.get('a') ?? '0')
  const sig = q.get('sig') ?? ''
  const deny = new Response('forbidden', { status: 403 })
  if (!env.TRIAL_SIGNING_KEY || q.get('m') !== method || !Number.isInteger(exp) || !Number.isInteger(attempt)) return deny
  if (exp < Date.now() / 1000) return deny
  if (!(method === 'GET' ? GET_KEY : PUT_KEY).test(key)) return deny
  if (!(await hmacVerify(env.TRIAL_SIGNING_KEY, blobMessage(method, key, exp, attempt), sig))) return deny
  return { key, attempt }
}

export const onRequestGet = async ({ request, env }: { request: Request; env: PagesEnv }) => {
  const auth = await authorize(request, env, 'GET')
  if (auth instanceof Response) return auth
  const obj = await env.TRIAL_BUCKET.get(auth.key)
  if (!obj) return new Response('not found', { status: 404 })
  return new Response(obj.body, {
    headers: {
      'content-type': obj.httpMetadata?.contentType ?? 'application/octet-stream',
      'content-length': String(obj.size),
      'cache-control': 'no-store',
    },
  })
}

export const onRequestPut = async ({ request, env }: { request: Request; env: PagesEnv }) => {
  const auth = await authorize(request, env, 'PUT')
  if (auth instanceof Response) return auth
  const { key, attempt } = auth
  // Only the current attempt of a job still in flight may write: a deleted or
  // superseded result must not be recreated.
  const id = key.split('/')[1]
  const live = `SELECT status, attempts FROM jobs WHERE id = ?`
  const job = await env.TRIAL_DB.prepare(live).bind(id).first<{ status: string; attempts: number }>()
  const writable = (j: typeof job) => !!j && (j.status === 'submitted' || j.status === 'running') && j.attempts === attempt
  if (!writable(job)) return new Response('gone', { status: 410 })
  const body = await request.arrayBuffer()
  if (body.byteLength === 0 || body.byteLength > MAX_ACTIVITY_BYTES || body.byteLength % 20484 !== 0) {
    return new Response('bad size', { status: 400 })
  }
  await env.TRIAL_BUCKET.put(key, body, { httpMetadata: { contentType: 'application/octet-stream' } })
  // Close the read-then-write window: if the job was deleted meanwhile, undo the write.
  const after = await env.TRIAL_DB.prepare(live).bind(id).first<{ status: string; attempts: number }>()
  if (!writable(after) && after?.status !== 'complete') {
    await env.TRIAL_BUCKET.delete(key)
    return new Response('gone', { status: 410 })
  }
  return new Response(null, { status: 204 })
}
