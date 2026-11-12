// Cloudflare Pages Function: POST /api/waitlist on the static site. Stores each
// signup in the WAITLIST KV namespace (bound in wrangler.toml).
import { handleWaitlist, type WaitlistEnv } from '../../lib/waitlist'

export const onRequestPost = ({ request, env }: { request: Request; env: WaitlistEnv }) =>
  handleWaitlist(request, env)
