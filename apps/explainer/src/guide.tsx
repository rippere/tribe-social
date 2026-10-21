import { useCallback, useMemo, useRef, useState, type ReactNode } from 'react'
import { Easing, Img, interpolate, staticFile, useCurrentFrame } from 'remotion'
import { FEET, SpotContext, idlePose, type Beat, type Plate, type SpotBox, type SpotRegistry } from './mascot'
import { FPS } from './theme'

/*
 * The guide cut: instead of standing at one spot, the mascot travels to whatever Ben
 * is talking about, an attention guide one step ahead of the narration. Its targets
 * are the Spots the narration already cues (the accent rings): each Spot reports its
 * box and cue times to GuideStage, and the guide lands beside the element just
 * before its cue word. Still no new footage and still a closed mouth: it is the keyed
 * idle still (moved, squashed and leaned here) plus, for long level moves, a run
 * looped from the walk-in's own side-on step (scripts/run-frames.sh).
 *
 * Move by distance: short → shuffle, medium → hop, long and level → run, a big
 * change in height → jump. Each scene starts and ends on its home spot (the anchor's
 * feet; full size before the play scene's Kling shots), so cuts join without a jump.
 */
export const GUIDE = {
  /** Guide height as a fraction of the full-size anchor. */
  scale: 0.56,
  /** Lands this long (s) before the cue word. */
  lead: 0.15,
  /** A cue this soon (s) after the last one taken is skipped. */
  minGap: 0.6,
  /** Shortest stay (s) beside a target; a move that can't keep it is skipped. */
  minDwell: 0.35,
  /** Back home this long (s) before the scene cuts. */
  settle: 0.35,
  /** Clearance (px) between the guide and the element it points at. */
  gap: 16,
  /** Moves shorter than this (px) are a shuffle. */
  shuffleMax: 90,
  /** Level moves at least this long (in guide heights) are a run. */
  runMin: 1.5,
  /** A height change above this fraction of the guide's height is a jump. */
  jumpDy: 0.45,
  hop: { dur: 0.5, crouch: 0.12, height: 46 },
  jump: { dur: 0.62, crouch: 0.18, height: 90 },
  /** Run cycle playback vs the walk it comes from. */
  runRate: 1.75,
  /** Crossfade (s) between the still and the run cycle. */
  fade: 3 / FPS,
  /** Lean (degrees) toward the target while beside it. */
  lean: 6,
}

/*
 * The run cycle: intro_a source frames 49-55, one side-on step facing right. `cx` is
 * the head's centre in each frame (fraction of the plate width), `next` the same at
 * frame 56; drawing frame j with its head at the guide's x, and advancing x by the
 * clip's own head travel, keeps the feet planted.
 */
const RUN = { first: 49, cx: [0.1148, 0.1409, 0.1654, 0.1888, 0.2133, 0.2388, 0.2591], next: 0.2763 }
const STRIDE = RUN.next - RUN.cx[0]

/** The idle still's body around its feet, in plate px (scripts/key_mascot.py --still bounding box). */
const BODY = { left: 171, right: 177, height: 388 }

interface Box {
  x0: number
  y0: number
  x1: number
  y1: number
}

/** Where the guide stands: feet (canvas px), size vs the anchor, and which way it leans (-1 left, 1 right; up: looks up). */
export interface Stop {
  x: number
  y: number
  k: number
  look: number
  up: number
}

type Kind = 'shuffle' | 'hop' | 'jump' | 'run'
interface Leg {
  from: Stop
  to: Stop
  d: number
  a: number
  kind: Kind
}

/** The anchor's feet on the canvas, at size k. */
export function anchorStop(plate: Plate, k: number): Stop {
  return { x: plate.x + FEET.x * plate.w, y: plate.y + FEET.y * plate.h, k, look: 0, up: 0 }
}

