import type { CSSProperties, ReactNode } from 'react'
import { Video } from '@remotion/media'
import { Sequence, interpolate, staticFile, useCurrentFrame } from 'remotion'
import { phraseAt, type Word } from './components'
import trackData from './data/mascot_track.json'
import { C, FONT, FPS } from './theme'

/*
 * The mascot is a chain of one-off Kling shots (scripts/mascot_shots.json), each
 * keyed to alpha WebM. Every shot starts and ends on the same anchor frames, so
 * consecutive shots join without a jump. A scene splits its length evenly over
 * its shots and plays each at whatever rate fills its slot (about 0.85x–1.25x).
 *
 * mascot_track.json holds the character's per-frame bounding box (normalised to
 * the clip), written by scripts/key_mascot.py. Bubbles and highlights hang off it.
 */

type Box = { l: number; r: number; t: number; b: number; cx: number } | null
interface ClipTrack {
  fps: number
  frames: Box[]
}
const TRACKS = trackData as unknown as Record<string, ClipTrack>

/** Where the 16:9 clip plate lands on the canvas. */
export interface Plate {
  x: number
  y: number
  w: number
  h: number
}

export interface Cut {
  clip: string
  from: number
  dur: number
  rate: number
}

export function cutsFor(clips: string[], frames: number): Cut[] {
  const per = frames / clips.length
  return clips.map((clip, i) => {
    const from = Math.round(i * per)
    const dur = Math.round((i + 1) * per) - from
    const t = TRACKS[clip]
    const srcFrames = t ? (t.frames.length * FPS) / t.fps : dur
    return { clip, from, dur, rate: srcFrames / dur }
  })
}

function boxAt(cuts: Cut[], frame: number): Box {
  const c = cuts.find(k => frame >= k.from && frame < k.from + k.dur) ?? cuts[cuts.length - 1]
  const t = TRACKS[c.clip]
  if (!t) return null
  const i = Math.floor(((frame - c.from) * c.rate * t.fps) / FPS)
  return t.frames[Math.min(t.frames.length - 1, Math.max(0, i))]
}

/** Character centre x on the canvas, averaged over ±k frames so a bubble riding on it doesn't jitter. */
export function charX(cuts: Cut[], frame: number, plate: Plate, k = 8): number | null {
  let sum = 0
  let n = 0
  for (let f = frame - k; f <= frame + k; f++) {
    const b = boxAt(cuts, f)
    if (b) {
      sum += b.cx
      n++
    }
  }
  return n ? plate.x + (sum / n) * plate.w : null
}

export function MascotLayer({ cuts, plate }: { cuts: Cut[]; plate: Plate }) {
  return (
    <>
      {cuts.map(c =>
        TRACKS[c.clip] ? (
          <Sequence key={c.clip} from={c.from} durationInFrames={c.dur} layout="none">
            <Video
              src={staticFile(`media/mascot/${c.clip}.webm`)}
              muted
              playbackRate={c.rate}
              style={{ position: 'absolute', left: plate.x, top: plate.y, width: plate.w, height: plate.h }}
            />
          </Sequence>
        ) : null,
      )}
    </>
  )
}

/**
 * The narration as a speech bubble on the character. `side` puts it beside the
 * head (landscape, where height is scarce) or above it (portrait).
 */
