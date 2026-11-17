#!/usr/bin/env node
// Invite waitlist signups to the PrePost research trial.
//
//   node scripts/invite.mjs [--dry-run] [--print-link] [--site URL] <email...>
//   node scripts/invite.mjs --revoke <code...>
//
// For each email: checks that WAITLIST KV has `signup:<email>`, writes
// `invite:<22-char base64url code>` → {email, issued, expires (30 d), max_uses: 3, used, revoked},
// and emails the private link <site>/trial#<code> through Resend. The code sits in the
// URL fragment, so it never reaches server logs.
//
//   --dry-run     write the invite and print the link; send no email
//   --print-link  also print the link when emailing (otherwise only a code prefix)
//   --site URL    link origin (default https://prepost-clw.pages.dev)
//   --revoke      mark invites revoked (uploads with them are refused)
//
// Needs `npx wrangler@4` logged in. RESEND_API_KEY comes from the environment or from
// ~/.config/prepost/env (read here, never printed).
import { execFileSync } from 'node:child_process'
import { randomBytes } from 'node:crypto'
import { readFileSync } from 'node:fs'
import { homedir } from 'node:os'
import { join } from 'node:path'

const NAMESPACE_ID = 'd2d0c4cb3fed43b9a0029204168452f4' // WAITLIST (wrangler.toml)
const FROM = 'PrePost <prepost@riphere.com>'
const MAX_USES = 3
const DAYS = 30
const EMAIL_RE = /^[^\s@]{1,64}@[^\s@]{1,190}\.[^\s@]{2,24}$/

const args = process.argv.slice(2)
const flag = (name) => {
  const i = args.indexOf(name)
  if (i === -1) return false
  args.splice(i, 1)
  return true
}
const option = (name, fallback) => {
  const i = args.indexOf(name)
  if (i === -1) return fallback
  const v = args[i + 1]
  args.splice(i, 2)
  return v
}

const dryRun = flag('--dry-run')
const printLink = flag('--print-link')
const revoke = flag('--revoke')
const site = String(option('--site', 'https://prepost-clw.pages.dev')).replace(/\/$/, '')

function wrangler(...a) {
  return execFileSync('npx', ['--yes', 'wrangler@4', 'kv', 'key', ...a, '--namespace-id', NAMESPACE_ID, '--remote'], {
    encoding: 'utf8',
    stdio: ['ignore', 'pipe', 'pipe'],
  })
}

function kvGet(key) {
  try {
    const out = wrangler('get', key, '--text').trim()
    return out === '' || /^Value not found/i.test(out) ? null : out
  } catch {
    return null
  }
}

const kvPut = (key, value, expiration) =>
  wrangler('put', key, value, ...(expiration ? ['--expiration', String(expiration)] : []))

function resendKey() {
  if (process.env.RESEND_API_KEY) return process.env.RESEND_API_KEY
  try {
    const line = readFileSync(join(homedir(), '.config/prepost/env'), 'utf8')
      .split('\n')
      .find((l) => l.startsWith('RESEND_API_KEY='))
    return line ? line.slice('RESEND_API_KEY='.length).trim() : ''
  } catch {
    return ''
  }
}

const esc = (s) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;')

function inviteText(link, expires) {
  return [
    "You're invited to the PrePost research trial.",
    '',
    `Your private link (good for ${MAX_USES} clips until ${expires.slice(0, 10)}):`,
    link,
    '',
    "Upload a video of up to 60 seconds (MP4 or MOV, 50 MB max). PrePost runs Meta's",
    'TRIBE v2 brain-encoding model on it and shows the predicted brain response, second',
    'by second. It is a free research trial, and the prediction is not shown to forecast',
    'engagement or views (pilot: r = 0.25, p = 0.24, n = 24).',
    '',
    'The video is deleted once it is scored (72 hours at most). The result is kept for',
    '30 days at a private link, and you can delete it sooner.',
    '',
    'The link is yours: anyone who has it can use your uploads.',
    '',
    '— PrePost (TRIBE v2 is CC BY-NC 4.0, non-commercial research use only)',
  ].join('\n')
}

