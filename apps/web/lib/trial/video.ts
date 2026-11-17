// Container sniffing for uploads: trust the bytes, not the filename or Content-Type.
// MP4 and QuickTime are both ISO base-media files: a sequence of [size:u32][type:4cc]
// boxes. We check the first box and read the movie duration from moov/mvhd.

export type VideoKind = 'mp4' | 'mov'

const fourcc = (b: Uint8Array, o: number) => String.fromCharCode(b[o], b[o + 1], b[o + 2], b[o + 3])

// Old QuickTime files may start with one of these instead of ftyp.
const QT_FIRST_BOXES = new Set(['moov', 'mdat', 'wide', 'free', 'skip', 'pnot'])

/** 'mp4' | 'mov' from the magic bytes, or null when it is neither. */
export function sniffVideo(b: Uint8Array): VideoKind | null {
  if (b.length < 12) return null
  const type = fourcc(b, 4)
  if (type === 'ftyp') {
    const brand = fourcc(b, 8)
    return brand === 'qt  ' ? 'mov' : 'mp4'
  }
  return QT_FIRST_BOXES.has(type) ? 'mov' : null
}

function u32(b: Uint8Array, o: number): number {
  return ((b[o] << 24) | (b[o + 1] << 16) | (b[o + 2] << 8) | b[o + 3]) >>> 0
}

/** Walk boxes in [start, end) and return the offset/size of the first `type`. */
function findBox(b: Uint8Array, start: number, end: number, type: string): { off: number; size: number; hdr: number } | null {
  let o = start
  while (o + 8 <= end) {
    let size = u32(b, o)
    let hdr = 8
    if (size === 1) {
      if (o + 16 > end) return null
      const hi = u32(b, o + 8)
      const lo = u32(b, o + 12)
      size = hi * 2 ** 32 + lo
      hdr = 16
    } else if (size === 0) {
      size = end - o
    }
    if (size < hdr) return null
    if (fourcc(b, o + 4) === type) return { off: o, size, hdr }
    o += size
  }
  return null
}

/** Duration in seconds from moov/mvhd, or null when it can't be read. */
export function videoDurationSeconds(b: Uint8Array): number | null {
  const moov = findBox(b, 0, b.length, 'moov')
  if (!moov) return null
  const mvhd = findBox(b, moov.off + moov.hdr, Math.min(b.length, moov.off + moov.size), 'mvhd')
  if (!mvhd) return null
  const p = mvhd.off + mvhd.hdr
  const version = b[p]
  if (version === 1) {
    if (p + 32 > b.length) return null
    const timescale = u32(b, p + 20)
    const duration = u32(b, p + 24) * 2 ** 32 + u32(b, p + 28)
    return timescale ? duration / timescale : null
  }
  if (p + 20 > b.length) return null
  const timescale = u32(b, p + 12)
  const duration = u32(b, p + 16)
  return timescale ? duration / timescale : null
}
