'use client'

import dynamic from 'next/dynamic'
import { useCallback, useEffect, useRef, useState } from 'react'
import type { CortexClock } from '@/components/brain/CortexBrain'
import { HERO_SPIN, type HeroRig } from '@/components/brain/hero-rig'
import { REGION_LABELS } from '@/components/brain/contract'
import ClipChat from '@/components/clips/ClipChat'
import { clock as mmss, REGION_KEYS, type Clip, type ClipRegion } from '@/lib/clips'
import { usePrefersReducedMotion } from '@/lib/usePrefersReducedMotion'

const CortexHeroScene = dynamic(() => import('@/components/brain/CortexHeroScene'), { ssr: false })

const THRESHOLD = 0.4
// Same hues as the --color-roi-* theme tokens (globals.css); Tailwind only emits
// those variables when a utility uses them, so the chart reads them from here.
const ROI_COLOR: Record<ClipRegion, string> = {
  attention: '#4FC3F7',
  social: '#81C784',
  language: '#CE93D8',
  valuation: '#FFB74D',
  auditory: '#F48FB1',
  motion: '#80DEEA',
  narrative: '#B0BEC5',
}
const YAW0 = Math.PI * 0.7

/**
 * One scored clip: the video drives the cortex and the timeline (the video's
 * currentTime is the single clock), and the chat can seek all three.
 */
export default function ClipWorkspace({ clip }: { clip: Clip }) {
  const reduced = usePrefersReducedMotion()
  const videoRef = useRef<HTMLVideoElement>(null)
  const cortexClock = useRef<CortexClock>({ t: 0, playing: false, speed: 1 })
  const rig = useRef<HeroRig>({ yaw: YAW0, pitch: 0, vel: HERO_SPIN, dragging: false, spin: true })
  const [t, setT] = useState(0)
  const [ready, setReady] = useState(false)
  const [region, setRegion] = useState<ClipRegion>('attention')

  const last = clip.context.seconds - 0.001

  // The video is the clock: copy its time into the cortex every frame, and into
  // React state when the tenth of a second changes.
  useEffect(() => {
    let id = 0
    let shown = -1
    const tick = () => {
      const v = videoRef.current
      if (v) {
        const now = Math.min(v.currentTime, last)
        cortexClock.current.t = now
        const tenth = Math.round(now * 10)
        if (tenth !== shown) {
          shown = tenth
          setT(now)
        }
      }
      id = requestAnimationFrame(tick)
    }
    id = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(id)
  }, [last])

  // Hosts that ignore Range requests (e.g. *.pages.dev) make a streamed video
  // unseekable, and seeking is the point of this page. The clip is a few MB, so load
  // it whole and play it from memory, keeping the viewer's place if it was playing.
  useEffect(() => {
    let url: string | null = null
    let cancelled = false
    fetch(clip.video)
      .then(r => (r.ok ? r.blob() : Promise.reject(new Error(String(r.status)))))
      .then(blob => {
        const v = videoRef.current
        if (cancelled || !v) return
        url = URL.createObjectURL(blob)
        const at = v.currentTime
        const playing = !v.paused
        v.src = url
        v.currentTime = at
        if (playing) v.play().catch(() => {})
      })
      .catch(() => {}) // keep the streamed source
    return () => {
      cancelled = true
      if (url) URL.revokeObjectURL(url)
    }
  }, [clip.video])

  useEffect(() => {
    rig.current.spin = !reduced
    if (reduced) rig.current.vel = 0
  }, [reduced])

  const seek = useCallback(
    (s: number) => {
      const v = videoRef.current
      if (!v) return
      v.currentTime = Math.max(0, Math.min(s, v.duration || s))
      v.scrollIntoView({ block: 'nearest', behavior: reduced ? 'auto' : 'smooth' })
    },
    [reduced],
  )

  const onReady = useCallback(() => setReady(true), [])

  const sec = Math.min(Math.floor(t), clip.context.seconds - 1)
  const shotIdx = clip.context.timeline.findIndex(s => t >= s.from && t < s.to)
  const z = clip.context.regions[region].vs_cortex_z[sec]

  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_400px]">
      <div className="min-w-0 space-y-4">
        <div className="grid grid-cols-2 gap-3 rounded-[22px] sm:grid-cols-[minmax(0,2fr)_minmax(0,3fr)] bg-elevated p-3 shadow-[var(--shadow-window),var(--shadow-hairline)]">
          <video
            ref={videoRef}
            src={clip.video}
            poster={clip.poster}
            controls
            playsInline
            preload="metadata"
            aria-label={`${clip.title}: the clip TRIBE v2 scored`}
            className="aspect-[9/16] w-full rounded-[16px] bg-ink-2 object-cover"
          />
          <div className="relative min-h-0">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src="/cortex/cortex-hero.webp"
              alt=""
              aria-hidden
              className={`absolute inset-0 h-full w-full object-contain transition-opacity duration-700 ${ready ? 'opacity-0' : 'opacity-100'}`}
            />
            <div
              role="img"
              aria-label="3D cortex showing TRIBE v2's predicted response at the video's current second"
              className={`absolute inset-0 transition-opacity duration-700 ${ready ? 'opacity-100' : 'opacity-0'}`}
            >
              <CortexHeroScene
                clock={cortexClock.current}
                rig={rig.current}
                frameloop="always"
                threshold={THRESHOLD}
                onReady={onReady}
                base={clip.cortexBase}
              />
            </div>
            <p className="absolute right-1 bottom-1 left-1 text-center font-mono text-[11px] text-muted">
              {mmss(t)} · cyan = stronger predicted response
            </p>
          </div>
        </div>

        <Timeline clip={clip} t={t} region={region} onRegion={setRegion} onSeek={seek} />

        <p className="px-1 text-[13px] leading-5 text-muted">
          <span className="font-mono text-ink">{mmss(t)}</span>
          {shotIdx >= 0 && <> · shot {shotIdx + 1}</>} · {REGION_LABELS[region]}{' '}
          <span className="font-mono text-ink">
            {z >= 0 ? '+' : ''}
            {z.toFixed(2)}
          </span>{' '}
          SD vs. the whole cortex
        </p>
      </div>

      <ClipChat
        clip={clip}
        onSeek={seek}
        className="lg:sticky lg:top-20 lg:h-[calc(100svh-6rem)] lg:max-h-[760px]"
      />
    </div>
  )
}

