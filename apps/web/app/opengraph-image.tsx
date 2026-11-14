import { ImageResponse } from 'next/og'
import { readFile } from 'node:fs/promises'
import { join } from 'node:path'
import { SITE_NAME, SITE_TAGLINE } from '@/lib/site'

// Social card for every page that doesn't set its own (link previews in Slack, iMessage,
// LinkedIn, X). Rendered once at build time.
export const alt = `${SITE_NAME}: ${SITE_TAGLINE}`
export const size = { width: 1200, height: 630 }
export const contentType = 'image/png'
export const dynamic = 'force-static'

export default async function OpengraphImage() {
  const face = await readFile(join(process.cwd(), 'public/mascot/mascot-face.png'))
  const src = `data:image/png;base64,${face.toString('base64')}`
  return new ImageResponse(
    (
      <div style={{ width: '100%', height: '100%', display: 'flex', alignItems: 'center', background: '#0B0B0B', color: '#F2F2F0', padding: '0 88px', gap: 64 }}>
        <div style={{ display: 'flex', flexDirection: 'column', flex: 1 }}>
          <div style={{ fontSize: 120, fontWeight: 600, letterSpacing: -4, lineHeight: 1 }}>{SITE_NAME}</div>
          <div style={{ fontSize: 46, marginTop: 28, lineHeight: 1.2, color: '#F2F2F0' }}>{`${SITE_TAGLINE}, second by second.`}</div>
          <div style={{ fontSize: 28, marginTop: 36, color: '#5CE1F0' }}>A research preview for reviewing creator video.</div>
        </div>
        <div style={{ width: 300, height: 300, borderRadius: 150, background: '#1C1C1B', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={src} width={250} height={250} alt="" />
        </div>
      </div>
    ),
    size,
  )
}
