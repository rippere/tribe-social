import type { ReactNode } from 'react'
import { Audio, Video } from '@remotion/media'
import { AbsoluteFill, Sequence, interpolate, staticFile, useCurrentFrame } from 'remotion'
import { AppWindow, Captions, Mascot, Phone, ResponseChart, Tag, fadeIn, type Stage, type Word } from './components'
import { Cortex, useCortexAssets, type CortexAssets } from './cortex'
import { C, FONT, FPS, MONO } from './theme'
import narration from './data/narration.json'
import result from './data/result.json'

export type Orientation = 'landscape' | 'portrait'

type LineKey = keyof typeof narration
const PAD = 18 // frames of air after each narration line
const STIM_SECONDS = 24.03
const CTA_FRAMES = 105

interface Scene {
  key: string
  line?: LineKey
  frames: number
}

const SCENES: Scene[] = (
  [
    { key: 'intro', line: 'n1_intro', frames: 0 },
    { key: 'upload', line: 'n2_upload', frames: 0 },
    { key: 'encode', line: 'n3_encode', frames: 0 },
    { key: 'extract', line: 'n4_extract', frames: 0 },
    { key: 'readIntro', line: 'n5_read', frames: 0 },
    { key: 'play', frames: Math.ceil(STIM_SECONDS * FPS) + 15 },
    { key: 'limits', line: 'n6_limits', frames: 0 },
    { key: 'cta', frames: CTA_FRAMES },
  ] as Scene[]
).map(s => ({ ...s, frames: s.line ? Math.ceil(narration[s.line].duration * FPS) + PAD : s.frames }))

export function explainerDuration(): number {
  return SCENES.reduce((n, s) => n + s.frames, 0)
}

const HAS_RESULT = result.source === 'tribe' && result.relative.length > 1

interface Layout {
  W: number
  H: number
  portrait: boolean
  /** Scorer window in logical px; drawn at `panelScale` so UI text stays legible on a phone. */
  panel: { x: number; y: number; w: number; h: number }
  panelScale: number
  mascot: { x: number; y: number; size: number }
  captions: { y: number; maxWidth: number; size: number }
}

function layout(o: Orientation): Layout {
  return o === 'landscape'
    ? {
        W: 1920, H: 1080, portrait: false,
        panel: { x: 760, y: 90, w: 1080, h: 760 }, panelScale: 1,
        mascot: { x: 40, y: 150, size: 680 },
        captions: { y: 900, maxWidth: 1600, size: 46 },
      }
    : {
        W: 1080, H: 1920, portrait: true,
        panel: { x: 40, y: 110, w: 740, h: 726 }, panelScale: 1.35,
        mascot: { x: 250, y: 1290, size: 580 },
        captions: { y: 1140, maxWidth: 980, size: 50 },
      }
}

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
            {s.line && <Audio src={staticFile(`media/narration/${s.line}.mp3`)} />}
            <SceneBody scene={s.key} L={L} cortex={cortex} frames={s.frames} />
            {s.line && (
              <AbsoluteFill style={{ top: L.captions.y, height: 'auto', alignItems: 'center' }}>
                <Captions words={narration[s.line].words as Word[]} size={L.captions.size} maxWidth={L.captions.maxWidth} />
              </AbsoluteFill>
            )}
          </Sequence>
        )
      })}
    </AbsoluteFill>
  )
}

function SceneBody({ scene, L, cortex, frames }: { scene: string; L: Layout; cortex: CortexAssets | null; frames: number }) {
  switch (scene) {
    case 'intro':
      return <Intro L={L} />
    case 'upload':
      return <WithMascot L={L} clip="m2_point" stage="upload" frames={frames}><UploadPane L={L} frames={frames} /></WithMascot>
    case 'encode':
      return <WithMascot L={L} clip="m3_think" stage="encode" frames={frames}><EncodePane L={L} /></WithMascot>
    case 'extract':
      return <WithMascot L={L} clip="m4_count" stage="extract" frames={frames}><ExtractPane L={L} cortex={cortex} /></WithMascot>
    case 'readIntro':
      return <WithMascot L={L} clip="m2_point" stage="read" frames={frames}><ReadIntroPane L={L} cortex={cortex} /></WithMascot>
    case 'play':
      return <Play L={L} cortex={cortex} />
    case 'limits':
      return <Limits L={L} />
    case 'cta':
      return <Cta L={L} />
    default:
      return null
  }
}

