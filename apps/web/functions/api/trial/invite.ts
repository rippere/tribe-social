// POST /api/trial/invite {code} → whether the invite works and how many uploads remain.
// The code comes in the body (the page reads it from the URL fragment), never a URL.
import { sha256Hex } from '../../../lib/trial/crypto'
import type { PagesEnv } from '../../../lib/trial/env'
import { checkInvite, inviteUses, json } from '../../../lib/trial/http'

export const onRequestPost = async ({ request, env }: { request: Request; env: PagesEnv }) => {
  let code: unknown
  try {
    code = ((await request.json()) as { code?: unknown }).code
  } catch {
    return json({ error: 'Send the invite code as JSON.' }, 400)
  }
  const check = await checkInvite(env.WAITLIST, typeof code === 'string' ? code : null)
  if (!check.ok) return json({ error: check.error }, check.status)
  const { used, active } = await inviteUses(env, await sha256Hex(check.code))
  return json({
    ok: true,
    remaining: Math.max(0, check.invite.max_uses - used),
    max_uses: check.invite.max_uses,
    active,
    expires: check.invite.expires,
  })
}
