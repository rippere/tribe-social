import { createContext, useContext, useId, useLayoutEffect, useRef, type CSSProperties, type ReactNode, type RefObject } from 'react'
import { Video } from '@remotion/media'
import { Easing, Img, Sequence, interpolate, staticFile, useCurrentFrame } from 'remotion'
import { phraseAt, type Word } from './components'
import trackData from './data/mascot_track.json'
import { C, FONT, FPS } from './theme'

/*
 * The mascot never speaks in v6: Ben narrates off-screen. It walks in (Kling
 * intro_a, cut before its mouth starts moving), then stands idle (the keyed centre
 * anchor, animated here: breathing, a small bob, and a hop or lean on cue words)
 * while Ben talks, and watches the scored clip in the play scene (silent Kling
 * shots, scripts/mascot_shots.json). Every shot starts and ends on the same anchor
 * frame as the idle still, so shots and idle join without a jump.
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

/** How the idle character reacts to a cue word while Ben talks. */
export type BeatKind = 'hop' | 'lookL' | 'lookR' | 'lookUp' | 'nod' | 'droop'
export interface Beat {
  at: number
  kind: BeatKind
}

/** The keyed centre anchor's feet, as a fraction of the plate (scripts/key_mascot.py --still). */
export const FEET = { x: 0.498, y: 0.954 }

/** 0→1, held, →0 around a beat: ease in over `rise`, hold, ease out over `fall`. */
function envelope(t: number, at: number, rise: number, hold: number, fall: number): number {
  return interpolate(t, [at - rise * 0.3, at + rise * 0.7, at + rise * 0.7 + hold, at + rise * 0.7 + hold + fall], [0, 1, 1, 0], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
    easing: Easing.inOut(Easing.sin),
  })
}

/** The idle character's procedural offset from its anchor: px in the 1920-wide plate, degrees, scale. */
export interface Pose {
  x: number
  y: number
  rot: number
  sx: number
  sy: number
}

/**
 * Breathing (~1.2 % vertical scale), a slow bob and sway on global time (`clock`,
 * seconds since the video started, so they carry across scene cuts), plus the beats
 * around scene time `t`: a hop, a lean toward a UI element (left / right / up), a nod
 * or a droop.
 */