/* ---------- shared frame: mascot narrator + scorer window ---------- */

function WithMascot({ L, clip, stage, frames, children }: { L: Layout; clip: string; stage: Stage; frames: number; children: ReactNode }) {
  const frame = useCurrentFrame()
  const o = fadeIn(frame) * interpolate(frame, [frames - 8, frames], [1, 0.4], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' })
  return (
    <AbsoluteFill>
      <Mascot clip={clip} size={L.mascot.size} style={{ position: 'absolute', left: L.mascot.x, top: L.mascot.y }} />
      <div style={{ position: 'absolute', left: L.panel.x, top: L.panel.y, opacity: o, transformOrigin: 'top left', transform: `translateY(${(1 - fadeIn(frame)) * 16}px) scale(${L.panelScale})` }}>
        <AppWindow stage={stage} width={L.panel.w} height={L.panel.h}>{children}</AppWindow>
      </div>
    </AbsoluteFill>
  )
}

function Intro({ L }: { L: Layout }) {
  const frame = useCurrentFrame()
  const title = (
    <div style={{ opacity: fadeIn(frame, 20, 18) }}>
      <div style={{ fontSize: L.portrait ? 120 : 132, fontWeight: 500, letterSpacing: -3, lineHeight: 1 }}>fMRIght</div>
      <div style={{ marginTop: 22, fontSize: L.portrait ? 38 : 40, color: C.muted, maxWidth: 820, lineHeight: 1.3 }}>
        A predicted brain response to your video, second by second.
      </div>
    </div>
  )
  return L.portrait ? (
    <AbsoluteFill>
      <div style={{ position: 'absolute', top: 260, left: 60, right: 60 }}>{title}</div>
      <Mascot clip="m1_hello" size={680} style={{ position: 'absolute', left: 200, top: 470 }} />
    </AbsoluteFill>
  ) : (
    <AbsoluteFill>
      <Mascot clip="m1_hello" size={760} style={{ position: 'absolute', left: 20, top: 90 }} />
      <div style={{ position: 'absolute', left: 860, top: 300 }}>{title}</div>
    </AbsoluteFill>
  )
}

/* ---------- stage panes (inside the app window) ---------- */

function UploadPane({ L, frames }: { L: Layout; frames: number }) {
  const frame = useCurrentFrame()
  const p = interpolate(frame, [15, frames * 0.7], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' })
  const thumbW = 280
  return (
    <div style={{ position: 'absolute', inset: 0, padding: 32, display: 'flex', flexDirection: 'column', gap: 28 }}>
      <div style={{ display: 'flex', gap: 28, alignItems: 'center', background: C.fill, borderRadius: 16, padding: 24 }}>
        <Phone width={thumbW * 0.56}>
          <Video src={staticFile('media/stimulus.mp4')} muted style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
        </Phone>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 30, fontWeight: 500 }}>mac_and_cheese.mp4</div>
          <div style={{ fontSize: 20, color: C.muted, marginTop: 8, fontFamily: MONO }}>0:24 · 9:16 · AI-generated test clip</div>
          <div style={{ marginTop: 26, height: 10, borderRadius: 5, background: C.fill, overflow: 'hidden' }}>
            <div style={{ width: `${p * 100}%`, height: '100%', background: C.accent }} />
          </div>
          <div style={{ marginTop: 12, fontSize: 18, color: C.muted, fontFamily: MONO }}>
            {p < 1 ? `Sending to rented cloud GPU… ${Math.round(p * 100)}%` : 'On the GPU'}
          </div>
        </div>
      </div>
      <div style={{ fontSize: 19, lineHeight: 1.5, color: C.muted }}>
        By scoring a clip you confirm you have the rights to it. The video is sent to a rented cloud GPU and isn&apos;t kept; the scores are saved to our research dataset.
      </div>
    </div>
  )
}

