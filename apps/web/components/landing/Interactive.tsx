'use client'

import { useEffect, useRef, useState } from 'react'

const FAQS = [
  {
    q: 'What is fMRI?',
    a: 'A brain scan that tracks blood flow to show which parts of the brain are working. fMRIght doesn’t scan anyone. It uses a model that learned from fMRI scans.',
  },
  {
    q: 'Does this predict views or virality?',
    a: 'No. It predicts how an average brain responds to a video. Whether that relates to views is exactly what our current study is testing.',
  },
  {
    q: 'How accurate is it?',
    a: 'For this use, we don’t know yet. Our pilot found a weak relationship that wasn’t statistically significant (r = 0.25, p = 0.24, 24 videos). The pre-registered hook test will give a clearer answer.',
  },
  {
    q: 'Whose brain is it predicting?',
    a: 'An average of the people in the scan data the model learned from, not your audience specifically.',
  },
  {
    q: 'What happens to my video?',
    a: 'It’s sent to a rented cloud GPU to be scored, and fMRIght doesn’t keep the video file. The resulting scores are saved to our research dataset. Only upload videos you have the rights to.',
  },
  {
    q: 'Can I use it for commercial work?',
    a: 'Not yet. TRIBE v2 is licensed for non-commercial use only, so fMRIght is a research preview.',
  },
]

export function Faq() {
  const [open, setOpen] = useState<number | null>(0)

  return (
    <section id="faq" className="mx-auto grid max-w-[976px] gap-10 px-6 pt-32 md:grid-cols-[1fr_1.4fr]">
      <h2 className="type-h2 text-ink">FAQs</h2>
      <div>
        {FAQS.map((f, i) => {
          const isOpen = open === i
          return (
            <div key={f.q} className="border-b border-line">
              <button
                type="button"
                aria-expanded={isOpen}
                onClick={() => setOpen(isOpen ? null : i)}
                className="flex w-full items-center justify-between gap-6 py-4 text-left text-[16px] text-ink"
              >
                {f.q}
                <span aria-hidden className="text-[20px] leading-none text-muted">{isOpen ? '×' : '+'}</span>
              </button>
              {isOpen && <p className="pb-5 text-[15px] leading-6 text-ink/70">{f.a}</p>}
            </div>
          )
        })}
      </div>
    </section>
  )
}

const mmss = (t: number) => `${Math.floor(t / 60)}:${String(Math.floor(t % 60)).padStart(2, '0')}`

/**
 * The demo video with its controls under the frame, not over it. Native controls
 * cover the bottom of the picture, where the explainer puts its captions and the
 * mascot, so they only come back in fullscreen.
 */
