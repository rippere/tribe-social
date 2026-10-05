import type { CSSProperties, ReactNode } from 'react'
import { Audio, Video } from '@remotion/media'
import { AbsoluteFill, Freeze, Sequence, interpolate, staticFile, useCurrentFrame } from 'remotion'
import { AppWindow, Phone, ResponseChart, Tag, fadeIn, type Stage, type Word } from './components'
import { Cortex, useCortexAssets, type CortexAssets } from './cortex'
import { Captions, MascotLayer, Spot, cue, cutsFor, cutsLength, lit, pulse, type Cut, type Plate } from './mascot'
import { C, FONT, FPS, MONO } from './theme'
import narration from './data/narration.json'
import result from './data/result.json'

export type Orientation = 'landscape' | 'portrait'

type Talk = keyof typeof narration
const STIM_SECONDS = 24.03
const STIM_FRAMES = Math.floor(STIM_SECONDS * FPS)

type SceneKey = 'intro' | 'upload' | 'encode' | 'extract' | 'read' | 'play' | 'cta'

/*
 * One talking shot per sentence (or two), played at its natural speed with its own
 * audio slice from the shot's first frame, so the mouth and every gesture land on
 * their words. The scorer UI around the standing character is laid out in three
 * targets (up-left, straight up, up-right) and each shot's prompt points at one of
 * them on the word that names it; the accent ring is cued from the same word.
 */
interface SceneSpec {
  key: SceneKey
  shots: { clip: string; at?: number }[]
}

// The watching scene pins its reactions to the result: the excited lean in play_d
// starts 1.9 s into the shot, landing just after the peak (0:16) on the plateau;
// play_e frowns from 0.5 s and stands up and walks off at ~2.4 s, over the decline
// into the biggest drop (0:23).
const SPECS: SceneSpec[] = [
  { key: 'intro', shots: [{ clip: 'intro_a' }, { clip: 't_intro' }] },
  { key: 'upload', shots: [{ clip: 't_upload' }] },
  { key: 'encode', shots: [{ clip: 't_enc1' }, { clip: 't_enc2' }] },
  { key: 'extract', shots: [{ clip: 't_extract' }] },
  { key: 'read', shots: [{ clip: 't_read1' }, { clip: 't_read2' }] },
  {
    key: 'play',
    shots: [{ clip: 'play_a' }, { clip: 'play_b' }, { clip: 'play_c', at: 10.02 }, { clip: 'play_d', at: result.peak.second - 1 }, { clip: 'play_e', at: result.peak.second + 4.04 }],
  },
  { key: 'cta', shots: [{ clip: 't_outro' }] },
]

interface Scene extends SceneSpec {
  frames: number
  words: Word[]
  cuts: Cut[]
  talks: { clip: Talk; from: number }[]
}

const SCENES: Scene[] = SPECS.map(s => {
  const cuts = cutsFor(s.shots)
  for (const c of cuts) {
    if (c.clip.startsWith('t_') && !(c.clip in narration)) throw new Error(`Talking shot "${c.clip}" has no narration: run scripts/build_data.py`)
  }
  const talks = cuts.filter(c => c.clip in narration).map(c => ({ clip: c.clip as Talk, from: c.from }))
  const words = talks.flatMap(k => (narration[k.clip].words as Word[]).map(w => ({ ...w, s: w.s + k.from / FPS, e: w.e + k.from / FPS })))
  return { ...s, cuts, talks, words, frames: cutsLength(cuts) }
})

export function explainerDuration(): number {
  return SCENES.reduce((n, s) => n + s.frames, 0)
}

const HAS_RESULT = result.source === 'tribe' && result.relative.length > 1
const WINDOW_SCENES: Partial<Record<SceneKey, Stage>> = { upload: 'upload', encode: 'encode', extract: 'extract', read: 'read', play: 'read' }

/* ---------- layout ---------- */

type R = [number, number, number, number]

interface Layout {
  W: number
  H: number
  portrait: boolean
  /** Scorer window on the canvas. */
  win: { x: number; y: number; w: number; h: number }
  plate: Plate
}

/*
 * Where the standing character points, in window-body coordinates. Landscape: the
 * character stands at canvas x 960 with its head at y ~640, so targets centred near
 * body x 375 / 935 / 1510 read as up-left / straight up / up-right. Portrait: the
 * same three directions map to a row of cards just above the caption band.
 */
