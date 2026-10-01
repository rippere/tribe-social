import type { CSSProperties, ReactNode } from 'react'
import { Audio, Video } from '@remotion/media'
import { AbsoluteFill, Sequence, interpolate, staticFile, useCurrentFrame } from 'remotion'
import { AppWindow, Phone, ResponseChart, Tag, fadeIn, type Stage, type Word } from './components'
import { Cortex, useCortexAssets, type CortexAssets } from './cortex'
import { Bubble, MascotLayer, Spot, charX, cue, cutsFor, lit, pulse, useSceneTime, type Cut, type Plate } from './mascot'
import { C, FONT, FPS, MONO } from './theme'
import narration from './data/narration.json'
import result from './data/result.json'

export type Orientation = 'landscape' | 'portrait'

type LineKey = keyof typeof narration
const PAD = 18 // frames of air after each narration line
const STIM_SECONDS = 24.03
const CTA_FRAMES = 150

type SceneKey = 'intro' | 'upload' | 'encode' | 'extract' | 'read' | 'play' | 'limits' | 'cta'

interface SceneSpec {
  key: SceneKey
  line?: LineKey
  /** Frames before the narration starts, so the line lands on the character's action. */
  lead: number
  /** One-off mascot shots, played back to back across the scene. */
  clips: string[]
  /** Where the speech bubble sits in landscape (portrait always puts it above the head). */
  bubble?: 'left' | 'right'
  frames?: number
}

const SPECS: SceneSpec[] = [
  { key: 'intro', line: 'n1_intro', lead: 90, clips: ['intro_a', 'intro_b', 'intro_c'], bubble: 'right' },
  { key: 'upload', line: 'n2_upload', lead: 9, clips: ['upload_a', 'upload_b'], bubble: 'right' },
  { key: 'encode', line: 'n3_encode', lead: 6, clips: ['enc_a', 'enc_b', 'enc_c'], bubble: 'right' },
  { key: 'extract', line: 'n4_extract', lead: 6, clips: ['ext_a', 'ext_b'], bubble: 'left' },
  { key: 'read', line: 'n5_read', lead: 6, clips: ['read_a', 'read_b', 'read_c'], bubble: 'left' },
  { key: 'play', lead: 0, clips: ['play_a', 'play_b', 'play_c', 'play_d', 'play_e'], frames: Math.ceil(STIM_SECONDS * FPS) + 15 },
  { key: 'limits', line: 'n6_limits', lead: 6, clips: ['lim_a', 'lim_b', 'lim_c'], bubble: 'right' },
  { key: 'cta', lead: 0, clips: ['cta'], frames: CTA_FRAMES },
]

interface Scene extends SceneSpec {
  frames: number
  words: Word[]
  cuts: Cut[]
}

const SCENES: Scene[] = SPECS.map(s => {
  const frames = s.line ? s.lead + Math.ceil(narration[s.line].duration * FPS) + PAD : (s.frames ?? 0)
  return { ...s, frames, words: s.line ? (narration[s.line].words as Word[]) : [], cuts: cutsFor(s.clips, frames) }
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
  /** Scorer window on the canvas; its body starts BODY px below the window top. */
  win: { x: number; y: number; w: number; h: number }
  plate: Plate
  /** Canvas y of the character's head when standing. */
  headY: number
  bubble: { size: number; maxWidth: number }
}

const HEAD = 0.596 // anchor head-top, as a fraction of the clip height

function layout(o: Orientation): Layout {
  if (o === 'landscape') {
    const plate = { x: 0, y: 0, w: 1920, h: 1080 }
    return { W: 1920, H: 1080, portrait: false, win: { x: 24, y: 24, w: 1872, h: 1032 }, plate, headY: plate.y + HEAD * plate.h, bubble: { size: 34, maxWidth: 560 } }
  }
  const plate = { x: -276, y: 1920 - 918 - 30, w: 1632, h: 918 }
  return { W: 1080, H: 1920, portrait: true, win: { x: 20, y: 20, w: 1040, h: 1880 }, plate, headY: plate.y + HEAD * plate.h, bubble: { size: 40, maxWidth: 900 } }
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
            {s.line && (
              <Sequence from={s.lead} layout="none">
                <Audio src={staticFile(`media/narration/${s.line}.mp3`)} />
              </Sequence>
            )}
            <SceneFrame scene={s} L={L} cortex={cortex} first={s.key === 'upload'} />
          </Sequence>
        )
      })}
    </AbsoluteFill>
  )
}

