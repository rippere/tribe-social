'use client'

import { useCallback, useEffect, useState } from 'react'
import {
  DEMO_CALLOUTS,
  DEMO_CLIP,
  DEMO_STAGES,
  DEMO_TIMELINE,
  IS_SAMPLE,
} from './demo-data'

const LAST = DEMO_STAGES.length - 1

function usePrefersReducedMotion(): boolean {
  const [reduced, setReduced] = useState(false)
  useEffect(() => {
    const mq = window.matchMedia('(prefers-reduced-motion: reduce)')
    setReduced(mq.matches)
    const onChange = () => setReduced(mq.matches)
    mq.addEventListener('change', onChange)
    return () => mq.removeEventListener('change', onChange)
  }, [])
  return reduced
}

export default function HeroDemo() {
  const reducedMotion = usePrefersReducedMotion()
  const [index, setIndex] = useState(0)
  const [runId, setRunId] = useState(0)
  const done = index === LAST
  const stage = DEMO_STAGES[index]

  useEffect(() => {
    if (reducedMotion) {
      setIndex(LAST)
      return
    }
    if (index >= LAST) return
    const t = setTimeout(() => setIndex(i => Math.min(i + 1, LAST)), DEMO_STAGES[index].duration)
    return () => clearTimeout(t)
  }, [index, runId, reducedMotion])

  const replay = useCallback(() => {
    setIndex(0)
    setRunId(r => r + 1)
  }, [])

  return (
    <div className="mx-auto w-full max-w-[976px] overflow-hidden rounded-[22px] bg-elevated text-left shadow-[var(--shadow-window),var(--shadow-hairline)]">
      {/* Window chrome */}
      <div className="flex h-11 items-center justify-between border-b border-line px-4">
        <div className="flex items-center gap-2">
          <span className="h-3 w-3 rounded-full bg-[#FF5F57]" />
          <span className="h-3 w-3 rounded-full bg-[#FEBC2E]" />
          <span className="h-3 w-3 rounded-full bg-[#28C840]" />
          <span className="ml-3 text-[13px] text-muted">
            {DEMO_CLIP.title} · 0:{String(DEMO_CLIP.seconds).padStart(2, '0')}
          </span>
          {IS_SAMPLE && (
            <span className="ml-1 rounded-full bg-accent-bg px-2 py-0.5 text-[11px] font-medium text-accent">
              Sample data
            </span>
          )}
        </div>
        <button
          type="button"
          onClick={replay}
          disabled={!done}
          className="rounded-full px-3 py-1 text-[13px] text-ink transition-opacity hover:bg-fill disabled:opacity-0"
        >
          Replay
        </button>
      </div>

      <div className="grid md:grid-cols-[200px_1fr]">
        {/* Stage rail */}
        <ol className="flex gap-1 border-b border-line p-3 md:flex-col md:border-b-0 md:border-r">
          {DEMO_STAGES.map((s, i) => {
            const state = i < index ? 'done' : i === index ? 'active' : 'todo'
            return (
              <li
                key={s.key}
                className={`flex flex-1 items-center gap-2.5 rounded-xl px-3 py-2 text-[13px] transition-colors md:flex-none ${
                  state === 'active' ? 'bg-fill text-ink' : state === 'done' ? 'text-ink' : 'text-muted'
                }`}
              >
                <span
                  className={`flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-[11px] ${
                    state === 'todo' ? 'bg-fill text-muted' : 'bg-ink text-on-ink'
                  }`}
                  aria-hidden
                >
                  {state === 'done' ? '✓' : i + 1}
                </span>
                <span className="font-medium">{s.label}</span>
                {state === 'active' && !done && (
                  <span className="ml-auto hidden h-1.5 w-1.5 animate-pulse rounded-full bg-accent md:block" />
                )}
              </li>
            )
          })}
        </ol>

        <div className="grid gap-4 p-4 md:p-5">
          <div className="grid gap-4 md:grid-cols-[1fr_1.1fr]">
            {/* Clip being scored (the full 3D cortex lives on the processing page) */}
            <VideoPane stageIndex={index} done={done} />

            {/* Plain-language explainer for the active stage */}
            <div key={`${stage.key}-${runId}`} className="flex flex-col justify-center rounded-2xl bg-fill p-5 animate-in fade-in duration-500">
              <p className="text-[12px] font-medium uppercase tracking-wide text-muted">
                Step {index + 1} of {DEMO_STAGES.length}
              </p>
              <h3 className="mt-2 text-[18px] font-medium leading-6 text-ink">{stage.heading}</h3>
              <p className="mt-2 text-[14px] leading-[22px] text-ink/70">{stage.body}</p>
            </div>
          </div>

          <Timeline revealed={done} />
        </div>
      </div>
    </div>
  )
}