function layout(o: Orientation): Layout {
  if (o === 'landscape') {
    return { W: 1920, H: 1080, portrait: false, win: { x: 24, y: 24, w: 1872, h: 1032 }, plate: { x: 0, y: 0, w: 1920, h: 1080 } }
  }
  return { W: 1080, H: 1920, portrait: true, win: { x: 20, y: 20, w: 1040, h: 1880 }, plate: { x: -276, y: 1920 - 918 - 30, w: 1632, h: 918 } }
}

/** A box in window-body coordinates, one rect per orientation. */
function at(L: Layout, land: R, port: R, extra?: CSSProperties): CSSProperties {
  const [left, top, width, height] = L.portrait ? port : land
  return { position: 'absolute', left, top, width, height, ...extra }
}

/* ---------- composition ---------- */

export function Explainer({ orientation }: { orientation: Orientation }) {
  const L = layout(orientation)
  const cortex = useCortexAssets()
  let from = 0
  return (
    <AbsoluteFill style={{ background: C.bg, fontFamily: FONT, color: C.ink }}>
      {SCENES.map(s => {
        const start = from
        from += s.frames
        return (
          <Sequence key={s.key} from={start} durationInFrames={s.frames} name={s.key}>
            {s.talks.map(k => (
              <Sequence key={k.clip} from={k.from} layout="none">
                <Audio src={staticFile(`media/narration/${k.clip}.mp3`)} />
              </Sequence>
            ))}
            <SceneFrame scene={s} L={L} cortex={cortex} first={s.key === 'upload'} />
          </Sequence>
        )
      })}
    </AbsoluteFill>
  )
}

function SceneFrame({ scene, L, cortex, first }: { scene: Scene; L: Layout; cortex: CortexAssets | null; first: boolean }) {
  const frame = useCurrentFrame()
  const t = frame / FPS
  const stage = WINDOW_SCENES[scene.key]
  const content = <SceneBody scene={scene} L={L} cortex={cortex} t={t} />
  return (
    <AbsoluteFill>
      {stage ? (
        <div
          style={{
            position: 'absolute',
            left: L.win.x,
            top: L.win.y,
            opacity: first ? fadeIn(frame, 0, 14) : 1,
            transform: first ? `translateY(${(1 - fadeIn(frame, 0, 14)) * 24}px)` : undefined,
          }}
        >
          <AppWindow stage={stage} width={L.win.w} height={L.win.h}>
            <div style={{ position: 'absolute', inset: 0, opacity: fadeIn(frame, 0, 10) }}>{content}</div>
          </AppWindow>
        </div>
      ) : (
        content
      )}
      <MascotLayer cuts={scene.cuts} plate={L.plate} />
      <Captions words={scene.words} t={t} portrait={L.portrait} />
    </AbsoluteFill>
  )
}

function SceneBody({ scene, L, cortex, t }: { scene: Scene; L: Layout; cortex: CortexAssets | null; t: number }) {
  const w = scene.words
  switch (scene.key) {
    case 'intro':
      return <Intro L={L} w={w} t={t} />
    case 'upload':
      return <UploadPane L={L} w={w} t={t} />
    case 'encode':
      return <EncodePane L={L} w={w} t={t} />
    case 'extract':
      return <ExtractPane L={L} w={w} t={t} cortex={cortex} />
    case 'read':
      return <ReadPane L={L} w={w} t={t} cortex={cortex} />
    case 'play':
      return <PlayPane L={L} t={t} cortex={cortex} />
    case 'cta':
      return <Cta L={L} w={w} t={t} />
  }
}

/* ---------- shared pieces ---------- */

const card: CSSProperties = { background: C.panel, border: `1px solid ${C.line}`, borderRadius: 18, padding: 26, boxSizing: 'border-box' }
const label: CSSProperties = { fontFamily: MONO, fontSize: 16, color: C.muted, letterSpacing: 0.4, textTransform: 'uppercase' }

function Stim({ trim = 0 }: { trim?: number }) {
  return <Video src={staticFile('media/stimulus.mp4')} muted trimBefore={trim} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
}

