'use client'

import dynamic from 'next/dynamic'
import Image from 'next/image'
import { useCallback, useEffect, useRef, useState } from 'react'
import type { CortexClock } from '@/components/brain/CortexBrain'
import { HERO_SPIN, type HeroRig } from '@/components/brain/hero-rig'
import { usePrefersReducedMotion } from '@/lib/usePrefersReducedMotion'
// Build-time copy of the committed activity metadata, so the caption is in the
// server HTML and always describes the asset that actually ships.
import meta from '@/public/cortex/activity.json'

// three.js, r3f and the 4.8 MB mesh stay out of first paint: the scene module is
// only requested after the page is idle, and only on devices with WebGL2.
const CortexHeroScene = dynamic(() => import('@/components/brain/CortexHeroScene'), {
  ssr: false,
})

/** Second shown in the static fallback image and under reduced motion. */
const STILL_T = 12
/** Show only the stronger predicted responses so the folds stay readable. */
const THRESHOLD = 0.4
const YAW0 = Math.PI * 0.7 // left hemisphere, three-quarter front
// Still of the live scene at YAW0 / STILL_T, captured from this component under
// reduced motion. Re-capture it whenever activity.* or the framing changes
// (docs/CORTEX-VIEW.md, "Hero fallback still").
const FALLBACK_SRC = '/cortex/cortex-hero.webp'

const DURATION = meta.frames / meta.hz
const ILLUSTRATIVE = meta.source !== 'tribe'
const POINTS = meta.vertices.toLocaleString('en-US')
// Non-breaking hyphens keep "(AI-generated)" on one line at phone widths.
const LABEL = meta.label.replace(/-/g, '\u2011')

function canRender3d(): boolean {
  const conn = (navigator as Navigator & { connection?: { saveData?: boolean } }).connection
  if (conn?.saveData) return false
  try {
    const gl = document.createElement('canvas').getContext('webgl2')
    gl?.getExtension('WEBGL_lose_context')?.loseContext()
    return gl !== null
  } catch {
    return false
  }
}

