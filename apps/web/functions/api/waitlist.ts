// Cloudflare Pages Function: POST /api/waitlist on the static site. Stores each
// signup in the WAITLIST KV namespace (bound in wrangler.toml) and, for a first-time
// signup, sends a thank-you email via Resend (RESEND_API_KEY, a Pages secret).
import { handleWaitlist, type WaitlistEnv, type WaitUntil } from '../../lib/waitlist'

export const onRequestPost = ({
  request,
  env,
  waitUntil,
}: {
  request: Request
  env: WaitlistEnv
  waitUntil: WaitUntil
}) => handleWaitlist(request, env, waitUntil)
