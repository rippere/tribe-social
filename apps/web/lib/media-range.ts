// HTTP Range support for videos on the static Cloudflare Pages site.
//
// Pages' asset server answers `Range: bytes=…` with a full 200, so browsers mark the
// <video> as unseekable: the demo's seek bar did nothing. functions/demo and
// functions/media route video requests through here and answer ranges with a 206.
// Everything that isn't a range request passes straight through.

export interface AssetsEnv {
  ASSETS: { fetch: (input: Request | string) => Promise<Response> }
}

const RANGE_RE = /^bytes=(\d*)-(\d*)$/

export async function serveWithRange(request: Request, env: AssetsEnv): Promise<Response> {
  // Fetch the whole asset without the Range header (Pages would ignore it anyway).
  const asset = await env.ASSETS.fetch(new Request(request.url, { method: 'GET' }))
  const range = request.headers.get('range')
  const m = range ? RANGE_RE.exec(range.trim()) : null
  if (!asset.ok || !m || (m[1] === '' && m[2] === '')) {
    const headers = new Headers(asset.headers)
    headers.set('Accept-Ranges', 'bytes')
    return new Response(request.method === 'HEAD' ? null : asset.body, { status: asset.status, headers })
  }

  const body = await asset.arrayBuffer()
  const size = body.byteLength
  let start: number
  let end: number
  if (m[1] === '') {
    // Suffix range: the last N bytes.
    start = Math.max(0, size - Number(m[2]))
    end = size - 1
  } else {
    start = Number(m[1])
    end = m[2] === '' ? size - 1 : Math.min(Number(m[2]), size - 1)
  }
  if (start >= size || start > end) {
    return new Response(null, { status: 416, headers: { 'Content-Range': `bytes */${size}`, 'Accept-Ranges': 'bytes' } })
  }

  const headers = new Headers()
  for (const k of ['content-type', 'etag', 'cache-control', 'last-modified']) {
    const v = asset.headers.get(k)
    if (v) headers.set(k, v)
  }
  headers.set('Accept-Ranges', 'bytes')
  headers.set('Content-Range', `bytes ${start}-${end}/${size}`)
  headers.set('Content-Length', String(end - start + 1))
  return new Response(request.method === 'HEAD' ? null : body.slice(start, end + 1), { status: 206, headers })
}