const SHOT_NAMES = ['Hook', 'Middle', 'Payoff']

/** Per-second region response (vs. whole cortex) over the clip, with shots and a playhead. */
function Timeline({
  clip,
  t,
  region,
  onRegion,
  onSeek,
}: {
  clip: Clip
  t: number
  region: ClipRegion
  onRegion: (r: ClipRegion) => void
  onSeek: (s: number) => void
}) {
  const { seconds, timeline, regions, whole_cortex } = clip.context
  const W = 1000
  const H = 160
  const pad = { top: 22, bottom: 18 }
  // Sample i covers second [i, i+1); plot it at its middle so the playhead (video time)
  // and the samples share one axis that spans the whole clip.
  const x = (s: number) => (s / seconds) * W
  const zMax = 2.5
  const y = (v: number) =>
    pad.top + ((zMax - Math.max(-zMax, Math.min(zMax, v))) / (2 * zMax)) * (H - pad.top - pad.bottom)
  const line = regions[region].vs_cortex_z
    .map((v, i) => `${i ? 'L' : 'M'}${x(i + 0.5).toFixed(1)},${y(v).toFixed(1)}`)
    .join('')

  const gfp = whole_cortex.global_field_power_per_second
  const gMin = Math.min(...gfp)
  const gSpan = Math.max(...gfp) - gMin || 1
  const base = H - pad.bottom
  const area =
    `M0,${base}` +
    gfp.map((g, i) => `L${x(i + 0.5).toFixed(1)},${(base - 4 - ((g - gMin) / gSpan) * 44).toFixed(1)}`).join('') +
    `L${W},${base}Z`

  const onClick = (e: React.MouseEvent<SVGSVGElement>) => {
    const r = e.currentTarget.getBoundingClientRect()
    onSeek(((e.clientX - r.left) / r.width) * seconds)
  }

  return (
    <div className="rounded-[22px] bg-elevated p-4 shadow-[var(--shadow-hairline)] md:p-5">
      <div className="flex flex-wrap gap-1.5" role="group" aria-label="Region to plot">
        {REGION_KEYS.map(k => (
          <button
            key={k}
            type="button"
            aria-pressed={k === region}
            onClick={() => onRegion(k)}
            className={`flex cursor-pointer items-center gap-1.5 rounded-full px-2.5 py-1.5 text-[12px] transition-colors ${
              k === region ? 'bg-accent-bg text-accent' : 'bg-fill text-ink/70 hover:text-ink'
            }`}
          >
            <span aria-hidden className="h-2 w-2 rounded-full" style={{ background: ROI_COLOR[k] }} />
            {REGION_LABELS[k]}
          </button>
        ))}
      </div>

      <div className="relative mt-4 h-4 text-[11px] text-muted" aria-hidden>
        {timeline.map((s, i) => (
          <span key={i} className="absolute top-0" style={{ left: `calc(${(x(s.from) / W) * 100}% + 6px)` }}>
            {SHOT_NAMES[i] ?? `Shot ${i + 1}`}
          </span>
        ))}
      </div>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        preserveAspectRatio="none"
        className="-mt-4 h-[160px] w-full cursor-pointer"
        onClick={onClick}
        role="img"
        aria-label={`${REGION_LABELS[region]}: predicted response relative to the whole cortex, per second. Click to jump the video.`}
      >
        {timeline.map((s, i) => (
          <g key={i}>
            <rect
              x={x(s.from)}
              y={0}
              width={x(Math.min(s.to, seconds)) - x(s.from)}
              height={H}
              fill={i % 2 ? 'rgba(255,255,255,0.03)' : 'transparent'}
            />
          </g>
        ))}
        <path d={area} fill="rgba(255,255,255,0.06)" />
        <line
          x1={0}
          x2={W}
          y1={y(0)}
          y2={y(0)}
          stroke="var(--line)"
          strokeDasharray="4 6"
          vectorEffect="non-scaling-stroke"
        />
        <path
          d={line}
          fill="none"
          stroke={ROI_COLOR[region]}
          strokeWidth={2.5}
          vectorEffect="non-scaling-stroke"
          strokeLinejoin="round"
        />
        <line x1={x(t)} x2={x(t)} y1={0} y2={H} stroke="var(--ink)" strokeWidth={1.5} vectorEffect="non-scaling-stroke" />
      </svg>
      <label className="sr-only" htmlFor={`seek-${clip.slug}`}>
        Jump the video to a second
      </label>
      <input
        id={`seek-${clip.slug}`}
        type="range"
        min={0}
        max={seconds - 1}
        step={1}
        value={Math.min(Math.floor(t), seconds - 1)}
        aria-valuetext={mmss(t)}
        onChange={e => onSeek(Number(e.target.value))}
        className="sr-only focus:not-sr-only focus:mt-2 focus:block focus:w-full"
      />
      <div className="mt-1 flex justify-between gap-2 font-mono text-[11px] text-muted">
        <span>0:00</span>
        <span className="hidden truncate sm:inline">dashed = cortex average · grey = overall drive</span>
        <span>{mmss(seconds)}</span>
      </div>
    </div>
  )
}
