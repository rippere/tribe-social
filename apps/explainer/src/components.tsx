import type { CSSProperties, ReactNode } from 'react'
import { Video } from '@remotion/media'
import { interpolate, staticFile, useCurrentFrame, useVideoConfig } from 'remotion'
import { C, FONT, MONO } from './theme'

export type Stage = 'upload' | 'encode' | 'extract' | 'read'
export interface Word { w: string; s: number; e: number }

/** On-screen spelling for words the narrator says phonetically. */
const DISPLAY: Record<string, string> = { 'Eff-em-aright': 'fMRIght' }

function display(word: string): string {
  const m = word.match(/^(.*?)([.,:;?!]?)$/)
  const [core, punct] = m ? [m[1], m[2]] : [word, '']
  return (DISPLAY[core] ?? core) + punct
}

export function Mascot({ clip, size, style }: { clip: string; size: number; style?: CSSProperties }) {
  // Kling clips are 5 s; loop them under longer lines. A radial mask feathers
  // the square edge into the canvas.
  return (
    <div
      style={{
        width: size,
        height: size,
        WebkitMaskImage: 'radial-gradient(circle at 50% 50%, black 58%, transparent 71%)',
        maskImage: 'radial-gradient(circle at 50% 50%, black 58%, transparent 71%)',
        ...style,
      }}
    >
      <Video src={staticFile(`media/mascot/${clip}.mp4`)} muted loop style={{ width: '100%', height: '100%' }} />
    </div>
  )
}

/** Word-timed captions: one short phrase at a time, the spoken word in accent. */
export function Captions({ words, size = 44, maxWidth }: { words: Word[]; size?: number; maxWidth: number }) {
  const frame = useCurrentFrame()
  const { fps } = useVideoConfig()
  const t = frame / fps
  if (!words.length || t > words[words.length - 1].e + 0.6) return null

  // Phrases break after punctuation or every 7 words.
  const phrases: Word[][] = [[]]
  for (const w of words) {
    const cur = phrases[phrases.length - 1]
    cur.push(w)
    if (/[.,:;?!]$/.test(w.w) || cur.length >= 7) phrases.push([])
  }
  const live = phrases.filter(p => p.length)
  const idx = live.findIndex(p => t < p[p.length - 1].e + 0.15)
  const phrase = live[idx === -1 ? live.length - 1 : idx]

  return (
    <div style={{ maxWidth, fontFamily: FONT, fontSize: size, fontWeight: 500, lineHeight: 1.25, letterSpacing: -0.4, textAlign: 'center' }}>
      {phrase.map((w, i) => (
        <span key={i} style={{ color: t >= w.s && t < w.e + 0.1 ? C.accent : t >= w.s ? C.ink : 'rgba(242,242,240,0.35)' }}>
          {display(w.w)}{i < phrase.length - 1 ? ' ' : ''}
        </span>
      ))}
    </div>
  )
}

const STAGES: { key: Stage; label: string }[] = [
  { key: 'upload', label: 'Upload' },
  { key: 'encode', label: 'Encode' },
  { key: 'extract', label: 'Extract' },
  { key: 'read', label: 'Read' },
]

/** The scorer's app window from the site: chrome, stage rail, main pane. */
export function AppWindow({ stage, width, height, children }: { stage: Stage; width: number; height: number; children: ReactNode }) {
  const active = STAGES.findIndex(s => s.key === stage)
  return (
    <div style={{ width, height, background: C.elevated, borderRadius: 22, border: `1px solid ${C.line}`, overflow: 'hidden', display: 'flex', flexDirection: 'column', fontFamily: FONT }}>
      <div style={{ height: 44, flexShrink: 0, display: 'flex', alignItems: 'center', gap: 8, padding: '0 18px', borderBottom: `1px solid ${C.line}` }}>
        {[0, 1, 2].map(i => <span key={i} style={{ width: 11, height: 11, borderRadius: 6, background: '#242423' }} />)}
        <span style={{ marginLeft: 12, color: C.muted, fontSize: 15 }}>fMRIght scorer</span>
      </div>
      <div style={{ display: 'flex', gap: 8, padding: '14px 18px', flexShrink: 0 }}>
        {STAGES.map((s, i) => (
          <span
            key={s.key}
            style={{
              padding: '7px 16px',
              borderRadius: 999,
              fontSize: 16,
              fontWeight: 500,
              color: i === active ? C.accent : i < active ? C.ink : C.muted,
              background: i === active ? C.accentBg : C.fill,
            }}
          >
            {i < active ? '✓ ' : ''}{s.label}
          </span>
        ))}
      </div>
      <div style={{ flex: 1, position: 'relative' }}>{children}</div>
    </div>
  )
}

