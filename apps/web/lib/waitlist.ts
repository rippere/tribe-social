// Waitlist signups for the static site. Served by functions/api/waitlist.ts on
// Cloudflare Pages and stored in the WAITLIST KV namespace, one key per email.
// The extra fields (role, monthly draft volume, company) are the demand signal we
// want before any letter of intent: who is asking, and at what volume.

export type WaitlistEnv = {
  WAITLIST?: {
    get(key: string): Promise<string | null>
    put(key: string, value: string): Promise<void>
  }
}

export const ROLES = [
  'Influencer agency',
  'Brand creator program',
  'Performance / creative strategy',
  'Creator',
  'Other',
] as const

export const VOLUMES = ['Under 10', '10 to 19', '20 to 49', '50 or more'] as const

const EMAIL_RE = /^[^\s@]{1,64}@[^\s@]{1,190}\.[^\s@]{2,24}$/

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } })

const pick = <T extends readonly string[]>(list: T, v: unknown): T[number] | null =>
  typeof v === 'string' && (list as readonly string[]).includes(v) ? (v as T[number]) : null

export async function handleWaitlist(request: Request, env: WaitlistEnv): Promise<Response> {
  let body: Record<string, unknown>
  try {
    body = (await request.json()) as Record<string, unknown>
  } catch {
    return json({ error: 'Send the form as JSON.' }, 400)
  }
  if (!body || typeof body !== 'object') return json({ error: 'Send the form as JSON.' }, 400)

  // Honeypot: real visitors never see this field, so a filled one is a bot. Answer
  // as if it worked so the bot has nothing to learn from.
  if (typeof body.website === 'string' && body.website.trim() !== '') return json({ ok: true })

  const email = typeof body.email === 'string' ? body.email.trim().toLowerCase() : ''
  if (!EMAIL_RE.test(email)) return json({ error: 'That email address doesn’t look right.' }, 400)

  const role = pick(ROLES, body.role)
  if (!role) return json({ error: 'Pick the role that fits you best.' }, 400)
  const volume = pick(VOLUMES, body.volume)
  const company = typeof body.company === 'string' ? body.company.trim().slice(0, 120) : ''

  if (!env.WAITLIST) return json({ error: 'The waitlist isn’t open yet. Try again soon.' }, 503)

  const key = `signup:${email}`
  let joined: string | undefined
  try {
    const existing = await env.WAITLIST.get(key)
    joined = existing ? (JSON.parse(existing) as { joined?: string }).joined : undefined
  } catch {
    joined = undefined
  }
  const now = new Date().toISOString()
  await env.WAITLIST.put(key, JSON.stringify({ email, role, volume, company, joined: joined ?? now, updated: now }))

  return json({ ok: true })
}