function SceneFrame({ scene, L, cortex, first }: { scene: Scene; L: Layout; cortex: CortexAssets | null; first: boolean }) {
  const frame = useCurrentFrame()
  const t = useSceneTime(scene.lead)
  const stage = WINDOW_SCENES[scene.key]
  const content = <SceneBody scene={scene} L={L} cortex={cortex} t={t} />
  const x = charX(scene.cuts, frame, L.plate)
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
      {scene.line && (
        <Bubble
          words={scene.words}
          t={t}
          x={x}
          headY={L.headY}
          side={L.portrait ? 'above' : (scene.bubble ?? 'right')}
          canvasW={L.W}
          canvasH={L.H}
          size={L.bubble.size}
          maxWidth={L.bubble.maxWidth}
        />
      )}
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
    case 'limits':
      return <Limits L={L} w={w} t={t} />
    case 'cta':
      return <Cta L={L} t={t} />
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

/* ---------- intro ---------- */

function Intro({ L, w, t }: { L: Layout; w: Word[]; t: number }) {
  const frame = useCurrentFrame()
  const on = pulse(t, cue(w, /^Eff/), 2.2)
  return (
    <AbsoluteFill style={{ alignItems: 'center', paddingTop: L.portrait ? 360 : 150, opacity: fadeIn(frame, 10, 18) }}>
      <Spot on={on} radius={28} style={{ padding: '18px 44px', textAlign: 'center' }}>
        <div style={{ fontSize: L.portrait ? 132 : 150, fontWeight: 500, letterSpacing: -4, lineHeight: 1 }}>fMRIght</div>
        <div style={{ marginTop: 24, fontSize: L.portrait ? 38 : 40, color: C.muted, maxWidth: 860, lineHeight: 1.3 }}>
          A predicted brain response to your video, second by second.
        </div>
      </Spot>
    </AbsoluteFill>
  )
}

/* ---------- upload: file → rented GPU; video dropped, scores kept ---------- */

function UploadPane({ L, w, t }: { L: Layout; w: Word[]; t: number }) {
  const up = cue(w, /^upload/)
  const gpu = cue(w, /^graphics/)
  const kept = cue(w, /^isn't/)
  const scores = cue(w, /^scores/)
  const p = interpolate(t, [up + 0.3, gpu + 1.4], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' })
  const gone = lit(t, kept + 0.3)
  return (
    <>
      <Spot on={pulse(t, up, 2)} style={at(L, [40, 36, 860, 330], [30, 30, 980, 380], card)}>
        <div style={{ display: 'flex', gap: 30, height: '100%' }}>
          <div style={{ opacity: 1 - 0.75 * gone }}>
            <Phone width={L.portrait ? 170 : 150}>
              <Stim />
            </Phone>
          </div>
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
            <div style={{ fontSize: 32, fontWeight: 500 }}>mac_and_cheese.mp4</div>
            <div style={{ fontSize: 19, color: C.muted, marginTop: 8, fontFamily: MONO }}>0:24 · 9:16 · AI-generated test clip</div>
            <div style={{ marginTop: 28, height: 12, borderRadius: 6, background: C.fill, overflow: 'hidden' }}>
              <div style={{ width: `${p * 100}%`, height: '100%', background: C.accent }} />
            </div>
            <div style={{ marginTop: 12, fontSize: 18, color: C.muted, fontFamily: MONO }}>
              {p <= 0 ? 'Ready to send' : p < 1 ? `Sending to the GPU… ${Math.round(p * 100)}%` : 'Delivered'}
            </div>
            <div style={{ marginTop: 22, fontSize: 16, color: C.muted, lineHeight: 1.45 }}>By scoring a clip you confirm you have the rights to it.</div>
          </div>
        </div>
      </Spot>
      <Arrow L={L} p={p} />
      <Spot on={pulse(t, gpu, 2.2)} style={at(L, [980, 36, 420, 330], [30, 460, 980, 250], { ...card, display: 'flex', flexDirection: 'column', justifyContent: 'center', gap: 14 })}>
        <span style={label}>Rented cloud GPU</span>
        <div style={{ fontSize: 34, fontWeight: 500 }}>NVIDIA A100</div>
        <div style={{ fontFamily: MONO, fontSize: 18, color: C.muted }}>80 GB · billed by the second</div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, fontFamily: MONO, fontSize: 18, color: p >= 1 ? C.accent : C.muted }}>
          <span style={{ width: 10, height: 10, borderRadius: 5, background: p >= 1 ? C.accent : '#3a3a39' }} />
          {p <= 0 ? 'idle' : p < 1 ? 'receiving' : 'running TRIBE v2'}
        </div>
      </Spot>
      <div style={at(L, [1440, 36, 400, 330], [30, 750, 980, 230], { display: 'flex', flexDirection: 'column', gap: 20 })}>
        <Spot on={pulse(t, kept, 1.4)} style={{ ...card, flex: 1, padding: '0 26px', display: 'flex', alignItems: 'center', gap: 14, fontSize: 22 }}>
          <span style={{ fontFamily: MONO, color: gone ? C.ink : C.muted }}>{gone > 0.5 ? '✕' : '·'}</span>
          <span>
            Video <span style={{ color: C.muted }}>· deleted after scoring</span>
          </span>
        </Spot>
        <Spot on={pulse(t, scores, 1.6)} style={{ ...card, flex: 1, padding: '0 26px', display: 'flex', alignItems: 'center', gap: 14, fontSize: 22 }}>
          <span style={{ fontFamily: MONO, color: lit(t, scores) > 0.5 ? C.accent : C.muted }}>✓</span>
          <span>
            Scores <span style={{ color: C.muted }}>· kept in the research dataset</span>
          </span>
        </Spot>
      </div>
    </>
  )
}

function Arrow({ L, p }: { L: Layout; p: number }) {
  // landscape: card → GPU to the right; portrait: card → GPU below
  const [x, y, len] = L.portrait ? [520, 418, 34] : [912, 200, 44]
  const dot = p > 0 && p < 1 ? (p * 3) % 1 : -1
  return (
    <svg style={{ position: 'absolute', left: x - 30, top: y - 30, overflow: 'visible' }} width={60} height={60}>
      <g transform={`translate(30 30) rotate(${L.portrait ? 90 : 0})`}>
        <line x1={0} x2={len} y1={0} y2={0} stroke={p > 0 ? C.accent : C.line} strokeWidth={3} strokeDasharray="6 6" />
        <path d={`M${len} -8 L${len + 12} 0 L${len} 8 Z`} fill={p > 0 ? C.accent : C.line} />
        {dot >= 0 && <circle cx={dot * len} cy={0} r={5} fill={C.accent} />}
      </g>
    </svg>
  )
}

/* ---------- encode: frames, audio, words → TRIBE v2 ---------- */

function EncodePane({ L, w, t }: { L: Layout; w: Word[]; t: number }) {
  const frame = useCurrentFrame()
  const at3 = [cue(w, /^frames/), cue(w, /^audio/), cue(w, /^words/)]
  const learned = cue(w, /^learned/)
  const scanner = cue(w, /^scanner/)
  const channel = (i: number, title: string, body: ReactNode) => (
    <Spot on={pulse(t, at3[i], 1.4)} style={{ ...card, flex: 1, display: 'flex', flexDirection: 'column', gap: L.portrait ? 10 : 16, minWidth: 0, minHeight: 0, overflow: 'hidden', padding: L.portrait ? 18 : 26 }}>
      <span style={{ ...label, color: lit(t, at3[i]) > 0.5 ? C.accent : C.muted }}>{title}</span>
      <div style={{ flex: 1, minHeight: 0, opacity: 0.35 + 0.65 * lit(t, at3[i]) }}>{body}</div>
    </Spot>
  )
  const bars = Array.from({ length: 28 }, (_, i) => 0.25 + 0.75 * Math.abs(Math.sin(i * 1.7 + frame * 0.21) * Math.cos(i * 0.6 + frame * 0.09)))
  return (
    <>
      <div style={at(L, [56, 30, 256, 455], [30, 30, 300, 533])}>
        <Phone width={L.portrait ? 300 : 256}>
          <Stim />
        </Phone>
      </div>
      <div style={at(L, [356, 30, 1484, 230], [360, 30, 650, 533], { display: 'flex', flexDirection: L.portrait ? 'column' : 'row', gap: 22 })}>
        {channel(
          0,
          'Frames',
          <div style={{ display: 'flex', gap: 8, height: '100%' }}>
            {[2, 8, 14, 20].map(s => (
              <div key={s} style={{ flex: 1, borderRadius: 8, overflow: 'hidden', background: '#000' }}>
                <Stim trim={s * FPS} />
              </div>
            ))}
          </div>,
        )}
        {channel(
          1,
          'Audio',
          <div style={{ display: 'flex', alignItems: 'center', gap: 5, height: '100%' }}>
            {bars.map((b, i) => (
              <div key={i} style={{ flex: 1, height: `${b * 100}%`, borderRadius: 3, background: C.accent }} />
            ))}
          </div>,
        )}
        {channel(
          2,
          'Words',
          <div style={{ fontSize: 22, lineHeight: 1.45, color: C.ink }}>
            “…for about a full minute. Okay, yeah.”
            <div style={{ marginTop: 8, fontFamily: MONO, fontSize: 15, color: C.muted }}>transcript, word-timed</div>
          </div>,
        )}
      </div>
      <Spot on={pulse(t, learned, 2.4)} style={at(L, [356, 290, 960, 190], [30, 600, 980, 200], { ...card, display: 'flex', flexDirection: 'column', justifyContent: 'center', gap: 10 })}>
        <span style={label}>The model</span>
        <div style={{ fontSize: 32, fontWeight: 500 }}>TRIBE v2 · Meta FAIR</div>
        <div style={{ fontSize: 20, color: C.muted }}>Trained on fMRI scans of people watching video.</div>
      </Spot>
      <Spot on={pulse(t, scanner, 2)} style={at(L, [1346, 290, 494, 190], [30, 830, 980, 160], { ...card, display: 'flex', flexDirection: 'column', justifyContent: 'center', gap: 10 })}>
        <span style={{ ...label, color: lit(t, scanner) > 0.5 ? C.accent : C.muted }}>No scanner involved</span>
        <div style={{ fontSize: 20, color: C.muted, lineHeight: 1.4 }}>It predicts the response from the video file alone.</div>
      </Spot>
    </>
  )
}

/* ---------- extract: ~20k points, one frame per second ---------- */

function ExtractPane({ L, w, t, cortex }: { L: Layout; w: Word[]; t: number; cortex: CortexAssets | null }) {
  const pts = cue(w, /^twenty/)
  const fps1 = cue(w, /^frame/)
  const glow = cue(w, /^lighting/)
  const n = Math.round(interpolate(t, [pts - 0.1, pts + 1.3], [0, 20484], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' }))
  const ticks = Math.floor(interpolate(t, [fps1, fps1 + 1.8], [0, 24], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' }))
  const [cw, ch] = L.portrait ? [980, 640] : [900, 470]
  return (
    <>
      <Spot on={pulse(t, pts, 2.2)} style={at(L, [40, 30, 420, 210], [30, 700, 470, 230], { ...card, display: 'flex', flexDirection: 'column', justifyContent: 'center', gap: 8 })}>
        <span style={label}>Points predicted</span>
        <div style={{ fontFamily: MONO, fontSize: 64, fontVariantNumeric: 'tabular-nums' }}>{n.toLocaleString('en-US')}</div>
        <div style={{ fontSize: 18, color: C.muted }}>across the cortex surface</div>
      </Spot>
      <Spot on={pulse(t, glow, 2)} radius={22} style={at(L, [490, 6, cw, ch], [30, 20, cw, ch])}>
        <CortexBox cortex={cortex} t={t % 24} w={cw} h={ch} rotation={Math.PI / 2 + t * 0.12} />
      </Spot>
      <Spot on={pulse(t, fps1, 2.2)} style={at(L, [1420, 30, 420, 210], [540, 700, 470, 230], { ...card, display: 'flex', flexDirection: 'column', justifyContent: 'center', gap: 14 })}>
        <span style={label}>One frame per second</span>
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

/* ---------- read: what the line means ---------- */

function ReadPane({ L, w, t, cortex }: { L: Layout; w: Word[]; t: number; cortex: CortexAssets | null }) {
  const real = cue(w, /^real/)
  const line = cue(w, /^line/)
  const done = cue(w, /^second\.$/)
  const rises = cue(w, /^Rises/)
  const dips = cue(w, /^Dips/)
  const upTo = interpolate(t, [line, done + 0.4], [0, result.relative.length - 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' })
  const bands = HAS_RESULT
    ? [
        { from: Math.max(result.warmup_seconds, result.peak.second - 4), to: result.peak.second, on: lit(t, rises, 0.35), label: '▲ rise' },
        { from: result.drop.second - 1, to: result.drop.second, on: lit(t, dips, 0.35), label: '▼ dip' },
      ]
    : []
  const [chartW, chartH] = L.portrait ? [980, 420] : [1020, 400]
  return (
    <>
      <Spot on={pulse(t, real, 2)} style={at(L, [40, 20, 210, 430], [30, 20, 250, 500])}>
        <Phone width={L.portrait ? 250 : 210}>
          <Stim />
        </Phone>
        <div style={{ marginTop: 10, fontFamily: MONO, fontSize: 15, color: C.muted }}>scored · 0:24</div>
      </Spot>
      <div style={at(L, [280, 10, 520, 430], [310, 20, 700, 460])}>
        <CortexBox cortex={cortex} t={0} w={L.portrait ? 700 : 520} h={L.portrait ? 460 : 430} rotation={Math.PI / 2} />
      </div>
      <Spot on={pulse(t, line, 2.6)} style={at(L, [820, 20, chartW, chartH], [30, 520, chartW, chartH], { ...card, padding: 0 })}>
        {HAS_RESULT ? (
          <ResponseChart values={result.relative} upTo={upTo} width={chartW} height={chartH} warmup={result.warmup_seconds} bands={bands} />
        ) : (
          <Tag tone="amber">Awaiting model output · no curve shown</Tag>
        )}
      </Spot>
      <div style={at(L, [820, 436, 1020, 50], [30, 970, 980, 60], { display: 'flex', gap: 30, fontSize: 22, color: C.muted, alignItems: 'center' })}>
        <span style={{ opacity: 0.4 + 0.6 * lit(t, rises) }}>
          <span style={{ color: C.accent }}>▲ Rise</span> predicted to lock in
        </span>
        <span style={{ opacity: 0.4 + 0.6 * lit(t, dips) }}>
          <span style={{ color: C.ink }}>▼ Dip</span> predicted to drift
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
  const [cw, ch] = L.portrait ? [550, 400] : [560, 400]
  return (
    <>
      <div style={at(L, [40, 20, 470, 836], [30, 20, 400, 711])}>
        <Phone width={L.portrait ? 400 : 470}>
          <Video src={staticFile('media/stimulus.mp4')} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
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
      <div style={at(L, [560, 440, 560, 150], [30, 1090, 980, 130], { display: 'flex', flexDirection: 'column', gap: 10 })}>
        {callouts.filter(c => t >= c.second).map(c => (
          <div key={c.label} style={{ fontSize: 22, opacity: fadeIn(frame, c.second * FPS, 10) }}>
            <span style={{ fontFamily: MONO, color: C.accent }}>0:{String(c.second).padStart(2, '0')} · {c.label}</span>
            <span style={{ color: C.muted }}>{c.said ? ` · “${c.said}”` : ''}</span>
          </div>
        ))}
      </div>
      <div style={at(L, [560, 610, 560, 80], [30, 1230, 980, 60], { fontFamily: MONO, fontSize: 15, color: C.muted, lineHeight: 1.4 })}>
        Whole-cortex predicted response (RMS across 20,484 points), relative to this clip. Model output, not measured brain data.
      </div>
    </>
  )
}

/* ---------- limits + CTA (outside the scorer) ---------- */

function Limits({ L, w, t }: { L: Layout; w: Word[]; t: number }) {
  const frame = useCurrentFrame()
  const read = cue(w, /^read/)
  const pilot = cue(w, /^pilot/)
  const weak = cue(w, /^weakly/)
  const second = cue(w, /^opinion/)
  const stat = (on: number, k: string, v: string, note: string) => (
    <Spot on={on} style={{ ...card, flex: 1, display: 'flex', flexDirection: 'column', gap: 10 }}>
      <span style={label}>{k}</span>
      <div style={{ fontFamily: MONO, fontSize: L.portrait ? 40 : 44 }}>{v}</div>
      <div style={{ fontSize: 19, color: C.muted, lineHeight: 1.4 }}>{note}</div>
    </Spot>
  )
  return (
    <AbsoluteFill style={{ alignItems: 'center', paddingTop: L.portrait ? 220 : 80, opacity: fadeIn(frame, 0, 12) }}>
      <Spot on={pulse(t, read, 2.4)} radius={22} style={{ padding: '14px 28px', textAlign: 'center' }}>
        <div style={{ fontSize: L.portrait ? 54 : 60, fontWeight: 500, letterSpacing: -1, lineHeight: 1.15, maxWidth: L.portrait ? 940 : 1400 }}>
          A read of the video, not a forecast of views.
        </div>
      </Spot>
      <div style={{ marginTop: 36, width: L.portrait ? 980 : 1500, display: 'flex', flexDirection: L.portrait ? 'column' : 'row', gap: 22 }}>
        {stat(pulse(t, pilot, 2.2), 'Pilot, 24 clips', 'r = 0.25', 'Score vs engagement, p = 0.24.')}
        {stat(pulse(t, weak, 2.2), 'Verdict', 'Weak · n.s.', 'Not statistically significant.')}
        {stat(pulse(t, second, 2.4), 'Use it as', 'A second opinion', 'The clip shown is AI-generated. TRIBE v2 is CC-BY-NC-4.0.')}
      </div>
    </AbsoluteFill>
  )
}

function Cta({ L, t }: { L: Layout; t: number }) {
  const frame = useCurrentFrame()
  return (
    <AbsoluteFill style={{ alignItems: 'center', paddingTop: L.portrait ? 420 : 170, opacity: fadeIn(frame, 0, 15) }}>
      <div style={{ fontSize: L.portrait ? 120 : 140, fontWeight: 500, letterSpacing: -3 }}>fMRIght</div>
      <Spot on={pulse(t, 0.8, 1.8)} radius={999} style={{ marginTop: 30 }}>
        <div style={{ padding: '20px 40px', borderRadius: 999, background: C.ink, color: C.bg, fontSize: 34, fontWeight: 500 }}>Score a clip</div>
      </Spot>
      <div style={{ marginTop: 22, fontSize: 26, color: C.muted }}>Free research preview</div>
    </AbsoluteFill>
  )
}