/** Collects the scene's Spot boxes (SpotContext) and hands them to `children`. */
export function GuideStage({ children }: { children: (spots: SpotBox[]) => ReactNode }) {
  const root = useRef<HTMLDivElement>(null)
  const [spots, setSpots] = useState<Record<string, SpotBox>>({})
  const report = useCallback((id: string, b: SpotBox) => setSpots(prev => (same(prev[id], b) ? prev : { ...prev, [id]: b })), [])
  const registry = useMemo<SpotRegistry>(() => ({ root, report }), [report])
  return (
    <SpotContext.Provider value={registry}>
      <div ref={root} style={{ position: 'absolute', inset: 0 }}>
        {children(Object.values(spots))}
      </div>
    </SpotContext.Provider>
  )
}

function same(a: SpotBox | undefined, b: SpotBox): boolean {
  if (!a) return false
  const near = (p: number, q: number) => Math.abs(p - q) < 0.5
  return near(a.x, b.x) && near(a.y, b.y) && near(a.w, b.w) && near(a.h, b.h) && a.cues.join() === b.cues.join()
}

/** Scene geometry for the guide: where its body may go, what it must never cover, and its home spots. */
export interface GuideScene {
  plate: Plate
  /** The body stays inside this box (the scorer window, or the canvas). */
  area: Box
  /** Never covered: the caption block. */
  avoid: Box[]
  /** Scene time (s) the guide takes over (after the intro walk-in). */
  from: number
  /** Scene length (s). */
  end: number
  start: Stop
  /** Where it must be when the scene cuts; null stays put (the last scene). */
  home: Stop | null
}

const overlap = (a: Box, b: Box) => Math.max(0, Math.min(a.x1, b.x1) - Math.max(a.x0, b.x0)) * Math.max(0, Math.min(a.y1, b.y1) - Math.max(a.y0, b.y0))
const boxOf = (s: SpotBox): Box => ({ x0: s.x, y0: s.y, x1: s.x + s.w, y1: s.y + s.h })
const grow = (b: Box, p: number): Box => ({ x0: b.x0 - p, y0: b.y0 - p, x1: b.x1 + p, y1: b.y1 + p })

function bodyAt(x: number, y: number, k: number, u: number): Box {
  return { x0: x - BODY.left * u * k, y0: y - BODY.height * u * k, x1: x + BODY.right * u * k, y1: y }
}

/**
 * A resting spot beside target `r`: to its side with feet on its bottom edge, perched
 * on its top edge, under it, or on the floor below it. Each must stay inside the
 * area, clear of the captions and the target; the cheapest wins (preference, other
 * UI covered, distance from the target, length of the move).
 */
function place(r: SpotBox, others: SpotBox[], cur: Stop, g: GuideScene): Stop | null {
  const u = g.plate.w / 1920
  const k = GUIDE.scale
  const hw = ((BODY.left + BODY.right) / 2) * u * k
  const h = BODY.height * u * k
  const R = boxOf(r)
  const cx = (R.x0 + R.x1) / 2
  const floor = anchorStop(g.plate, k).y
  const under = [cx, R.x0 + hw, R.x1 - hw]
  // On the floor it may also stay where it is, or step just clear of the captions.
  const ground = [...under, cur.x, ...g.avoid.flatMap(a => [a.x1 + BODY.left * u * k + 2, a.x0 - BODY.right * u * k - 2])]
  const cands: [number, number, number][] = [
    [R.x1 + GUIDE.gap + hw, R.y1, 0],
    [R.x0 - GUIDE.gap - hw, R.y1, 0],
    [R.x1 - hw - 8, R.y0, 1],
    [R.x0 + hw + 8, R.y0, 1],
    ...under.map((x): [number, number, number] => [x, R.y1 + GUIDE.gap + h, 1.5]),
    ...(floor - h > R.y1 + GUIDE.gap ? ground.map((x): [number, number, number] => [x, floor, 2]) : []),
    // standing on the caption block, when the UI leaves a strip above it
    ...g.avoid.flatMap(a => (a.y0 - h > R.y1 ? under.map((x): [number, number, number] => [x, a.y0 - 2, 1.8]) : [])),
  ]
  let best: { stop: Stop; cost: number } | null = null
  for (const [x0, y, pref] of cands) {
    const x = Math.min(Math.max(x0, g.area.x0 + BODY.left * u * k), g.area.x1 - BODY.right * u * k)
    const b = bodyAt(x, y, k, u)
    if (b.y0 < g.area.y0 || b.y1 > g.area.y1 + 1) continue
    if (g.avoid.some(a => overlap(a, b) > 0) || overlap(grow(R, 6), b) > 0) continue
    const covered = others.reduce((n, o) => n + overlap(boxOf(o), b), 0) / ((b.x1 - b.x0) * (b.y1 - b.y0))
    const near = Math.hypot(Math.max(0, R.x0 - b.x1, b.x0 - R.x1), Math.max(0, R.y0 - b.y1, b.y0 - R.y1))
    // Covering other UI is worst; then distance from the target and being off its axis; a long move costs a little.
    const off = Math.max(0, Math.abs(x - cx) - (R.x1 - R.x0) / 2)
    const cost = pref * 120 + covered * 6000 + 0.6 * near + 0.4 * off + 0.05 * Math.hypot(x - cur.x, y - cur.y)
    if (best && best.cost <= cost) continue
    const look = Math.abs(cx - x) > hw * 0.6 ? Math.sign(cx - x) : 0
    best = { stop: { x, y, k, look, up: R.y1 < b.y0 + 4 ? 1 : 0 }, cost }
  }
  return best?.stop ?? null
}