export function Bubble({
  words,
  t,
  x,
  headY,
  side,
  canvasW,
  canvasH,
  size,
  maxWidth,
}: {
  words: Word[]
  t: number
  x: number | null
  headY: number
  side: 'left' | 'right' | 'above'
  canvasW: number
  canvasH: number
  size: number
  maxWidth: number
}) {
  const phrase = phraseAt(words, t)
  if (!phrase || x === null) return null
  const first = words[0].s
  const last = words[words.length - 1].e
  const o = interpolate(t, [first - 0.25, first, last + 0.4, last + 0.7], [0, 1, 1, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' })
  const body: CSSProperties = {
    position: 'absolute',
    maxWidth,
    width: 'max-content',
    padding: `${size * 0.42}px ${size * 0.62}px`,
    borderRadius: size * 0.6,
    background: C.ink,
    fontFamily: FONT,
    fontSize: size,
    fontWeight: 500,
    lineHeight: 1.22,
    letterSpacing: -0.3,
    opacity: o,
  }
  const text = phrase.map((w, i) => (
    <span key={i} style={{ color: t >= w.s ? C.bg : 'rgba(15,15,15,0.32)' }}>
      {w.display}
      {i < phrase.length - 1 ? ' ' : ''}
    </span>
  ))
  const tw = size * 0.5
  const tail = (style: CSSProperties) => <div style={{ position: 'absolute', width: 0, height: 0, opacity: o, ...style }} />
  if (side === 'above') {
    // Clamp on the bubble's likely width, not its max, so a short phrase stays over its tail.
    const est = phrase.reduce((n, w) => n + w.display.length + 1, 0) * size * 0.52 + size * 1.24
    const half = Math.min(maxWidth, est) / 2
    const left = Math.min(Math.max(x, 24 + half), canvasW - 24 - half)
    const bottom = headY - 18 - tw
    return (
      <>
        <div style={{ ...body, left, bottom: canvasH - bottom, transform: 'translateX(-50%)', textAlign: 'center' }}>{text}</div>
        {tail({ left: x - tw, top: bottom - 1, borderLeft: `${tw}px solid transparent`, borderRight: `${tw}px solid transparent`, borderTop: `${tw}px solid ${C.ink}` })}
      </>
    )
  }
  const gap = 0.095 * canvasW + 24
  const top = headY + size * 0.3
  return side === 'right' ? (
    <>
      <div style={{ ...body, left: x + gap, top }}>{text}</div>
      {tail({ left: x + gap - tw + 1, top: top + size * 0.55, borderTop: `${tw}px solid transparent`, borderBottom: `${tw}px solid transparent`, borderRight: `${tw}px solid ${C.ink}` })}
    </>
  ) : (
    <>
      <div style={{ ...body, right: canvasW - (x - gap), top }}>{text}</div>
      {tail({ left: x - gap - 1, top: top + size * 0.55, borderTop: `${tw}px solid transparent`, borderBottom: `${tw}px solid transparent`, borderLeft: `${tw}px solid ${C.ink}` })}
    </>
  )
}

/** Seconds into a line where the first word matching `re` starts (Infinity if absent). */
export function cue(words: Word[], re: RegExp): number {
  return words.find(w => re.test(w.w))?.s ?? Infinity
}

/** 0→1→0 around a cue: the highlight that tells you what the narrator means. */
export function pulse(t: number, at: number, hold = 1.6): number {
  if (!Number.isFinite(at)) return 0
  return interpolate(t, [at - 0.15, at + 0.2, at + hold, at + hold + 0.5], [0, 1, 1, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' })
}

/** 0→1 from a cue onward. */
export function lit(t: number, at: number, dur = 0.25): number {
  if (!Number.isFinite(at)) return 0
  return interpolate(t, [at, at + dur], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' })
}

/** A UI element the narrator is talking about: an accent ring while `on` is up. */
export function Spot({ on, style, radius = 18, children }: { on: number; style?: CSSProperties; radius?: number; children: ReactNode }) {
  return (
    <div
      style={{
        borderRadius: radius,
        boxShadow: on > 0 ? `0 0 0 ${2 + on}px rgba(92,225,240,${on}), 0 0 ${56 * on}px rgba(92,225,240,${0.22 * on})` : 'none',
        transform: `scale(${1 + 0.012 * on})`,
        ...style,
      }}
    >
      {children}
    </div>
  )
}

export function useSceneTime(lead: number): number {
  return (useCurrentFrame() - lead) / FPS
}