function EncodePane({ L }: { L: Layout }) {
  const frame = useCurrentFrame()
  const t = frame / FPS
  const words = narration.n3_encode.words as Word[]
  const at = (re: RegExp) => words.find(w => re.test(w.w))?.s ?? 99
  const chips = [
    { label: 'Frames', on: at(/^frames/i) },
    { label: 'Audio', on: at(/^audio/i) },
    { label: 'Words', on: at(/^words/i) },
  ]
  const phoneW = 300
  return (
    <div style={{ position: 'absolute', inset: 0, padding: 32, display: 'flex', gap: 40, alignItems: 'center' }}>
      <Phone width={phoneW}>
        <Video src={staticFile('media/stimulus.mp4')} muted style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
      </Phone>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
        {chips.map(c => {
          const lit = t >= c.on
          return (
            <span key={c.label} style={{ alignSelf: 'flex-start', padding: '14px 26px', borderRadius: 999, fontSize: 30, fontWeight: 500, color: lit ? C.accent : C.muted, background: lit ? C.accentBg : C.fill }}>
              {c.label}
            </span>
          )
        })}
        <div style={{ marginTop: 18, fontSize: 20, lineHeight: 1.5, color: C.muted, maxWidth: 420 }}>
          TRIBE v2 (Meta FAIR), trained on fMRI of people watching video. Predicts the response; no scanner involved.
        </div>
      </div>
    </div>
  )
}

function CortexBox({ cortex, t, w: width, h: height, rotation }: { cortex: CortexAssets | null; t: number; w: number; h: number; rotation: number }) {
  // ThreeCanvas rejects fractional sizes.
  const w = Math.round(width)
  const h = Math.round(height)
  if (!cortex) return <div style={{ width: w, height: h }} />
  return (
    <div style={{ position: 'relative', width: w, height: h }}>
      <Cortex assets={cortex} t={t} rotation={rotation} width={w} height={h} />
      <div style={{ position: 'absolute', left: 12, bottom: 12 }}>
        {cortex.activity ? <Tag tone="accent">TRIBE v2 output · fsaverage cortex</Tag> : <Tag tone="amber">Awaiting model output · no activity shown</Tag>}
      </div>
    </div>
  )
}

function ExtractPane({ L, cortex }: { L: Layout; cortex: CortexAssets | null }) {
  const frame = useCurrentFrame()
  const t = frame / FPS
  return (
    <div style={{ position: 'absolute', inset: 0, padding: 32 }}>
      <CortexBox cortex={cortex} t={t % 24} w={L.panel.w - 64} h={L.panel.h - 210} rotation={Math.PI / 2 + t * 0.12} />
      <div style={{ marginTop: 14, fontFamily: MONO, fontSize: 22, color: C.muted }}>
        20,484 points · 1 frame per second of video
      </div>
    </div>
  )
}

function ReadIntroPane({ L, cortex }: { L: Layout; cortex: CortexAssets | null }) {
  const w = L.panel.w - 64
  return (
    <div style={{ position: 'absolute', inset: 0, padding: 32, display: 'flex', flexDirection: 'column', gap: 18 }}>
      <CortexBox cortex={cortex} t={0} w={w} h={L.panel.h * 0.42} rotation={Math.PI / 2} />
      <ResponseChart values={HAS_RESULT ? result.relative : [0, 0]} upTo={0} width={w} height={L.panel.h * 0.3} warmup={HAS_RESULT ? result.warmup_seconds : 0} />
      <div style={{ display: 'flex', gap: 28, fontSize: 20, color: C.muted }}>
        <span><span style={{ color: C.accent }}>▲ Rise</span> predicted to lock in</span>
        <span><span style={{ color: C.ink }}>▼ Dip</span> predicted to drift</span>
      </div>
    </div>
  )
}

/* ---------- the scored clip, played back against its result ---------- */

