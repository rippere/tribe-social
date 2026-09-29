'use client'

import { useState } from 'react'
import type { RevisionTip } from '@/lib/types'
import { regionLabel } from '@/components/brain/contract'

interface Props {
  tips: RevisionTip[]
}

function ScoreBar({ score }: { score: number }) {
  return (
    <div className="flex min-w-[110px] items-center gap-2">
      <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-fill">
        <div className="h-full rounded-full bg-accent transition-all" style={{ width: `${score * 100}%` }} />
      </div>
      <span className="font-mono text-[12px] text-muted">{score.toFixed(2)}</span>
    </div>
  )
}

function TipSection({ tip }: { tip: RevisionTip }) {
  const [open, setOpen] = useState(true)

  return (
    <div className="overflow-hidden rounded-2xl bg-fill">
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center justify-between gap-4 px-4 py-3 text-left transition-colors hover:bg-fill"
      >
        <div className="flex flex-wrap items-center gap-3">
          <span className="text-[14px] font-medium text-ink">{regionLabel(tip.roi)}</span>
          <ScoreBar score={tip.score} />
        </div>
        <svg
          className={`h-4 w-4 shrink-0 text-muted transition-transform ${open ? 'rotate-180' : ''}`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
          aria-hidden
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {open && (
        <div className="space-y-3 px-4 pb-4">
          <p className="text-[14px] leading-[22px] text-ink/80">{tip.tip}</p>
          {tip.hook_templates.length > 0 && (
            <div>
              <p className="mb-2 text-[12px] font-medium uppercase tracking-wide text-muted">Openings to try</p>
              <ul className="space-y-1.5">
                {tip.hook_templates.map((h, i) => (
                  <li key={i} className="flex items-start gap-2 text-[14px] text-ink/70">
                    <span aria-hidden className="mt-0.5 text-accent">▸</span>
                    <span>{h}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default function RevisionPanel({ tips }: Props) {
  if (tips.length === 0) {
    return (
      <p className="rounded-2xl bg-fill px-5 py-4 text-[14px] text-ink/80">
        No region fell below the revision threshold, so there are no edits to suggest for this clip.
      </p>
    )
  }

  return (
    <div className="space-y-2">
      <p className="mb-3 text-[13px] text-muted">
        The lowest-scoring regions, with edits to try. Suggestions are starting points, not guarantees.
      </p>
      {tips.map((tip) => (
        <TipSection key={tip.roi} tip={tip} />
      ))}
    </div>
  )
}
