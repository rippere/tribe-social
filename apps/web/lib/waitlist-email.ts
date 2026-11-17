// Thank-you email for a first-time waitlist signup, sent through Resend's HTTP API.
// Kept dependency-free (plain fetch) so it runs unchanged in a Pages Function.
//
// Config (Pages project secrets/vars, never committed):
//   RESEND_API_KEY  sending-only Resend key. Unset → no email is sent, signup still works.
//   WAITLIST_FROM   optional sender, default "PrePost <prepost@riphere.com>".

export type EmailEnv = {
  RESEND_API_KEY?: string
  WAITLIST_FROM?: string
}

const DEFAULT_FROM = 'PrePost <prepost@riphere.com>'
const RESEND_URL = 'https://api.resend.com/emails'

export const SUBJECT = 'Thanks for joining the PrePost waitlist'

export function thankYouText(siteUrl: string): string {
  return [
    'Thanks for joining the PrePost waitlist.',
    '',
    "PrePost runs Meta's TRIBE v2 brain-encoding model on a short video and shows the",
    'predicted brain response, second by second. It is a free research preview: the',
    'predictions are not yet shown to forecast engagement or views.',
    '',
    "We're opening a small, invite-only trial. When a spot opens we'll email you a",
    'private link to try it on your own clips.',
    '',
    `Read how it works: ${siteUrl}/science`,
    '',
    "Didn't sign up, or want off the list? Reply to this email and we'll remove you.",
    '',
    '— PrePost',
  ].join('\n')
}

export const escapeHtml = (s: string) =>
  s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;')

export function thankYouHtml(siteUrl: string): string {
  const science = escapeHtml(`${siteUrl}/science`)
  return `<!doctype html><html><body style="margin:0;padding:24px;background:#ffffff;color:#111111;font:16px/1.5 -apple-system,Segoe UI,Helvetica,Arial,sans-serif">
<div style="max-width:520px;margin:0 auto">
<p style="margin:0 0 16px">Thanks for joining the PrePost waitlist.</p>
<p style="margin:0 0 16px">PrePost runs Meta's TRIBE v2 brain-encoding model on a short video and shows the predicted brain response, second by second. It is a free research preview: the predictions are not yet shown to forecast engagement or views.</p>
<p style="margin:0 0 16px">We're opening a small, invite-only trial. When a spot opens we'll email you a private link to try it on your own clips.</p>
<p style="margin:0 0 16px"><a href="${science}" style="color:#111111">Read how it works</a></p>
<p style="margin:0 0 16px;color:#555555;font-size:14px">Didn't sign up, or want off the list? Reply to this email and we'll remove you.</p>
<p style="margin:0">— PrePost</p>
</div></body></html>`
}

export interface EmailMessage {
  to: string
  subject: string
  text: string
  html: string
  /** Resend drops a repeat send with the same key, so a retried request can't double-mail. */
  idempotencyKey: string
  /** Short label for logs. Never the address. */
  tag: string
}

/**
 * Send one email through Resend. Never throws: a failed send must not fail the
 * request that triggered it, so errors are logged and reported as false.
 */
export async function sendEmail(env: EmailEnv, msg: EmailMessage): Promise<boolean> {
  if (!env.RESEND_API_KEY) return false
  try {
    const res = await fetch(RESEND_URL, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${env.RESEND_API_KEY}`,
        'Content-Type': 'application/json',
        'Idempotency-Key': msg.idempotencyKey.slice(0, 256),
      },
      body: JSON.stringify({
        from: env.WAITLIST_FROM || DEFAULT_FROM,
        to: [msg.to],
        subject: msg.subject,
        text: msg.text,
        html: msg.html,
      }),
    })
    if (!res.ok) {
      console.error(`${msg.tag} email failed`, res.status, (await res.text()).slice(0, 300))
      return false
    }
    return true
  } catch (err) {
    console.error(`${msg.tag} email error`, err instanceof Error ? err.message : String(err))
    return false
  }
}

/** Send the thank-you email (never throws; see sendEmail). */
export function sendThankYou(env: EmailEnv, to: string, siteUrl: string): Promise<boolean> {
  return sendEmail(env, {
    to,
    subject: SUBJECT,
    text: thankYouText(siteUrl),
    html: thankYouHtml(siteUrl),
    idempotencyKey: `waitlist-thanks:${to}`,
    tag: 'waitlist',
  })
}