function VideoPane({ stageIndex, done }: { stageIndex: number; done: boolean }) {
  return (
    <div className="relative flex h-[240px] items-center justify-center overflow-hidden rounded-2xl bg-panel">
      <div className="relative h-[208px] w-[117px] overflow-hidden rounded-xl bg-gradient-to-b from-[#2A2F36] to-[#15171A] shadow-[var(--shadow-inner)]">
        <span className="absolute inset-x-0 top-1/2 -translate-y-1/2 text-center text-[11px] text-ink/60">
          {DEMO_CLIP.title}
        </span>
        {/* Scan line while the model is reading the clip */}
        {!done && stageIndex > 0 && (
          <span className="absolute inset-x-0 h-8 animate-pulse bg-gradient-to-b from-transparent via-accent/25 to-transparent" style={{ top: `${20 + stageIndex * 22}%` }} />
        )}
        <span className="absolute bottom-2 left-2 rounded-full bg-black/50 px-1.5 py-0.5 font-mono text-[10px] text-ink/80">
          0:{String(DEMO_CLIP.seconds).padStart(2, '0')}
        </span>
      </div>
      <span className="pointer-events-none absolute bottom-3 left-3 text-[11px] text-muted">Your video</span>
    </div>
  )
}

function Timeline({ revealed }: { revealed: boolean }) {
  const W = 640
  const H = 120
  const PAD = 8
  const n = DEMO_TIMELINE.length
  const x = (i: number) => PAD + (i / (n - 1)) * (W - PAD * 2)
  const y = (v: number) => H - PAD - v * (H - PAD * 2)
  const path = DEMO_TIMELINE.map((v, i) => `${i === 0 ? 'M' : 'L'}${x(i).toFixed(1)} ${y(v).toFixed(1)}`).join(' ')
  const area = `${path} L${x(n - 1)} ${H} L${x(0)} ${H} Z`

  return (
    <div className="rounded-2xl border border-line p-4">
      <div className="flex items-baseline justify-between">
        <p className="text-[13px] font-medium text-ink">Predicted attention, second by second</p>
        <p className="font-mono text-[11px] text-muted">0:00 – 0:{String(n).padStart(2, '0')}</p>
      </div>

      <div className="relative mt-3">
        <svg viewBox={`0 0 ${W} ${H}`} className="h-[120px] w-full" preserveAspectRatio="none" aria-hidden>
          <line x1={x(3)} x2={x(3)} y1={0} y2={H} stroke="var(--line)" strokeDasharray="3 4" />
          <path d={area} fill="var(--accent)" opacity={revealed ? 0.08 : 0} className="transition-opacity duration-700" />
          {/* Left-to-right reveal; a clip keeps it exact when the chart stretches */}
          <g style={{ clipPath: revealed ? 'inset(0 0 0 0)' : 'inset(0 100% 0 0)', transition: 'clip-path 2.4s ease-out' }}>
            <path d={path} fill="none" stroke="var(--ink)" strokeWidth={2} vectorEffect="non-scaling-stroke" />
          </g>
        </svg>

        {revealed &&
          DEMO_CALLOUTS.map(c => (
            <span
              key={c.second}
              className="absolute -translate-x-1/2 whitespace-nowrap rounded-full bg-ink px-2.5 py-1 text-[11px] text-on-ink animate-in fade-in duration-700"
              style={{
                left: `${(x(c.second) / W) * 100}%`,
                top: `${Math.max(0, (y(DEMO_TIMELINE[c.second]) / H) * 100 - 34)}%`,
              }}
            >
              {c.text}
            </span>
          ))}

        {!revealed && (
          <p className="absolute inset-0 flex items-center justify-center text-[13px] text-muted">
            The read appears when scoring finishes
          </p>
        )}
      </div>

      <p className="mt-2 text-[11px] text-muted">
        Dashed line: the first 3 seconds, the hook window our study measures.
      </p>
    </div>
  )
}