/** Full-size natural run speed (px/s at scale k on a plate of u px per plate px). */
function runSpeed(u: number, k: number): number {
  return (STRIDE * 1920 * u * k * 24 * GUIDE.runRate) / RUN.cx.length
}

function legFor(a: Stop, b: Stop, u: number): { kind: Kind; dur: number } {
  const dx = b.x - a.x
  const dy = b.y - a.y
  const dist = Math.hypot(dx, dy)
  const h = BODY.height * u * Math.max(a.k, b.k)
  if (dist < GUIDE.shuffleMax) return { kind: 'shuffle', dur: 0.4 }
  if (Math.abs(dy) > GUIDE.jumpDy * h) return { kind: 'jump', dur: GUIDE.jump.dur + 0.2 * Math.min(1, dist / 900) }
  if (Math.abs(dx) >= GUIDE.runMin * h) return { kind: 'run', dur: dist / runSpeed(u, (a.k + b.k) / 2) }
  return { kind: 'hop', dur: GUIDE.hop.dur + 0.1 * Math.min(1, dist / 400) }
}

/**
 * The scene's moves. A target is the most recently cued Spot; the guide leaves early
 * enough to land GUIDE.lead before the cue. Cues too close to the last one, repeats
 * of the current target, and moves that would leave less than GUIDE.minDwell beside
 * the last target are skipped; a move that is merely late is compressed (to 85 % of its length at most).
 */
function schedule(spots: SpotBox[], g: GuideScene): Leg[] {
  const u = g.plate.w / 1920
  const events = spots
    .flatMap(s => s.cues.map(t => ({ t, s })))
    .filter(e => e.t >= g.from + 0.4 && e.t < g.end)
    .sort((p, q) => p.t - q.t || p.s.x - q.s.x)
  const legs: Leg[] = []
  let cur = g.start
  let free = g.from
  let last = -Infinity
  let at: SpotBox | null = null
  for (const e of events) {
    if (e.t - last < GUIDE.minGap) continue
    if (e.s === at) {
      last = e.t
      continue
    }
    const to = place(
      e.s,
      spots.filter(s => s !== e.s),
      cur,
      g,
    )
    if (!to) continue
    const { kind, dur } = legFor(cur, to, u)
    const a = e.t - GUIDE.lead
    let d = a - dur
    if (d < free) {
      if (a - free < dur * 0.85) continue
      d = free
    }
    legs.push({ from: cur, to, d, a, kind })
    cur = to
    free = a + GUIDE.minDwell
    last = e.t
    at = e.s
  }
  const home = g.home
  if (home && Math.hypot(home.x - cur.x, home.y - cur.y) + Math.abs(home.k - cur.k) * 100 > 0.5) {
    const { kind, dur } = legFor(cur, home, u)
    let a = g.end - GUIDE.settle
    let d = a - dur
    if (d < free) {
      d = Math.max(free - GUIDE.minDwell + 0.15, d)
      a = Math.min(g.end - 2 / FPS, d + dur)
    }
    legs.push({ from: cur, to: home, d, a, kind })
  }
  return legs
}

