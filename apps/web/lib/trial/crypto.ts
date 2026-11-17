// Tokens, hashes and HMAC signatures for the trial (Web Crypto only, so the same code
// runs in Pages Functions, the dispatcher Worker and Node 20+).

const enc = new TextEncoder()

export function base64url(bytes: Uint8Array): string {
  let s = ''
  for (const b of bytes) s += String.fromCharCode(b)
  return btoa(s).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
}

/** Random base64url string from `bytes` random bytes (16 → 22 chars, 32 → 43 chars). */
export function randomToken(bytes = 32): string {
  return base64url(crypto.getRandomValues(new Uint8Array(bytes)))
}

export async function sha256Hex(s: string): Promise<string> {
  const d = new Uint8Array(await crypto.subtle.digest('SHA-256', enc.encode(s)))
  return Array.from(d, (b) => b.toString(16).padStart(2, '0')).join('')
}

async function hmacKey(secret: string): Promise<CryptoKey> {
  return crypto.subtle.importKey('raw', enc.encode(secret), { name: 'HMAC', hash: 'SHA-256' }, false, [
    'sign',
    'verify',
  ])
}

export async function hmac(secret: string, message: string): Promise<string> {
  const sig = await crypto.subtle.sign('HMAC', await hmacKey(secret), enc.encode(message))
  return base64url(new Uint8Array(sig))
}

/** Constant-time compare of two signatures (after computing the expected one). */
export async function hmacVerify(secret: string, message: string, sig: string): Promise<boolean> {
  const expected = await hmac(secret, message)
  if (expected.length !== sig.length) return false
  let diff = 0
  for (let i = 0; i < expected.length; i++) diff |= expected.charCodeAt(i) ^ sig.charCodeAt(i)
  return diff === 0
}

export const TOKEN_RE = /^[A-Za-z0-9_-]{43}$/
export const INVITE_RE = /^[A-Za-z0-9_-]{22}$/

// ── Signed blob URLs ─────────────────────────────────────────────────────────
// R2 bindings can't presign S3 URLs, so the GPU worker fetches the clip from (and
// PUTs the cortex activity to) functions/api/trial/blob.ts with an HMAC-signed,
// expiring, method- and key-bound URL instead. Same effect as an R2 presigned URL.

export const blobMessage = (method: 'GET' | 'PUT', key: string, exp: number) => `blob\n${method}\n${key}\n${exp}`

export async function signedBlobUrl(
  site: string,
  secret: string,
  method: 'GET' | 'PUT',
  key: string,
  ttlSeconds: number,
): Promise<string> {
  const exp = Math.floor(Date.now() / 1000) + ttlSeconds
  const sig = await hmac(secret, blobMessage(method, key, exp))
  const q = new URLSearchParams({ key, m: method, exp: String(exp), sig })
  return `${site}/api/trial/blob?${q}`
}

export const webhookMessage = (jobId: string, attempt: number) => `webhook\n${jobId}\n${attempt}`

export async function webhookUrl(site: string, secret: string, jobId: string, attempt: number): Promise<string> {
  const sig = await hmac(secret, webhookMessage(jobId, attempt))
  const q = new URLSearchParams({ job: jobId, a: String(attempt), sig })
  return `${site}/api/trial/webhook?${q}`
}
