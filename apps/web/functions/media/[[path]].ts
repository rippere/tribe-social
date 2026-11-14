// Cloudflare Pages Function: /media/* with HTTP Range support, so videos are seekable.
// See lib/media-range.ts.
import { serveWithRange, type AssetsEnv } from '../../lib/media-range'

export const onRequestGet = ({ request, env }: { request: Request; env: AssetsEnv }) => serveWithRange(request, env)
export const onRequestHead = onRequestGet