export function DemoVideo({ src, poster, label }: { src: string; poster: string; label: string }) {
  const ref = useRef<HTMLVideoElement>(null)
  const [playing, setPlaying] = useState(false)
  const [started, setStarted] = useState(false)
  const [muted, setMuted] = useState(false)
  const [t, setT] = useState(0)
  const [duration, setDuration] = useState(0)
  const [fullscreen, setFullscreen] = useState(false)

  useEffect(() => {
    const onChange = () => setFullscreen(document.fullscreenElement === ref.current)
    document.addEventListener('fullscreenchange', onChange)
    return () => document.removeEventListener('fullscreenchange', onChange)
  }, [])

  const toggle = () => {
    const v = ref.current
    if (!v) return
    if (v.paused) void v.play()
    else v.pause()
  }
  const goFullscreen = () => {
    const v = ref.current as (HTMLVideoElement & { webkitEnterFullscreen?: () => void }) | null
    if (!v) return
    if (v.requestFullscreen) void v.requestFullscreen()
    else v.webkitEnterFullscreen?.() // iOS Safari
  }

  const iconBtn =
    'flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-fill text-ink shadow-[var(--shadow-hairline)] transition-colors hover:bg-btn-2'

  return (
    <figure className="mt-10">
      <div className="relative overflow-hidden rounded-[24px] bg-ink-2">
        <video
          ref={ref}
          className="block aspect-video w-full cursor-pointer"
          src={src}
          poster={poster}
          controls={fullscreen}
          playsInline
          preload="metadata"
          aria-label={label}
          onClick={toggle}
          onPlay={() => {
            setPlaying(true)
            setStarted(true)
          }}
          onPause={() => setPlaying(false)}
          onTimeUpdate={e => setT(e.currentTarget.currentTime)}
          onLoadedMetadata={e => setDuration(e.currentTarget.duration)}
          onVolumeChange={e => setMuted(e.currentTarget.muted)}
        />
        {!playing && (
          <button
            type="button"
            onClick={toggle}
            aria-label={started ? 'Resume the demo' : 'Play the demo'}
            className="absolute top-1/2 left-1/2 flex h-16 w-16 -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full bg-ink/90 text-on-ink shadow-lg transition-transform hover:scale-105 md:h-20 md:w-20"
          >
            <svg viewBox="0 0 12 12" className="ml-1 h-6 w-6 md:h-7 md:w-7" fill="currentColor" aria-hidden>
              <path d="M3 1.5v9l7.5-4.5z" />
            </svg>
          </button>
        )}
      </div>

      <figcaption className="mt-4 flex items-center gap-3 px-1">
        <button type="button" onClick={toggle} aria-label={playing ? 'Pause the demo' : 'Play the demo'} className={iconBtn}>
          {playing ? (
            <svg viewBox="0 0 12 12" className="h-2.5 w-2.5" fill="currentColor" aria-hidden>
              <path d="M2.5 1.5h2.5v9H2.5zM7 1.5h2.5v9H7z" />
            </svg>
          ) : (
            <svg viewBox="0 0 12 12" className="h-2.5 w-2.5" fill="currentColor" aria-hidden>
              <path d="M3 1.5v9l7.5-4.5z" />
            </svg>
          )}
        </button>
        <span className="relative flex h-5 flex-1 items-center">
          <span className="relative h-px w-full overflow-hidden bg-line" aria-hidden>
            <span
              className="absolute inset-0 origin-left bg-accent"
              style={{ transform: `scaleX(${duration ? t / duration : 0})` }}
            />
          </span>
          <input
            type="range"
            min={0}
            max={duration || 0}
            step={0.1}
            value={t}
            onChange={e => {
              const v = ref.current
              if (v) v.currentTime = Number(e.target.value)
            }}
            aria-label="Seek"
            aria-valuetext={`${mmss(t)} of ${mmss(duration)}`}
            className="absolute inset-0 w-full cursor-pointer opacity-0"
          />
        </span>
        <span className="shrink-0 font-mono text-[12px] tabular-nums text-muted">
          {mmss(t)} / {mmss(duration)}
        </span>
        <button
          type="button"
          onClick={() => ref.current && (ref.current.muted = !ref.current.muted)}
          aria-label={muted ? 'Unmute' : 'Mute'}
          className={iconBtn}
        >
          <svg viewBox="0 0 12 12" className="h-3 w-3" fill="none" stroke="currentColor" strokeWidth="1.2" aria-hidden>
            <path d="M1.5 4.5h2l3-2.5v8l-3-2.5h-2z" fill="currentColor" stroke="none" />
            {muted ? <path d="M8.5 4.5l2.5 3M11 4.5l-2.5 3" /> : <path d="M8.5 4a3 3 0 0 1 0 4M9.8 2.8a4.8 4.8 0 0 1 0 6.4" />}
          </svg>
        </button>
        <button type="button" onClick={goFullscreen} aria-label="Full screen" className={iconBtn}>
          <svg viewBox="0 0 12 12" className="h-3 w-3" fill="none" stroke="currentColor" strokeWidth="1.3" aria-hidden>
            <path d="M1.5 4.5v-3h3M7.5 1.5h3v3M10.5 7.5v3h-3M4.5 10.5h-3v-3" />
          </svg>
        </button>
      </figcaption>
    </figure>
  )
}
