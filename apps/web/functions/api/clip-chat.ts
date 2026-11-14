// Cloudflare Pages Function: POST /api/clip-chat on the static site. Uses the
// Workers AI binding (wrangler.toml) unless CHAT_LLM_BASE_URL + CHAT_LLM_API_KEY
// are set as Pages secrets.
import { handleClipChat, type ChatEnv } from '../../lib/clip-chat'

export const onRequestPost = ({ request, env }: { request: Request; env: ChatEnv }) =>
  handleClipChat(request, env)
