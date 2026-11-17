'use client'

import dynamic from 'next/dynamic'
import { useEffect, useRef, useState } from 'react'
import type { Activity, CortexClock } from '@/components/brain/CortexBrain'
import type { CortexView } from '@/components/brain/CortexScene'

// three.js / r3f are client-only.
const CortexScene = dynamic(() => import('@/components/brain/CortexScene'), { ssr: false })

const VIEWS: CortexView[] = ['left', 'right', 'top', 'front', 'back']

interface Props {
  token: string
  frames: number
  label: string
}

/** The trial's cortex view: this clip's TRIBE v2 activity, fetched with the result token. */
export default function TrialCortex({ token, frames, label }: Props) {
  const [activity, setActivity] = useState<Activity | null>(null)
  const [failed, setFailed] = useState(false)
  const clock = useRef<CortexClock>({ t: 0, playing: true, speed: 1 })
  const [playing, setPlaying] = useState(true)
  const [t, setT] = useState(0)
  const [view, setView] = useState<CortexView>('left')

  useEffect(() => {
    let alive = true
    fetch('/api/trial/activity', { headers: { authorization: `Bearer ${token}` } })
      .then((r) => (r.ok ? r.arrayBuffer() : Promise.reject(new Error(String(r.status)))))
      .then((buf) => {
        if (!alive) return
        const data = new Uint8Array(buf)
        setActivity({
          meta: {
            frames: Math.floor(data.length / 20484) || frames,
            vertices: 20484,
            hz: 1,
            source: 'tribe',
            label,
            note: 'TRIBE v2 predicted cortical response (fsaverage5), 1 frame per second.',
          },
          data,
        })
      })
      .catch(() => alive && setFailed(true))
    return () => {
      alive = false
    }
  }, [token, frames, label])

  useEffect(() => {
    const id = setInterval(() => setT(clock.current.t), 100)
    return () => clearInterval(id)
  }, [])

  const duration = activity ? activity.meta.frames / activity.meta.hz : frames

  if (failed) {
    return <p className="py-10 text-center text-[13px] text-muted">The cortex view could not be loaded.</p>
  }

  return (
    <div>
      <div className="relative h-[320px] overflow-hidden rounded-xl bg-background md:h-[380px]" data-testid="trial-cortex">
        {activity ? (
          <CortexScene activity={activity} clock={clock.current} view={view} />
        ) : (
          <p className="flex h-full items-center justify-center text-[13px] text-muted">Loading the cortex view…</p>
        )}
        <div className="absolute right-3 top-3 flex gap-1 rounded-full bg-white/5 p-1 ring-1 ring-white/10">
          {VIEWS.map((v) => (
            <button
              key={v}
              type="button"
              onClick={() => setView(v)}
              className={`rounded-full px-2.5 py-1 text-[11px] capitalize transition-colors ${
                view === v ? 'bg-white text-black' : 'text-muted hover:text-ink'
              }`}
            >
              {v}
            </button>
          ))}
        </div>
      </div>
      <div className="mt-3 flex items-center gap-3">
        <button
          type="button"
          onClick={() => {
            clock.current.playing = !clock.current.playing
            setPlaying(clock.current.playing)
          }}
          className="btn-secondary btn-sm min-w-16"
        >
          {playing ? 'Pause' : 'Play'}
        </button>
        <input
          type="range"
          min={0}
          max={duration || 1}
          step={0.05}
          value={t}
          onChange={(e) => {
            clock.current.t = Number(e.target.value)
            setT(clock.current.t)
          }}
          className="flex-1 accent-[#4AD8EC]"
          aria-label="Time"
        />
        <span className="w-20 text-right font-mono text-[12px] text-muted">
          {t.toFixed(1)} / {duration.toFixed(0)} s
        </span>
      </div>
    </div>
  )
}