function inviteHtml(link, expires) {
  const l = esc(link)
  return `<!doctype html><html><body style="margin:0;padding:24px;background:#ffffff;color:#111111;font:16px/1.5 -apple-system,Segoe UI,Helvetica,Arial,sans-serif">
<div style="max-width:520px;margin:0 auto">
<p style="margin:0 0 16px">You're invited to the PrePost research trial.</p>
<p style="margin:0 0 16px"><a href="${l}" style="color:#111111;font-weight:600">Open your private trial link</a><br><span style="color:#555555;font-size:14px">Good for ${MAX_USES} clips until ${esc(expires.slice(0, 10))}.</span></p>
<p style="margin:0 0 16px">Upload a video of up to 60 seconds (MP4 or MOV, 50 MB max). PrePost runs Meta's TRIBE v2 brain-encoding model on it and shows the predicted brain response, second by second. It is a free research trial, and the prediction is not shown to forecast engagement or views (pilot: r = 0.25, p = 0.24, n = 24).</p>
<p style="margin:0 0 16px;font-size:14px;color:#555555">The video is deleted once it is scored (72 hours at most). The result is kept for 30 days at a private link, and you can delete it sooner. The link is yours: anyone who has it can use your uploads.</p>
<p style="margin:0 0 16px;color:#555555;font-size:13px">TRIBE v2 is CC BY-NC 4.0, non-commercial research use only.</p>
<p style="margin:0">— PrePost</p>
</div></body></html>`
}

async function sendInvite(to, link, expires, code) {
  const key = resendKey()
  if (!key) throw new Error('RESEND_API_KEY not found (env or ~/.config/prepost/env)')
  const res = await fetch('https://api.resend.com/emails', {
    method: 'POST',
    headers: { Authorization: `Bearer ${key}`, 'Content-Type': 'application/json', 'Idempotency-Key': `trial-invite:${code}` },
    body: JSON.stringify({ from: FROM, to: [to], subject: 'Your PrePost trial invite', text: inviteText(link, expires), html: inviteHtml(link, expires) }),
  })
  if (!res.ok) throw new Error(`Resend ${res.status}: ${(await res.text()).slice(0, 200)}`)
}

async function invite(rawEmail) {
  const email = rawEmail.trim().toLowerCase()
  if (!EMAIL_RE.test(email)) return console.error(`skip ${rawEmail}: not an email address`)
  if (!kvGet(`signup:${email}`)) return console.error(`skip ${email}: no waitlist signup`)

  const code = randomBytes(16).toString('base64url') // 22 chars
  const issued = new Date()
  const expires = new Date(issued.getTime() + DAYS * 86400_000)
  const record = { email, issued: issued.toISOString(), expires: expires.toISOString(), max_uses: MAX_USES, used: 0, revoked: false }
  kvPut(`invite:${code}`, JSON.stringify(record), Math.floor(expires.getTime() / 1000) + 86400)
  const link = `${site}/trial#${code}`

  if (dryRun) return console.log(`invite ${email} (dry run, no email): ${link}`)
  await sendInvite(email, link, record.expires, code)
  console.log(`invited ${email}: emailed, code ${code.slice(0, 4)}…${printLink ? ` ${link}` : ''}`)
}

function revokeCode(code) {
  const raw = kvGet(`invite:${code}`)
  if (!raw) return console.error(`skip ${code.slice(0, 4)}…: no such invite`)
  const record = JSON.parse(raw)
  kvPut(`invite:${code}`, JSON.stringify({ ...record, revoked: true }), Math.floor(Date.parse(record.expires) / 1000) + 86400)
  console.log(`revoked ${code.slice(0, 4)}… (${record.email})`)
}

if (args.length === 0) {
  console.error('usage: node scripts/invite.mjs [--dry-run] [--print-link] [--site URL] <email...> | --revoke <code...>')
  process.exit(2)
}
for (const a of args) {
  try {
    if (revoke) revokeCode(a)
    else await invite(a)
  } catch (err) {
    console.error(`failed ${a}: ${err instanceof Error ? err.message : String(err)}`)
    process.exitCode = 1
  }
}
