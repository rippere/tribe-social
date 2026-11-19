// POST /api/clip-chat under `next dev` / `next start`. The `.node.ts` extension keeps
// this route out of the static export (next.config.ts); on Cloudflare Pages the same
// handler is served by functions/api/clip-chat.ts.
import { handleClipChat } from '@/lib/clip-chat'

export const runtime = 'nodejs'

export function POST(req: Request) {
  return handleClipChat(req, {
    CHAT_LLM_BASE_URL: process.env.CHAT_LLM_BASE_URL,
    CHAT_LLM_API_KEY: process.env.CHAT_LLM_API_KEY,
    CHAT_LLM_MODEL: process.env.CHAT_LLM_MODEL,
  })
}
