// GET/PUT /api/trial/blob?key=…&m=…&exp=…&sig=… — signed, expiring R2 access for the GPU
// worker (R2 bindings can't mint S3 presigned URLs). The signature binds method, key
// and expiry. GET serves uploads/<id>.<ext>; PUT accepts only results/<id>/activity.bin.
import { blobMessage, hmacVerify } from '../../../lib/trial/crypto'
import type { PagesEnv } from '../../../lib/trial/env'

const GET_KEY = /^uploads\/[A-Za-z0-9_-]{22}\.(mp4|mov)$/
const PUT_KEY = /^results\/[A-Za-z0-9_-]{22}\/activity\.bin$/
const MAX_ACTIVITY_BYTES = 8 * 1024 * 1024 // 75 frames × 20484 ≈ 1.5 MB; generous cap

async function authorize(request: Request, env: PagesEnv, method: 'GET' | 'PUT'): Promise<string | Response> {
  const q = new URL(request.url).searchParams
  const key = q.get('key') ?? ''
  const exp = Number(q.get('exp') ?? 'NaN')
  const sig = q.get('sig') ?? ''
  const deny = new Response('forbidden', { status: 403 })
  if (!env.TRIAL_SIGNING_KEY || q.get('m') !== method || !Number.isInteger(exp)) return deny
  if (exp < Date.now() / 1000) return deny
  if (!(method === 'GET' ? GET_KEY : PUT_KEY).test(key)) return deny
  if (!(await hmacVerify(env.TRIAL_SIGNING_KEY, blobMessage(method, key, exp), sig))) return deny
  return key
}

export const onRequestGet = async ({ request, env }: { request: Request; env: PagesEnv }) => {
  const key = await authorize(request, env, 'GET')
  if (key instanceof Response) return key
  const obj = await env.TRIAL_BUCKET.get(key)
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
  const key = await authorize(request, env, 'PUT')
  if (key instanceof Response) return key
  // Only for a job that is still in flight: a deleted result must not be recreated.
  const id = key.split('/')[1]
  const job = await env.TRIAL_DB.prepare(`SELECT status FROM jobs WHERE id = ?`).bind(id).first<{ status: string }>()
  if (!job || (job.status !== 'submitted' && job.status !== 'running')) return new Response('gone', { status: 410 })
  const body = await request.arrayBuffer()
  if (body.byteLength === 0 || body.byteLength > MAX_ACTIVITY_BYTES || body.byteLength % 20484 !== 0) {
    return new Response('bad size', { status: 400 })
  }
  await env.TRIAL_BUCKET.put(key, body, { httpMetadata: { contentType: 'application/octet-stream' } })
  return new Response(null, { status: 204 })
}