export function Phone({ width, children }: { width: number; children: ReactNode }) {
  return (
    <div style={{ width, height: (width * 16) / 9, borderRadius: width * 0.09, border: `6px solid ${C.ink2}`, overflow: 'hidden', background: '#000', position: 'relative' }}>
      {children}
    </div>
  )
}

export function Tag({ children, tone = 'muted' }: { children: ReactNode; tone?: 'muted' | 'amber' | 'accent' }) {
  const color = tone === 'amber' ? C.amber : tone === 'accent' ? C.accent : C.muted
  return (
    <span style={{ display: 'inline-block', padding: '6px 12px', borderRadius: 999, fontFamily: MONO, fontSize: 15, color, background: 'rgba(0,0,0,0.55)', border: `1px solid ${C.line}` }}>
      {children}
    </span>
  )
}

/**
 * Per-second response curve. `upTo` (seconds) reveals the line progressively
 * with a playhead; markers pin the result's peak and dip once revealed.
 */
export function ResponseChart({
  values,
  upTo,
  width,
  height,
  markers = [],
  warmup = 0,
}: {
  values: number[]
  upTo: number
  width: number
  height: number
  markers?: { second: number; label: string }[]
  /** Leading seconds shaded as fMRI signal lag rather than read as response. */
  warmup?: number
}) {
  const pad = { l: 16, r: 16, t: 24, b: 40 }
  const w = width - pad.l - pad.r
  const h = height - pad.t - pad.b
  const n = values.length
  const x = (s: number) => pad.l + (s / (n - 1)) * w
  const y = (v: number) => pad.t + (1 - v) * h
  const reveal = Math.max(0, Math.min(upTo, n - 1))

  const pts: [number, number][] = []
  for (let s = 0; s <= Math.floor(reveal); s++) pts.push([x(s), y(values[s])])
  const f0 = Math.floor(reveal)
  if (f0 < n - 1 && reveal > f0) {
    pts.push([x(reveal), y(values[f0] + (values[f0 + 1] - values[f0]) * (reveal - f0))])
  }
  const head = pts[pts.length - 1]

  return (
    <svg width={width} height={height} style={{ overflow: 'visible', fontFamily: MONO }}>
      {[0.25, 0.5, 0.75].map(g => (
        <line key={g} x1={pad.l} x2={pad.l + w} y1={pad.t + g * h} y2={pad.t + g * h} stroke={C.line} />
      ))}
      {warmup > 0 && n > 1 && (
        <g>
          <rect x={pad.l} y={pad.t} width={x(warmup) - pad.l} height={h} fill="rgba(255,255,255,0.045)" />
          <text x={pad.l + 10} y={pad.t + 22} fill={C.muted} fontSize={14}>warm-up · signal lags ~5 s</text>
        </g>
      )}
      <line x1={pad.l} x2={pad.l + w} y1={pad.t + h} y2={pad.t + h} stroke="rgba(255,255,255,0.18)" />
      {Array.from({ length: Math.floor((n - 1) / 5) + 1 }, (_, i) => i * 5).map(s => (
        <text key={s} x={x(s)} y={height - 12} fill={C.muted} fontSize={15} textAnchor="middle">0:{String(s).padStart(2, '0')}</text>
      ))}
      {pts.length > 1 && (
        <polyline points={pts.map(p => p.join(',')).join(' ')} fill="none" stroke={C.accent} strokeWidth={4} strokeLinejoin="round" strokeLinecap="round" />
      )}
      {head && upTo > 0 && upTo < n - 1 && <circle cx={head[0]} cy={head[1]} r={8} fill={C.accent} />}
      {markers.filter(m => m.second <= reveal).map(m => (
        <g key={m.label}>
          <line x1={x(m.second)} x2={x(m.second)} y1={pad.t} y2={pad.t + h} stroke="rgba(255,255,255,0.35)" strokeDasharray="4 6" />
          <circle cx={x(m.second)} cy={y(values[m.second])} r={7} fill={C.bg} stroke={C.ink} strokeWidth={3} />
        </g>
      ))}
    </svg>
  )
}

export function fadeIn(frame: number, start = 0, dur = 12): number {
  return interpolate(frame, [start, start + dur], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' })
}
