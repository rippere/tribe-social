// Small HTTP helpers for the trial's Pages Functions.

import { sha256Hex, TOKEN_RE, INVITE_RE } from './crypto'
import type { KVNamespace, TrialEnv } from './env'
import type { JobRow } from './jobs'

export const json = (body: unknown, status = 200, extra: Record<string, string> = {}) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json', 'cache-control': 'no-store', ...extra },
  })

export const notFound = () => json({ error: 'Not found.' }, 404)

/** `Authorization: Bearer <result token>`: the token travels in a header, never a URL. */
export function bearer(request: Request): string | null {
  const h = request.headers.get('authorization') ?? ''
  const m = /^Bearer\s+(\S+)$/i.exec(h)
  return m && TOKEN_RE.test(m[1]) ? m[1] : null
}

export async function jobByToken(env: TrialEnv, token: string): Promise<JobRow | null> {
  return env.TRIAL_DB.prepare('SELECT * FROM jobs WHERE token_hash = ?').bind(await sha256Hex(token)).first<JobRow>()
}

export interface Invite {
  email: string
  issued: string
  expires: string
  max_uses: number
  used: number
  revoked: boolean
}

export type InviteCheck = { ok: true; code: string; invite: Invite } | { ok: false; status: number; error: string }

/** Validate an invite code against KV `invite:<code>`. Uses are counted in D1 by the caller. */
export async function checkInvite(kv: KVNamespace, code: string | null | undefined): Promise<InviteCheck> {
  if (!code || !INVITE_RE.test(code)) return { ok: false, status: 401, error: 'This upload needs a valid invite link.' }
  const raw = await kv.get(`invite:${code}`)
  if (!raw) return { ok: false, status: 401, error: 'This upload needs a valid invite link.' }
  let invite: Invite
  try {
    invite = JSON.parse(raw) as Invite
  } catch {
    return { ok: false, status: 401, error: 'This upload needs a valid invite link.' }
  }
  if (invite.revoked) return { ok: false, status: 403, error: 'This invite has been withdrawn.' }
  if (Date.parse(invite.expires) < Date.now()) return { ok: false, status: 403, error: 'This invite has expired.' }
  return { ok: true, code, invite }
}

/** Uses consumed so far, from D1 (the source of truth; KV `used` is a mirror). */
export async function inviteUses(env: TrialEnv, inviteHash: string): Promise<{ used: number; active: number }> {
  const r = await env.TRIAL_DB.prepare(
    `SELECT COUNT(*) AS used, SUM(status IN ('uploading', 'queued', 'submitted', 'running')) AS active
     FROM jobs WHERE invite_hash = ?`,
  )
    .bind(inviteHash)
    .first<{ used: number; active: number | null }>()
  return { used: r?.used ?? 0, active: r?.active ?? 0 }
}