const lerp = (p: number, q: number, f: number) => p + (q - p) * f
const ease = Easing.inOut(Easing.sin)

interface Frame {
  x: number
  y: number
  k: number
  rot: number
  sx: number
  sy: number
  /** The ground under it (canvas y): where its contact shadow sits while it is in the air. */
  gy: number
  /** Run cycle: facing (1 right, -1 left), source frame, and its weight against the still. */
  run: { dir: number; frame: number; mix: number } | null
}

/** Where the guide is and how it is deformed at scene time t. */
function frameAt(t: number, legs: Leg[], start: Stop, u: number): Frame {
  let i = -1
  for (let j = 0; j < legs.length; j++) if (legs[j].d <= t) i = j
  const leg = legs[i]
  const rest = (s: Stop, since: number, until: number): Frame => {
    // settle into a lean toward the target after landing, straighten before leaving
    const e = Math.min(interpolate(t - since, [0.12, 0.45], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: ease }), interpolate(until - t, [0, 0.2], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' }))
    return { x: s.x + s.look * 6 * u * s.k * e, y: s.y - 4 * u * s.k * e * s.up, gy: s.y, k: s.k, rot: s.look * GUIDE.lean * e, sx: 1, sy: 1 + 0.03 * e * s.up, run: null }
  }
  if (!leg) return rest(start, -Infinity, legs[0]?.d ?? Infinity)
  const { from: A, to: B, d, a } = leg
  const dir = Math.sign(B.x - A.x) || 1
  if (t >= a) {
    const f = rest(B, a, legs[i + 1]?.d ?? Infinity)
    if (leg.kind === 'hop' || leg.kind === 'jump') {
      const land = interpolate(t - a, [0, 0.06, 0.24], [0, 1, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' })
      const amt = leg.kind === 'jump' ? 0.12 : 0.07
      f.sy *= 1 - amt * land
      f.sx *= 1 + amt * 0.6 * land
    }
    return f
  }
  const p = (t - d) / (a - d)
  const k = lerp(A.k, B.k, ease(p))
  switch (leg.kind) {
    case 'shuffle': {
      const e = ease(p)
      return { x: lerp(A.x, B.x, e), y: lerp(A.y, B.y, e) - 6 * u * k * Math.abs(Math.sin(2 * Math.PI * p)), gy: lerp(A.y, B.y, e), k, rot: dir * 4 * Math.sin(Math.PI * p), sx: 1, sy: 1, run: null }
    }
    case 'hop':
    case 'jump': {
      const spec = leg.kind === 'jump' ? GUIDE.jump : GUIDE.hop
      const c = Math.min(spec.crouch, 0.3 * (a - d))
      const amt = leg.kind === 'jump' ? 0.14 : 0.08
      if (t - d < c) {
        const q = Math.sin(((t - d) / c) * (Math.PI / 2))
        return { x: A.x, y: A.y, gy: A.y, k, rot: -dir * 2 * q, sx: 1 + amt * 0.6 * q, sy: 1 - amt * q, run: null }
      }
      const q = (t - d - c) / (a - d - c)
      const dist = Math.hypot(B.x - A.x, B.y - A.y)
      const lift = spec.height * u + 0.1 * dist + 0.6 * Math.max(0, A.y - B.y)
      const s = Math.sin(Math.PI * q)
      const stretch = leg.kind === 'jump' ? 0.1 : 0.06
      return { x: lerp(A.x, B.x, q), y: lerp(A.y, B.y, q) - lift * 4 * q * (1 - q), gy: lerp(A.y, B.y, q), k, rot: dir * (leg.kind === 'jump' ? 10 : 6) * s, sx: 1 - stretch * 0.5 * s, sy: 1 + stretch * s, run: null }
    }
    case 'run': {
      // Advance by the clip's own head travel per source frame, scaled to land exactly on B.
      // `total` source frames cover the move at the natural stride (more if the move was compressed).
      const kk = (A.k + B.k) / 2
      const total = Math.max(1, Math.floor(Math.hypot(B.x - A.x, B.y - A.y) / ((STRIDE / RUN.cx.length) * 1920 * u * kk)))
      const travel = (n: number) => Math.floor(n / RUN.cx.length) * STRIDE + RUN.cx[n % RUN.cx.length] - RUN.cx[0]
      const step = Math.min(total, Math.floor(p * total))
      const j = step % RUN.cx.length
      const f = travel(step) / travel(total)
      const mix = Math.min(1, (t - d) / GUIDE.fade, (a - t) / GUIDE.fade)
      return { x: lerp(A.x, B.x, f), y: lerp(A.y, B.y, f), gy: lerp(A.y, B.y, f), k, rot: 0, sx: 1, sy: 1, run: { dir, frame: RUN.first + j, mix: Math.max(0, mix) } }
    }
  }
}

/**
 * The guide itself. `beats` are the plain cut's cue-word beats; only the ones that
 * still read with a moving guide are kept (hop, nod, droop: the leans are its
 * travel now), and a hop is dropped where the guide has just landed anyway.
 */
export function GuideMascot({ spots, scene, beats, clock, opacity = 1 }: { spots: SpotBox[]; scene: GuideScene; beats: Beat[]; clock: number; opacity?: number }) {
  const t = useCurrentFrame() / FPS
  const u = scene.plate.w / 1920
  const legs = useMemo(() => schedule(spots, scene), [spots, scene])
  const kept = beats.filter(
    b => (b.kind === 'hop' || b.kind === 'nod' || b.kind === 'droop') && !legs.some(l => b.at >= l.d - 0.1 && b.at <= l.a + (b.kind === 'hop' && l.kind !== 'shuffle' ? 0.45 : 0)),
  )
  const f = frameAt(t, legs, scene.start, u)
  const pose = idlePose(t, clock, kept)
  const s = f.k * u
  const still = f.run ? 1 - f.run.mix : 1
  // A soft contact shadow so it stands on the UI rather than floating; it fades as the guide leaves the ground.
  const shadow = 1 - Math.min(1, (f.gy - f.y) / (160 * s))
  return (
    <>
      <div
        style={{
          position: 'absolute',
          left: f.x - 150 * s,
          top: f.gy - 14 * s,
          width: 300 * s,
          height: 28 * s,
          borderRadius: '50%',
          opacity: opacity * 0.55 * shadow,
          background: 'radial-gradient(closest-side, rgba(0,0,0,0.9), rgba(0,0,0,0))',
        }}
      />
      {still > 0 && (
        <div
          style={{
            position: 'absolute',
            left: 0,
            top: 0,
            opacity: opacity * still,
            transformOrigin: '0 0',
            transform: `translate(${f.x + pose.x * s}px, ${f.y + pose.y * s}px) rotate(${pose.rot + f.rot}deg) scale(${s * pose.sx * f.sx}, ${s * pose.sy * f.sy})`,
          }}
        >
          <Img src={staticFile('media/mascot/idle.png')} style={{ position: 'absolute', left: -FEET.x * 1920, top: -FEET.y * 1080, width: 1920, height: 1080, maxWidth: 'none' }} />
        </div>
      )}
      {f.run && f.run.mix > 0 && (
        <div
          style={{
            position: 'absolute',
            left: 0,
            top: 0,
            opacity: opacity * f.run.mix,
            transformOrigin: '0 0',
            transform: `translate(${f.x}px, ${f.y}px) rotate(${f.run.dir * 3}deg) scale(${f.run.dir * s}, ${s})`,
          }}
        >
          <Img
            src={staticFile(`media/mascot/run/${String(f.run.frame).padStart(3, '0')}.png`)}
            style={{ position: 'absolute', left: -RUN.cx[f.run.frame - RUN.first] * 1920, top: -FEET.y * 1080, width: 1920, height: 1080, maxWidth: 'none' }}
          />
        </div>
      )}
    </>
  )
}
