import type { CSSProperties, ReactNode } from 'react'
import { Video } from '@remotion/media'
import { Sequence, interpolate, staticFile, useCurrentFrame } from 'remotion'
import { phraseAt, type Word } from './components'
import trackData from './data/mascot_track.json'
import { C, FONT, FPS } from './theme'

/*
 * The mascot is a chain of one-off shots, each keyed to alpha WebM. Talking shots
 * are Seedance, lip-synced to their sentence (scripts/talk_shots.json); the walk-in
 * and the watching scene are Kling (scripts/mascot_shots.json). Every shot starts
 * and ends on the same anchor frames, so consecutive shots join without a jump.
 *
 * mascot_track.json holds the character's per-frame bounding box (normalised to
 * the clip), written by scripts/key_mascot.py; cutsFor reads clip lengths from it.
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

/**
 * Shots back to back at their natural speed: one shot per spoken sentence, so a
 * gesture lands on the word it was generated for. `at` pins a shot's start (in
 * seconds from the scene start) when it has to meet something on screen, like a
 * reaction on the result's peak; the shot before it is then sped up or slowed to
 * fill the gap.
 */
export function cutsFor(shots: { clip: string; at?: number }[]): Cut[] {
  const natural = (clip: string) => {
    const t = TRACKS[clip]
    if (!t) throw new Error(`No track for mascot clip "${clip}": key it with scripts/key_mascot.py (npm run sync)`)
    return Math.round((t.frames.length * FPS) / t.fps)
  }
  const starts: number[] = []
  let f = 0
  shots.forEach((s, i) => {
    f = s.at !== undefined ? Math.round(s.at * FPS) : i === 0 ? 0 : f
    starts.push(f)
    f += natural(s.clip)
  })
  return shots.map((s, i) => {
    const from = starts[i]
    const dur = (i + 1 < shots.length ? starts[i + 1] : from + natural(s.clip)) - from
    const rate = natural(s.clip) / dur
    // A pin too close to (or before) the previous shot would squeeze it past what reads as motion.
    if (!(rate >= 0.5 && rate <= 2)) throw new Error(`Shot "${s.clip}" would play at ${rate.toFixed(2)}x: move the next shot's pin`)
    return { clip: s.clip, from, dur, rate }
  })
}

/** Length of a chain of cuts, in frames. */
export function cutsLength(cuts: Cut[]): number {
  const last = cuts[cuts.length - 1]
  return last.from + last.dur
}

function boxAt(cuts: Cut[], frame: number): Box {
  const c = cuts.find(k => frame >= k.from && frame < k.from + k.dur) ?? cuts[cuts.length - 1]
  const t = TRACKS[c.clip]
  if (!t) return null
  const i = Math.floor(((frame - c.from) * c.rate * t.fps) / FPS)
  return t.frames[Math.min(t.frames.length - 1, Math.max(0, i))]
}

/** The centre anchor (A_C) as keyed: centre x, feet and height, normalised to the clip. */
const STAND = { cx: 0.498, b: 0.946, h: 0.354 }

/**
 * Seedance sometimes frames a talking shot tighter than its start image (same pose,
 * the character twice the size). Such a shot still starts and ends on itself, so
 * scaling it about its feet back to the anchor's size and spot joins it cleanly.
 * Small offsets (feet a few pixels high) are only moved, not scaled.
 */
function fitToAnchor(clip: string, plate: Plate): CSSProperties {
  const f = clip.startsWith('t_') ? TRACKS[clip]?.frames[0] : null
  if (!f) return {}
  const raw = STAND.h / (f.b - f.t)
  const s = Math.abs(raw - 1) < 0.04 ? 1 : raw
  if (s === 1 && Math.abs(STAND.cx - f.cx) < 0.002 && Math.abs(STAND.b - f.b) < 0.002) return {}
  return {
    transformOrigin: `${f.cx * 100}% ${f.b * 100}%`,
    transform: `translate(${(STAND.cx - f.cx) * plate.w}px, ${(STAND.b - f.b) * plate.h}px) scale(${s})`,
  }
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
              style={{ position: 'absolute', left: plate.x, top: plate.y, width: plate.w, height: plate.h, ...fitToAnchor(c.clip, plate) }}
            />
          </Sequence>
        ) : null,
      )}
    </>
  )
}

/**
 * The narration as captions. Landscape: a lower third at the bottom left, clear of
 * the character, who stands at centre. Portrait: centred in the band between the
 * scorer UI and the character's head. Words light up as they are spoken.
 */
export function Captions({ words, t, portrait }: { words: Word[]; t: number; portrait: boolean }) {
  const phrase = phraseAt(words, t)
  if (!phrase) return null
  const size = portrait ? 46 : 40
  const o = interpolate(t, [phrase[0].s - 0.25, phrase[0].s], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' })
  const box: CSSProperties = portrait
    ? { left: 60, right: 60, bottom: 1920 - 1480, textAlign: 'center', justifyContent: 'center' }
    : { left: 64, bottom: 64, maxWidth: 660, borderLeft: `4px solid ${C.accent}`, paddingLeft: 24 }
  return (
    <div style={{ position: 'absolute', display: 'flex', flexWrap: 'wrap', fontFamily: FONT, fontSize: size, fontWeight: 500, lineHeight: 1.25, letterSpacing: -0.3, opacity: o, textShadow: '0 2px 18px rgba(0,0,0,0.85)', ...box }}>
      <span>
        {phrase.map((w, i) => (
          <span key={i} style={{ color: t >= w.s ? C.ink : 'rgba(242,242,240,0.38)' }}>
            {w.display}
            {i < phrase.length - 1 ? ' ' : ''}
          </span>
        ))}
      </span>
    </div>
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