function Play({ L, cortex }: { L: Layout; cortex: CortexAssets | null }) {
  const frame = useCurrentFrame()
  const t = frame / FPS
  const phoneW = L.portrait ? 420 : 430
  const sideW = L.portrait ? L.W - 80 : L.W - phoneW - 200
  const callouts = HAS_RESULT
    ? [
        { second: result.peak.second, label: 'Highest', said: result.peak.said },
        { second: result.drop.second, label: 'Biggest drop', said: result.drop.said },
      ].sort((a, b) => a.second - b.second)
    : []

  const phone = (
    <div style={{ position: 'relative' }}>
      <Phone width={phoneW}>
        <Video src={staticFile('media/stimulus.mp4')} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
      </Phone>
      <div style={{ position: 'absolute', top: 18, left: 18 }}><Tag tone="amber">AI-generated test clip</Tag></div>
    </div>
  )
  const side = (
    <div style={{ width: sideW, display: 'flex', flexDirection: 'column', gap: 16 }}>
      <CortexBox cortex={cortex} t={t} w={sideW} h={L.portrait ? 420 : 400} rotation={Math.PI / 2 + t * 0.05} />
      {HAS_RESULT ? (
        <ResponseChart
          values={result.relative}
          upTo={t}
          width={sideW}
          height={L.portrait ? 300 : 280}
          markers={callouts.map(c => ({ second: c.second, label: c.label }))}
          warmup={result.warmup_seconds}
        />
      ) : (
        <Tag tone="amber">Awaiting model output · no curve shown</Tag>
      )}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10, minHeight: 110 }}>
        {callouts.filter(c => t >= c.second).map(c => (
          <div key={c.label} style={{ fontSize: 22, opacity: fadeIn(frame, c.second * FPS, 10) }}>
            <span style={{ fontFamily: MONO, color: C.accent }}>0:{String(c.second).padStart(2, '0')} · {c.label}</span>
            <span style={{ color: C.muted }}>{c.said ? ` · “${c.said}”` : ''}</span>
          </div>
        ))}
      </div>
      <div style={{ fontFamily: MONO, fontSize: 16, color: C.muted }}>
        Whole-cortex predicted response (RMS across 20,484 points), relative to this clip. Model output, not measured brain data.
      </div>
    </div>
  )
  return L.portrait ? (
    <AbsoluteFill style={{ alignItems: 'center', paddingTop: 70, gap: 30 }}>
      {phone}
      {side}
    </AbsoluteFill>
  ) : (
    <AbsoluteFill style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 70 }}>
      {phone}
      {side}
    </AbsoluteFill>
  )
}

function Limits({ L }: { L: Layout }) {
  const frame = useCurrentFrame()
  const card = (
    <div style={{ opacity: fadeIn(frame, 6), width: 960, background: C.panel, borderRadius: 24, padding: 44 }}>
      <div style={{ fontSize: 44, fontWeight: 500, letterSpacing: -0.6, lineHeight: 1.2 }}>A read of the video, not a forecast of views.</div>
      <div style={{ marginTop: 28, display: 'flex', flexDirection: 'column', gap: 14, fontSize: 24, color: C.muted, lineHeight: 1.45 }}>
        <span>Pilot, 24 clips: score vs engagement r = 0.25, p = 0.24. Weak and not significant.</span>
        <span>The clip above is AI-generated, made to test the pipeline.</span>
        <span>TRIBE v2 is Meta FAIR&apos;s model, licensed CC-BY-NC-4.0.</span>
      </div>
    </div>
  )
  return L.portrait ? (
    <AbsoluteFill>
      <div style={{ position: 'absolute', top: 420, left: 60 }}>{card}</div>
      <Mascot clip="m5_shrug" size={L.mascot.size} style={{ position: 'absolute', left: L.mascot.x, top: L.mascot.y }} />
    </AbsoluteFill>
  ) : (
    <AbsoluteFill>
      <Mascot clip="m5_shrug" size={L.mascot.size} style={{ position: 'absolute', left: L.mascot.x, top: L.mascot.y }} />
      <div style={{ position: 'absolute', left: 820, top: 200 }}>{card}</div>
    </AbsoluteFill>
  )
}

function Cta({ L }: { L: Layout }) {
  const frame = useCurrentFrame()
  return (
    <AbsoluteFill style={{ alignItems: 'center', justifyContent: 'center', opacity: fadeIn(frame, 0, 15) }}>
      <div style={{ fontSize: L.portrait ? 120 : 140, fontWeight: 500, letterSpacing: -3 }}>fMRIght</div>
      <div style={{ marginTop: 30, padding: '20px 40px', borderRadius: 999, background: C.ink, color: C.bg, fontSize: 34, fontWeight: 500 }}>
        Score a clip
      </div>
      <div style={{ marginTop: 22, fontSize: 26, color: C.muted }}>Free research preview</div>
    </AbsoluteFill>
  )
}