function CortexBox({ cortex, t, w: width, h: height, rotation }: { cortex: CortexAssets | null; t: number; w: number; h: number; rotation: number }) {
  // ThreeCanvas rejects fractional sizes.
  const w = Math.round(width)
  const h = Math.round(height)
  if (!cortex) return <div style={{ width: w, height: h }} />
  return (
    <div style={{ position: 'relative', width: w, height: h }}>
      <Cortex assets={cortex} t={t} rotation={rotation} width={w} height={h} />
      <div style={{ position: 'absolute', left: 14, bottom: 14 }}>
        {cortex.activity ? <Tag tone="accent">TRIBE v2 output · fsaverage cortex</Tag> : <Tag tone="amber">Awaiting model output · no activity shown</Tag>}
      </div>
    </div>
  )
}

/* ---------- intro: walks in, introduces itself, points up at the name ---------- */

function Intro({ L, w, t }: { L: Layout; w: Word[]; t: number }) {
  const give = cue(w, /^Give/)
  const name = cue(w, /^Eff/)
  return (
    <AbsoluteFill style={{ alignItems: 'center', paddingTop: L.portrait ? 360 : 150 }}>
      <Spot on={pulse(t, name, 2.2)} radius={28} style={{ padding: '18px 44px', textAlign: 'center', opacity: interpolate(t, [0.3, 1, name - 0.1, name + 0.2], [0, 0.22, 0.22, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' }) }}>
        <div style={{ fontSize: L.portrait ? 132 : 150, fontWeight: 500, letterSpacing: -4, lineHeight: 1 }}>fMRIght</div>
      </Spot>
      <div style={{ marginTop: 24, fontSize: L.portrait ? 38 : 40, color: C.muted, maxWidth: 860, lineHeight: 1.3, textAlign: 'center', opacity: lit(t, give, 0.5) }}>
        A predicted brain response to your video, second by second.
      </div>
    </AbsoluteFill>
  )
}

/* ---------- upload: your clip (up-left) → rented GPU (up) → video dropped, scores kept (up-right) ---------- */

function UploadPane({ L, w, t }: { L: Layout; w: Word[]; t: number }) {
  const up = cue(w, /^upload/)
  const gpu = cue(w, /^graphics/)
  const del = cue(w, /^delete/)
  const scores = cue(w, /^scores/)
  const p = interpolate(t, [up + 0.3, gpu + 1.4], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' })
  const gone = lit(t, del + 0.3)
  const status = p <= 0 ? 'Ready to send' : p < 1 ? `Sending to the GPU… ${Math.round(p * 100)}%` : 'Delivered'
  return (
    <>
      {L.portrait && (
        <div style={at(L, [0, 0, 0, 0], [340, 30, 360, 640], { opacity: 1 - 0.75 * gone })}>
          <Phone width={360}>
            <Stim />
          </Phone>
        </div>
      )}
      <Spot on={pulse(t, up, 2)} style={at(L, [40, 120, 640, 340], [30, 700, 315, 420], card)}>
        <div style={{ display: 'flex', gap: 28, height: '100%' }}>
          {!L.portrait && (
            <div style={{ opacity: 1 - 0.75 * gone }}>
              <Phone width={150}>
                <Stim />
              </Phone>
            </div>
          )}
          <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
            <span style={label}>Your clip</span>
            <div style={{ fontSize: L.portrait ? 21 : 30, fontWeight: 500, marginTop: 10, whiteSpace: 'nowrap' }}>mac_and_cheese.mp4</div>
            <div style={{ fontSize: 18, color: C.muted, marginTop: 8, fontFamily: MONO }}>0:24 · 9:16</div>
            <div style={{ marginTop: 24, height: 12, borderRadius: 6, background: C.fill, overflow: 'hidden' }}>
              <div style={{ width: `${p * 100}%`, height: '100%', background: C.accent }} />
            </div>
            <div style={{ marginTop: 12, fontSize: 17, color: C.muted, fontFamily: MONO }}>{status}</div>
          </div>
        </div>
      </Spot>
      <Arrow L={L} p={p} />
      <Spot on={pulse(t, gpu, 2.2)} style={at(L, [755, 120, 360, 340], [365, 700, 315, 420], { ...card, display: 'flex', flexDirection: 'column', justifyContent: 'center', gap: 14 })}>
        <span style={label}>Rented cloud GPU</span>
        <div style={{ fontSize: 34, fontWeight: 500 }}>NVIDIA A100</div>
        <div style={{ fontFamily: MONO, fontSize: 17, color: C.muted }}>80 GB · billed by the second</div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, fontFamily: MONO, fontSize: 17, color: p >= 1 ? C.accent : C.muted }}>
          <span style={{ width: 10, height: 10, borderRadius: 5, background: p >= 1 ? C.accent : '#3a3a39' }} />
          {p <= 0 ? 'idle' : p < 1 ? 'receiving' : 'running TRIBE v2'}
        </div>
      </Spot>
      <div style={at(L, [1185, 120, 650, 340], [700, 700, 310, 420], { display: 'flex', flexDirection: 'column', gap: 20 })}>
        <Spot on={pulse(t, del, 1.6)} style={{ ...card, flex: 1, padding: '0 24px', display: 'flex', alignItems: 'center', gap: 14, fontSize: L.portrait ? 21 : 24 }}>
          <span style={{ fontFamily: MONO, fontSize: 28, color: gone > 0.5 ? C.ink : C.muted }}>{gone > 0.5 ? '✕' : '·'}</span>
          <span>
            Video <span style={{ color: C.muted }}>· deleted after scoring</span>
          </span>
        </Spot>
        <Spot on={pulse(t, scores, 1.8)} style={{ ...card, flex: 1, padding: '0 24px', display: 'flex', alignItems: 'center', gap: 14, fontSize: L.portrait ? 21 : 24 }}>
          <span style={{ fontFamily: MONO, fontSize: 28, color: lit(t, scores) > 0.5 ? C.accent : C.muted }}>✓</span>
          <span>
            Scores <span style={{ color: C.muted }}>· kept</span>
          </span>
        </Spot>
      </div>
    </>
  )
}

function Arrow({ L, p }: { L: Layout; p: number }) {
  // card → GPU, to the right in both layouts
  const [x, y, len] = L.portrait ? [338, 910, 0] : [690, 290, 40]
  if (!len) return null
  const dot = p > 0 && p < 1 ? (p * 3) % 1 : -1
  return (
    <svg style={{ position: 'absolute', left: x, top: y - 30, overflow: 'visible' }} width={60} height={60}>
      <g transform="translate(0 30)">
        <line x1={0} x2={len} y1={0} y2={0} stroke={p > 0 ? C.accent : C.line} strokeWidth={3} strokeDasharray="6 6" />
        <path d={`M${len} -8 L${len + 12} 0 L${len} 8 Z`} fill={p > 0 ? C.accent : C.line} />
        {dot >= 0 && <circle cx={dot * len} cy={0} r={5} fill={C.accent} />}
      </g>
    </svg>
  )
}

/* ---------- encode: frames (up-left), audio (up), words (up-right) → TRIBE v2; no scanner (up-right) ---------- */

function EncodePane({ L, w, t }: { L: Layout; w: Word[]; t: number }) {
  const frame = useCurrentFrame()
  const at3 = [cue(w, /^frames/), cue(w, /^audio/), cue(w, /^words/)]
  const model = cue(w, /^Meta/)
  const learned = cue(w, /^learned/)
  const scanner = cue(w, /^without/)
  const bars = Array.from({ length: L.portrait ? 14 : 28 }, (_, i) => 0.25 + 0.75 * Math.abs(Math.sin(i * 1.7 + frame * 0.21) * Math.cos(i * 0.6 + frame * 0.09)))
  const channel = (i: number, title: string, land: R, port: R, body: ReactNode) => (
    <Spot on={pulse(t, at3[i], 1.5)} style={at(L, land, port, { ...card, display: 'flex', flexDirection: 'column', gap: 14, overflow: 'hidden', padding: L.portrait ? 18 : 24 })}>
      <span style={{ ...label, color: lit(t, at3[i]) > 0.5 ? C.accent : C.muted }}>{title}</span>
      <div style={{ flex: 1, minHeight: 0, opacity: 0.35 + 0.65 * lit(t, at3[i]) }}>{body}</div>
    </Spot>
  )
  return (
    <>
      {channel(
        0,
        'Frames',
        [40, 60, 560, 260],
        [30, 700, 315, 420],
        <div style={{ display: 'grid', gridTemplateColumns: L.portrait ? '1fr 1fr' : '1fr 1fr 1fr 1fr', gap: 8, height: '100%' }}>
          {[2, 8, 14, 20].map(s => (
            <div key={s} style={{ borderRadius: 8, overflow: 'hidden', background: '#000', minHeight: 0 }}>
              <Stim trim={s * FPS} />
            </div>
          ))}
        </div>,
      )}
      {channel(
        1,
        'Audio',
        [655, 60, 560, 260],
        [365, 700, 315, 420],
        <div style={{ display: 'flex', alignItems: 'center', gap: 5, height: '100%' }}>
          {bars.map((b, i) => (
            <div key={i} style={{ flex: 1, height: `${b * 100}%`, borderRadius: 3, background: C.accent }} />
          ))}
        </div>,
      )}
      {channel(
        2,
        'Words',
        [1270, 60, 565, 260],
        [700, 700, 310, 420],
        <div style={{ fontSize: L.portrait ? 21 : 24, lineHeight: 1.45, color: C.ink }}>
          “…for about a full minute. Okay, yeah.”
          <div style={{ marginTop: 8, fontFamily: MONO, fontSize: 15, color: C.muted }}>transcript, word-timed</div>
        </div>,
      )}
      <Spot on={Math.max(pulse(t, model, 1.6), pulse(t, learned, 2.6))} style={at(L, [40, 345, 1175, 150], [30, 30, 980, 300], { ...card, display: 'flex', flexDirection: 'column', justifyContent: 'center', gap: 10 })}>
        <span style={label}>The model</span>
        <div style={{ fontSize: L.portrait ? 44 : 34, fontWeight: 500 }}>TRIBE v2 · Meta FAIR</div>
        <div style={{ fontSize: L.portrait ? 24 : 20, color: C.muted }}>Trained on fMRI scans of people watching video.</div>
      </Spot>
      <Spot on={pulse(t, scanner, 2)} style={at(L, [1270, 345, 565, 150], [30, 360, 980, 300], { ...card, display: 'flex', flexDirection: 'column', justifyContent: 'center', gap: 10 })}>
        <span style={{ ...label, color: lit(t, scanner) > 0.5 ? C.accent : C.muted }}>No scanner involved</span>
        <div style={{ fontSize: L.portrait ? 24 : 20, color: C.muted, lineHeight: 1.4 }}>It predicts the response from the video file alone.</div>
      </Spot>
    </>
  )
}

/* ---------- extract: ~20k points (up-left), the cortex (up), one per second (up-right) ---------- */

function ExtractPane({ L, w, t, cortex }: { L: Layout; w: Word[]; t: number; cortex: CortexAssets | null }) {
  const out = cue(w, /^Out/)
  const pts = cue(w, /^twenty/)
  const fps1 = cue(w, /^every/)
  const glow = cue(w, /^lighting/)
  const n = Math.round(interpolate(t, [pts - 0.1, pts + 1.3], [0, 20484], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' }))
  const ticks = Math.floor(interpolate(t, [fps1, fps1 + 1.8], [0, 24], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' }))
  const [cw, ch] = L.portrait ? [980, 640] : [700, 480]
  return (
    <>
      <Spot on={pulse(t, pts, 2.2)} style={at(L, [40, 160, 540, 290], [30, 700, 470, 420], { ...card, display: 'flex', flexDirection: 'column', justifyContent: 'center', gap: 8 })}>
        <span style={label}>Points predicted</span>
        <div style={{ fontFamily: MONO, fontSize: 64, fontVariantNumeric: 'tabular-nums' }}>{n.toLocaleString('en-US')}</div>
        <div style={{ fontSize: 19, color: C.muted }}>across the cortex surface</div>
      </Spot>
      <Spot on={Math.max(pulse(t, out, 1.2), pulse(t, glow, 2.2))} radius={22} style={at(L, [585, 0, cw, ch], [30, 20, cw, ch])}>
        <CortexBox cortex={cortex} t={t % 24} w={cw} h={ch} rotation={Math.PI / 2 + t * 0.12} />
      </Spot>
      <Spot on={pulse(t, fps1, 2.4)} style={at(L, [1295, 160, 540, 290], [540, 700, 470, 420], { ...card, display: 'flex', flexDirection: 'column', justifyContent: 'center', gap: 14 })}>
        <span style={label}>One per second</span>
        <div style={{ display: 'flex', gap: 4 }}>
          {Array.from({ length: 24 }, (_, i) => (
            <div key={i} style={{ flex: 1, height: 34, borderRadius: 3, background: i < ticks ? C.accent : C.fill }} />
          ))}
        </div>
        <div style={{ fontFamily: MONO, fontSize: 18, color: C.muted }}>{ticks} / 24 s of video</div>
      </Spot>
    </>
  )
}

/* ---------- read: the clip (up-left), the line (up, swept left→right), warm-up (up-left), climb (up), dip (up-right) ---------- */

function ReadPane({ L, w, t, cortex }: { L: Layout; w: Word[]; t: number; cortex: CortexAssets | null }) {
  const real = cue(w, /^real/)
  const line = cue(w, /^line/)
  const done = cue(w, /^second\.$/)
  const ignore = cue(w, /^Ignore/)
  const climbs = cue(w, /^climbs/)
  const dips = cue(w, /^dips/)
  const upTo = interpolate(t, [line, done + 0.4], [0, result.relative.length - 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' })
  const bands = HAS_RESULT
    ? [
        { from: 0, to: result.warmup_seconds, on: pulse(t, ignore, 3.6), label: 'ignore: the signal lags' },
        { from: Math.max(result.warmup_seconds, result.peak.second - 4), to: result.peak.second, on: lit(t, climbs, 0.35), label: '▲ climbs' },
        { from: result.drop.second - 1, to: result.drop.second, on: lit(t, dips, 0.35), label: '▼ dips' },
      ]
    : []
  const [chartW, chartH] = L.portrait ? [980, 440] : [1535, 440]
  return (
    <>
      <Spot on={pulse(t, real, 2)} style={at(L, [40, 20, 230, 450], [30, 20, 300, 560])}>
        <Phone width={L.portrait ? 300 : 230}>
          <Stim />
        </Phone>
        <div style={{ marginTop: 10, fontFamily: MONO, fontSize: 15, color: C.muted }}>scored · 0:24</div>
      </Spot>
      {L.portrait && (
        <div style={at(L, [0, 0, 0, 0], [360, 20, 650, 533])}>
          <CortexBox cortex={cortex} t={0} w={650} h={533} rotation={Math.PI / 2} />
        </div>
      )}
      <Spot on={pulse(t, line, 3.2)} style={at(L, [300, 20, chartW, chartH], [30, 630, chartW, chartH], { ...card, padding: 0 })}>
        {HAS_RESULT ? (
          <ResponseChart values={result.relative} upTo={upTo} width={chartW} height={chartH} warmup={result.warmup_seconds} bands={bands} />
        ) : (
          <Tag tone="amber">Awaiting model output · no curve shown</Tag>
        )}
      </Spot>
      <div style={at(L, [1300, 474, 535, 70], [30, 1080, 980, 50], { display: 'flex', flexDirection: L.portrait ? 'row' : 'column', gap: L.portrait ? 30 : 6, fontSize: 20, color: C.muted })}>
        <span style={{ opacity: 0.4 + 0.6 * lit(t, climbs) }}>
          <span style={{ color: C.accent }}>▲ Climbs</span> predicted to lock in
        </span>
        <span style={{ opacity: 0.4 + 0.6 * lit(t, dips) }}>
          <span style={{ color: C.ink }}>▼ Dips</span> predicted to drift off
        </span>
      </div>
    </>
  )
}

/* ---------- the scored clip, played back against its result ---------- */

function PlayPane({ L, t, cortex }: { L: Layout; t: number; cortex: CortexAssets | null }) {
  const frame = useCurrentFrame()
  const s = Math.min(Math.floor(t), result.relative.length - 1)
  const callouts = HAS_RESULT
    ? [
        { second: result.peak.second, label: 'Highest', said: result.peak.said },
        { second: result.drop.second, label: 'Biggest drop', said: result.drop.said },
      ].sort((a, b) => a.second - b.second)
    : []
  const [chartW, chartH] = L.portrait ? [980, 300] : [690, 250]
  const [cw, ch] = L.portrait ? [550, 400] : [560, 330]
  return (
    <>
      <div style={at(L, [40, 20, 470, 836], [30, 20, 400, 711])}>
        <Phone width={L.portrait ? 400 : 470}>
          {/* The character walks off over the last drop, a second past the clip's end: hold its last frame. */}
          {frame < STIM_FRAMES ? (
            <Video src={staticFile('media/stimulus.mp4')} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
          ) : (
            <Freeze frame={STIM_FRAMES - 1}>
              <Video src={staticFile('media/stimulus.mp4')} muted style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
            </Freeze>
          )}
        </Phone>
        <div style={{ position: 'absolute', top: 18, left: 18 }}>
          <Tag tone="amber">AI-generated test clip</Tag>
        </div>
      </div>
      <div style={at(L, [560, 10, cw, ch], [460, 20, cw, ch])}>
        <CortexBox cortex={cortex} t={t} w={cw} h={ch} rotation={Math.PI / 2 + t * 0.05} />
      </div>
      <div style={at(L, [1150, 20, 690, 180], [460, 440, 550, 290], { ...card, display: 'flex', flexDirection: 'column', justifyContent: 'center', gap: L.portrait ? 16 : 10 })}>
        <span style={label}>Now</span>
        <div style={{ fontFamily: MONO, fontSize: L.portrait ? 72 : 52, fontVariantNumeric: 'tabular-nums' }}>0:{String(Math.max(0, s)).padStart(2, '0')}</div>
        <div style={{ height: 12, borderRadius: 6, background: C.fill, overflow: 'hidden' }}>
          <div style={{ width: `${(HAS_RESULT ? result.relative[Math.max(0, s)] : 0) * 100}%`, height: '100%', background: s < result.warmup_seconds ? C.muted : C.accent }} />
        </div>
        <div style={{ fontSize: 18, color: C.muted }}>{s < result.warmup_seconds ? 'Warm-up: the signal lags ~5 s' : 'Predicted response, relative to this clip'}</div>
      </div>
      <div style={at(L, [1150, 215, chartW, chartH], [30, 770, chartW, chartH])}>
        {HAS_RESULT ? (
          <ResponseChart values={result.relative} upTo={t} width={chartW} height={chartH} markers={callouts.map(c => ({ second: c.second, label: c.label }))} warmup={result.warmup_seconds} />
        ) : (
          <Tag tone="amber">Awaiting model output · no curve shown</Tag>
        )}
      </div>
      <div style={at(L, [560, 345, 560, 110], [30, 1090, 980, 130], { display: 'flex', flexDirection: 'column', gap: 10 })}>
        {callouts.filter(c => t >= c.second).map(c => (
          <div key={c.label} style={{ fontSize: 22, opacity: fadeIn(frame, c.second * FPS, 10) }}>
            <span style={{ fontFamily: MONO, color: C.accent }}>0:{String(c.second).padStart(2, '0')} · {c.label}</span>
            <span style={{ color: C.muted }}>{c.said ? ` · “${c.said}”` : ''}</span>
          </div>
        ))}
      </div>
      <div style={at(L, [560, 455, 560, 50], [30, 1230, 980, 60], { fontFamily: MONO, fontSize: 14, color: C.muted, lineHeight: 1.4 })}>
        Whole-cortex predicted response (RMS across 20,484 points), relative to this clip. Model output, not measured brain data.
      </div>
    </>
  )
}

/* ---------- sign-off (outside the scorer) ---------- */

function Cta({ L, w, t }: { L: Layout; w: Word[]; t: number }) {
  const frame = useCurrentFrame()
  const upload = cue(w, /^Upload/)
  const light = cue(w, /^light/)
  return (
    <AbsoluteFill style={{ alignItems: 'center', paddingTop: L.portrait ? 420 : 150, opacity: fadeIn(frame, 0, 15) }}>
      <Spot on={pulse(t, light, 1.6)} radius={28} style={{ padding: '10px 40px' }}>
        <div style={{ fontSize: L.portrait ? 120 : 140, fontWeight: 500, letterSpacing: -3 }}>fMRIght</div>
      </Spot>
      <Spot on={pulse(t, upload, 2.4)} radius={999} style={{ marginTop: 30 }}>
        <div style={{ padding: '20px 40px', borderRadius: 999, background: C.ink, color: C.bg, fontSize: 34, fontWeight: 500 }}>Score a clip</div>
      </Spot>
      <div style={{ marginTop: 22, fontSize: 24, color: C.muted, textAlign: 'center', maxWidth: 900, lineHeight: 1.4 }}>
        Free research preview · predictions are model output, not a forecast of views
      </div>
      <div style={{ marginTop: 10, fontSize: 24, color: C.muted, textAlign: 'center', maxWidth: 900, lineHeight: 1.4 }}>
        Unproven: in our 24-clip pilot the score's link to engagement was weak and not significant (r = 0.25, p = 0.24). A pre-registered test is next.
      </div>
    </AbsoluteFill>
  )
}
