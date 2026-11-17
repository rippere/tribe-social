// Trial emails (results ready / could not score), sent with the waitlist's Resend helper.
// The invite email is sent by scripts/invite.mjs, which runs in Node outside the bundle.

import { escapeHtml, sendEmail, type EmailEnv } from '../waitlist-email'
import { CLAIM } from './claim'

const wrap = (body: string) => `<!doctype html><html><body style="margin:0;padding:24px;background:#ffffff;color:#111111;font:16px/1.5 -apple-system,Segoe UI,Helvetica,Arial,sans-serif">
<div style="max-width:520px;margin:0 auto">${body}
<p style="margin:16px 0 0;color:#555555;font-size:13px">PrePost is a free research trial. It runs Meta's TRIBE v2 model (CC BY-NC 4.0), for non-commercial research only.</p>
<p style="margin:16px 0 0">— PrePost</p>
</div></body></html>`

export function sendResultReady(env: EmailEnv, to: string, resultUrl: string, jobId: string): Promise<boolean> {
  const link = escapeHtml(resultUrl)
  return sendEmail(env, {
    to,
    subject: 'Your PrePost result is ready',
    idempotencyKey: `trial-ready:${jobId}`,
    tag: 'trial-ready',
    text: [
      'Your clip has been scored. Your result is at this private link:',
      '',
      resultUrl,
      '',
      `${CLAIM}.`,
      '',
      'The video itself has been deleted. The result is kept for 30 days, and you can',
      'delete it sooner from the result page. Anyone with the link can open it, so share',
      'it only with people you trust.',
      '',
      '— PrePost (free research trial; TRIBE v2 is CC BY-NC 4.0, non-commercial use only)',
    ].join('\n'),
    html: wrap(`<p style="margin:0 0 16px">Your clip has been scored.</p>
<p style="margin:0 0 16px"><a href="${link}" style="color:#111111;font-weight:600">Open your result</a></p>
<p style="margin:0 0 16px;font-size:14px">${escapeHtml(CLAIM)}.</p>
<p style="margin:0 0 16px;font-size:14px;color:#555555">The video itself has been deleted. The result is kept for 30 days, and you can delete it sooner from the result page. Anyone with the link can open it, so share it only with people you trust.</p>`),
  })
}

export function sendResultFailed(env: EmailEnv, to: string, jobId: string, reason: string): Promise<boolean> {
  return sendEmail(env, {
    to,
    subject: 'We could not score your PrePost clip',
    idempotencyKey: `trial-failed:${jobId}`,
    tag: 'trial-failed',
    text: [
      'We could not score the clip you uploaded.',
      '',
      `Reason: ${reason}`,
      '',
      'The video has been deleted. Reply to this email and we will sort it out.',
      '',
      '— PrePost',
    ].join('\n'),
    html: wrap(`<p style="margin:0 0 16px">We could not score the clip you uploaded.</p>
<p style="margin:0 0 16px;font-size:14px">Reason: ${escapeHtml(reason)}</p>
<p style="margin:0 0 16px;font-size:14px;color:#555555">The video has been deleted. Reply to this email and we will sort it out.</p>`),
  })
}