export default function CortexHero() {
  const reduced = usePrefersReducedMotion()
  const [want3d, setWant3d] = useState(false)
  const [no3d, setNo3d] = useState(false)
  const [ready, setReady] = useState(false)
  const [paused, setPaused] = useState(false)
  const [visible, setVisible] = useState(true)

  const clock = useRef<CortexClock>({ t: STILL_T, playing: true, speed: 1 })
  const rig = useRef<HeroRig>({ yaw: YAW0, pitch: 0, vel: HERO_SPIN, dragging: false, spin: true })
  const figureRef = useRef<HTMLElement>(null)
  const timeRef = useRef<HTMLSpanElement>(null)
  const barRef = useRef<HTMLSpanElement>(null)
  const drag = useRef<{ id: number; x: number; y: number; t: number; touch: boolean } | null>(null)

  const still = reduced || paused

  // Load the 3D scene once the page is idle.
  useEffect(() => {
    if (!canRender3d()) {
      setNo3d(true) // the still stays; hide the playback control
      return
    }
    const start = () => setWant3d(true)
    if ('requestIdleCallback' in window) {
      const id = window.requestIdleCallback(start, { timeout: 1500 })
      return () => window.cancelIdleCallback(id)
    }
    const id = setTimeout(start, 300)
    return () => clearTimeout(id)
  }, [])

  // Stop rendering while the hero is scrolled out of view.
  useEffect(() => {
    const el = figureRef.current
    if (!el) return
    const io = new IntersectionObserver(([entry]) => setVisible(entry.isIntersecting), {
      rootMargin: '120px',
    })
    io.observe(el)
    return () => io.disconnect()
  }, [])

  // Reduced motion: no spin, no playback, one representative second.
  useEffect(() => {
    if (reduced) clock.current.t = STILL_T
    clock.current.playing = !still
    rig.current.spin = !still
    if (still) rig.current.vel = 0
    rig.current.invalidate?.()
  }, [reduced, still])

  // Mirror the render-loop clock into the readout without re-rendering React.
  useEffect(() => {
    if (still || !visible) {
      if (timeRef.current) timeRef.current.textContent = clock.current.t.toFixed(1)
      if (barRef.current) barRef.current.style.transform = `scaleX(${clock.current.t / DURATION})`
      return
    }
    const id = setInterval(() => {
      const t = clock.current.t
      if (timeRef.current) timeRef.current.textContent = t.toFixed(1)
      if (barRef.current) barRef.current.style.transform = `scaleX(${t / DURATION})`
    }, 100)
    return () => clearInterval(id)
  }, [still, visible])

  const onReady = useCallback(() => setReady(true), [])

  // Drag to turn. Vertical touch moves stay with the page (touch-action: pan-y);
  // the wheel is never captured.
  const onPointerDown = (e: React.PointerEvent<HTMLDivElement>) => {
    if (!ready || drag.current || (e.pointerType === 'mouse' && e.button !== 0)) return
    try {
      e.currentTarget.setPointerCapture(e.pointerId)
    } catch {
      return // stale or synthetic pointer: leave the spin alone
    }
    drag.current = { id: e.pointerId, x: e.clientX, y: e.clientY, t: e.timeStamp, touch: e.pointerType !== 'mouse' }
    rig.current.dragging = true
    rig.current.vel = 0
  }
  const onPointerMove = (e: React.PointerEvent<HTMLDivElement>) => {
    const d = drag.current
    if (!d || e.pointerId !== d.id) return // one finger drives the turn
    const r = rig.current
    const dx = (e.clientX - d.x) * 0.008
    const dt = Math.max((e.timeStamp - d.t) / 1000, 1 / 120)
    r.yaw += dx
    if (!d.touch) r.pitch = Math.max(-0.35, Math.min(0.35, r.pitch + (e.clientY - d.y) * 0.004))
    r.vel = still ? 0 : 0.6 * r.vel + 0.4 * (dx / dt)
    drag.current = { ...d, x: e.clientX, y: e.clientY, t: e.timeStamp }
    r.invalidate?.()
  }
  const endDrag = (e: React.PointerEvent<HTMLDivElement>) => {
    if (!drag.current || e.pointerId !== drag.current.id) return
    drag.current = null
    rig.current.dragging = false
    rig.current.vel = Math.max(-2, Math.min(2, rig.current.vel))
  }

  const frameloop = !visible ? 'never' : still ? 'demand' : 'always'

  return (
    <figure ref={figureRef} className="relative w-full">
      <div
        role="img"
        aria-label={`3D cortex, both hemispheres, showing ${
          ILLUSTRATIVE ? 'an illustrative activity sequence' : 'the TRIBE v2 predicted response'
        } second by second. Drag sideways to turn it.`}
        className={`relative aspect-[1.2/1] w-full select-none lg:aspect-auto lg:h-[min(620px,calc(100svh-230px))] ${
          ready ? 'cursor-grab active:cursor-grabbing' : ''
        }`}
        style={{ touchAction: 'pan-y' }}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={endDrag}
        onPointerCancel={endDrag}
        onLostPointerCapture={endDrag}
      >
        <Image
          src={FALLBACK_SRC}
          alt=""
          fill
          priority
          sizes="(min-width: 1024px) 720px, 100vw"
          className={`object-contain transition-opacity duration-700 ${ready ? 'opacity-0' : 'opacity-100'}`}
        />
        {want3d && (
          <div className={`absolute inset-0 transition-opacity duration-700 ${ready ? 'opacity-100' : 'opacity-0'}`}>
            <CortexHeroScene
              clock={clock.current}
              rig={rig.current}
              frameloop={frameloop}
              threshold={THRESHOLD}
              onReady={onReady}
            />
          </div>
        )}
      </div>

      <figcaption className="mx-auto mt-2 max-w-[560px] px-1 lg:mt-4">
        <div className="flex items-center gap-3">
          {!no3d && (
            <button
              type="button"
              onClick={() => setPaused(p => !p)}
              disabled={reduced}
              aria-label={still ? 'Play the cortex animation' : 'Pause the cortex animation'}
              className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-fill text-ink shadow-[var(--shadow-hairline)] transition-colors hover:bg-btn-2 disabled:opacity-40"
            >
              {still ? (
                <svg viewBox="0 0 12 12" className="h-2.5 w-2.5" fill="currentColor" aria-hidden>
                  <path d="M3 1.5v9l7.5-4.5z" />
                </svg>
              ) : (
                <svg viewBox="0 0 12 12" className="h-2.5 w-2.5" fill="currentColor" aria-hidden>
                  <path d="M2.5 1.5h2.5v9H2.5zM7 1.5h2.5v9H7z" />
                </svg>
              )}
            </button>
          )}
          <span className="relative h-px flex-1 overflow-hidden bg-line" aria-hidden>
            <span
              ref={barRef}
              className="absolute inset-0 origin-left bg-accent"
              style={{ transform: `scaleX(${STILL_T / DURATION})` }}
            />
          </span>
          <span className="shrink-0 font-mono text-[12px] tabular-nums text-muted">
            <span ref={timeRef}>{STILL_T.toFixed(1)}</span> / {DURATION} s
          </span>
        </div>

        <p className="mt-3 text-[13px] leading-5 text-ink/80">
          {ILLUSTRATIVE ? (
            <span className="mr-2 inline-flex rounded-full bg-[#D97706]/15 px-2 py-0.5 text-[11px] font-medium text-[#FBBF24] ring-1 ring-[#D97706]/40">
              Illustrative, not model output
            </span>
          ) : (
            'TRIBE v2 prediction for a '
          )}
          {ILLUSTRATIVE ? LABEL : LABEL.charAt(0).toLowerCase() + LABEL.slice(1)}
        </p>
        <p className="mt-1 font-mono text-[11px] leading-[18px] text-muted">
          {POINTS} cortical points · {meta.hz} frame/s · cyan marks the stronger predicted responses ·
          a model prediction for an average viewer, not a recorded scan
        </p>
      </figcaption>
    </figure>
  )
}