export function idlePose(t: number, clock: number, beats: Beat[]): Pose {
  const breathe = Math.sin((2 * Math.PI * clock) / 3.4)
  let sx = 1 - 0.006 * breathe
  let sy = 1 + 0.012 * breathe
  let x = 0
  let y = -3 * (0.5 + 0.5 * Math.sin((2 * Math.PI * clock) / 3.4 + 0.9))
  let rot = 0.6 * Math.sin((2 * Math.PI * clock) / 5.3)
  for (const b of beats) {
    if (!Number.isFinite(b.at)) continue
    const d = t - b.at
    if (d < -0.4 || d > 3) continue
    switch (b.kind) {
      case 'hop': {
        // crouch, spring up, land with a little squash
        const crouch = interpolate(d, [-0.12, 0, 0.05], [0, 1, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' })
        const air = d > 0.02 && d < 0.4 ? Math.sin((Math.PI * (d - 0.02)) / 0.38) : 0
        const land = interpolate(d, [0.38, 0.45, 0.6], [0, 1, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' })
        y -= 26 * air
        sy *= 1 - 0.05 * crouch - 0.05 * land + 0.04 * air
        sx *= 1 + 0.03 * crouch + 0.03 * land - 0.015 * air
        break
      }
      case 'lookL':
      case 'lookR': {
        const e = envelope(t, b.at, 0.35, 1.3, 0.5)
        const dir = b.kind === 'lookL' ? -1 : 1
        rot += dir * 5 * e
        x += dir * 6 * e
        break
      }
      case 'lookUp': {
        const e = envelope(t, b.at, 0.3, 1.2, 0.5)
        sy *= 1 + 0.035 * e
        y -= 5 * e
        break
      }
      case 'nod': {
        const k = d > 0 && d < 0.9 ? Math.abs(Math.sin((2 * Math.PI * d) / 0.9)) : 0
        sy *= 1 - 0.035 * k
        break
      }
      case 'droop': {
        const e = envelope(t, b.at, 0.4, 1.2, 0.6)
        sy *= 1 - 0.04 * e
        sx *= 1 + 0.015 * e
        rot += 2.5 * e
        break
      }
    }
  }
  return { x, y, rot, sx, sy }
}

/** The idle character: the keyed anchor still with procedural life (idlePose), so it never moves its mouth. */
export function IdleMascot({ plate, beats, clock, opacity = 1 }: { plate: Plate; beats: Beat[]; clock: number; opacity?: number }) {
  const t = useCurrentFrame() / FPS
  const u = plate.w / 1920 // px in the 1920-wide plate → canvas px
  const { x, y, rot, sx, sy } = idlePose(t, clock, beats)
  return (
    <Img
      src={staticFile('media/mascot/idle.png')}
      style={{
        position: 'absolute',
        left: plate.x,
        top: plate.y,
        width: plate.w,
        height: plate.h,
        opacity,
        transformOrigin: `${FEET.x * 100}% ${FEET.y * 100}%`,
        transform: `translate(${x * u}px, ${y * u}px) rotate(${rot}deg) scale(${sx}, ${sy})`,
      }}
    />
  )
}

/**
 * The intro walk-in (Kling intro_a) handed off to the idle still. intro_a's mouth
 * starts moving at source frame 78, right after it reaches its mark, so it is cut
 * at frame 76 (mouth closed, a blink) and cross-faded into the idle anchor, which
 * matches its position and size. `still` swaps in another idle (the guide cut's).
 */
export const WALK_IN = { clip: 'intro_a', cutAt: 76 / 24, fade: 6 }

export function WalkInMascot({ plate, beats, clockStart, still }: { plate: Plate; beats: Beat[]; clockStart: number; still?: (opacity: number) => ReactNode }) {
  const frame = useCurrentFrame()
  const cut = Math.round(WALK_IN.cutAt * FPS)
  const fade = interpolate(frame, [cut - WALK_IN.fade, cut], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' })
  return (
    <>
      <Sequence durationInFrames={cut} layout="none">
        <Video
          src={staticFile(`media/mascot/${WALK_IN.clip}.webm`)}
          muted
          style={{ position: 'absolute', left: plate.x, top: plate.y, width: plate.w, height: plate.h, opacity: 1 - fade }}
        />
      </Sequence>
      {frame >= cut - WALK_IN.fade && (still ? still(fade) : <IdleMascot plate={plate} beats={beats} clock={clockStart + frame / FPS} opacity={fade} />)}
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

/** A Spot's layout box on the composition (px, before its own pulse scale) and the cue times it lights up on. */
export interface SpotBox {
  x: number
  y: number
  w: number
  h: number
  cues: number[]
}

/**
 * Where the guide cut (src/guide.tsx) collects its targets: every Spot in the scene
 * reports its box here, measured against `root` (the composition-sized scene root).
 * Absent in the plain cuts, where Spots measure nothing.
 */
export interface SpotRegistry {
  root: RefObject<HTMLDivElement | null>
  report: (id: string, box: SpotBox) => void
}
export const SpotContext = createContext<SpotRegistry | null>(null)

/**
 * Reports the element's box to the guide cut's SpotContext (a no-op elsewhere). With
 * no cues it is UI the guide keeps clear of, not a target (useKeepClear).
 */
function useSpotBox(cue: number[]): RefObject<HTMLDivElement | null> {
  const registry = useContext(SpotContext)
  const ref = useRef<HTMLDivElement>(null)
  const id = useId()
  const cues = cue.filter(Number.isFinite)
  // Every render: the box moves with entrance transforms, and fonts can shift layout.
  // Studio scales the whole composition, so divide by the root's on-screen scale; the
  // centre is unaffected by a Spot's own pulse scale and offsetWidth ignores it.
  useLayoutEffect(() => {
    const el = ref.current
    const root = registry?.root.current
    if (!registry || !el || !root) return
    const r = root.getBoundingClientRect()
    const k = r.width / root.offsetWidth || 1
    const b = el.getBoundingClientRect()
    const cx = (b.left + b.width / 2 - r.left) / k
    const cy = (b.top + b.height / 2 - r.top) / k
    registry.report(id, { x: cx - el.offsetWidth / 2, y: cy - el.offsetHeight / 2, w: el.offsetWidth, h: el.offsetHeight, cues })
  })
  return ref
}

/** A ref for UI that is not a Spot but that the guide must not stand on (captions aside). */
export function useKeepClear(): RefObject<HTMLDivElement | null> {
  return useSpotBox([])
}

/** An invisible guide target for something the narration names that is not a Spot of its own (a band on a chart). */
export function CueMark({ cue, style }: { cue: number; style: CSSProperties }) {
  const ref = useSpotBox([cue])
  return <div ref={ref} style={{ position: 'absolute', ...style }} />
}

/**
 * A UI element the narrator is talking about: an accent ring while `on` is up.
 * `cue` (seconds into the scene, one or more) is when the narration names it; in the
 * guide cut the mascot travels to it then.
 */
export function Spot({ on, cue, style, radius = 18, children }: { on: number; cue?: number | number[]; style?: CSSProperties; radius?: number; children: ReactNode }) {
  const ref = useSpotBox(Array.isArray(cue) ? cue : cue === undefined ? [] : [cue])
  return (
    <div
      ref={ref}
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
