'use client'

import dynamic from 'next/dynamic'
import { useEffect, useRef, useState } from 'react'
import { useActivity, type CortexClock } from './CortexBrain'
import type { CortexView } from './CortexScene'

// three.js / r3f are client-only — load the scene without SSR.
const CortexScene = dynamic(() => import('./CortexScene'), { ssr: false })

const VIEW_LABELS: Record<CortexView, string> = {
  left: 'Left',
  right: 'Right',
  top: 'Top',
  front: 'Front',
  back: 'Back',
}

export default function CortexViewer() {
  const activity = useActivity()
  const clock = useRef<CortexClock>({ t: 0, playing: true, speed: 1 })
  const [view, setView] = useState<CortexView>('left')
  const [playing, setPlaying] = useState(true)
  const [t, setT] = useState(0)
  const [threshold, setThreshold] = useState(0.18)

  // Mirror the render-loop clock into the UI at 10 Hz.
  useEffect(() => {
    const id = setInterval(() => setT(clock.current.t), 100)
    return () => clearInterval(id)
  }, [])

  const duration = activity ? activity.meta.frames / activity.meta.hz : 0
  const illustrative = activity?.meta.source === 'illustrative'

  const togglePlay = () => {
    clock.current.playing = !clock.current.playing
    setPlaying(clock.current.playing)
  }

  return (
    <div className="relative h-[calc(100vh-3.5rem)] w-full overflow-hidden bg-background">
      <CortexScene activity={activity} clock={clock.current} view={view} threshold={threshold} />

      <div className="pointer-events-none absolute left-6 top-6 max-w-sm space-y-2">
        <p className="font-mono text-xs uppercase tracking-widest text-muted">
          fsaverage · cortical surface
        </p>
        <h1 className="text-2xl font-medium text-ink">{activity?.meta.label ?? 'Loading cortex…'}</h1>
        {activity && (
          <span
            className={`inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs ${
              illustrative
                ? 'bg-[#D97706]/15 text-[#FBBF24] ring-1 ring-[#D97706]/40'
                : 'bg-[#0093A3]/15 text-[#4AD8EC] ring-1 ring-[#4AD8EC]/30'
            }`}
          >
            {illustrative ? 'Illustrative — not model output' : 'TRIBE v2 prediction'}
          </span>
        )}
        {activity && <p className="text-xs leading-relaxed text-muted">{activity.meta.note}</p>}
      </div>

      <div className="absolute right-6 top-6 flex gap-1 rounded-full bg-white/5 p-1 ring-1 ring-white/10">
        {(Object.keys(VIEW_LABELS) as CortexView[]).map(v => (
          <button
            key={v}
            onClick={() => setView(v)}
            className={`rounded-full px-3 py-1 text-xs transition-colors ${
              view === v ? 'bg-white text-black' : 'text-muted hover:text-ink'
            }`}
          >
            {VIEW_LABELS[v]}
          </button>
        ))}
      </div>

      <div className="absolute inset-x-6 bottom-6 mx-auto flex max-w-2xl items-center gap-4 rounded-full bg-white/5 px-4 py-2 ring-1 ring-white/10 backdrop-blur">
        <button
          onClick={togglePlay}
          className="h-8 min-w-16 rounded-full bg-white px-3 text-xs font-medium text-black"
        >
          {playing ? 'Pause' : 'Play'}
        </button>
        <input
          type="range"
          min={0}
          max={duration || 1}
          step={0.05}
          value={t}
          onChange={e => {
            clock.current.t = Number(e.target.value)
            setT(clock.current.t)
          }}
          className="flex-1 accent-[#4AD8EC]"
          aria-label="Time"
        />
        <span className="w-20 text-right font-mono text-xs text-muted">
          {t.toFixed(1)} / {duration.toFixed(0)} s
        </span>
        <label className="flex items-center gap-2 font-mono text-xs text-muted">
          thr
          <input
            type="range"
            min={0}
            max={0.8}
            step={0.02}
            value={threshold}
            onChange={e => setThreshold(Number(e.target.value))}
            className="w-20 accent-[#4AD8EC]"
            aria-label="Activation threshold"
          />
        </label>
      </div>
    </div>
  )
}
