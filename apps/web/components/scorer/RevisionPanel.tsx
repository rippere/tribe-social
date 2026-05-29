'use client'

import { useState } from 'react'
import type { RevisionTip } from '@/lib/types'

interface Props {
  tips: RevisionTip[]
}

function scoreColor(v: number): string {
  if (v < 0.45) return '#DC2626'
  if (v < 0.70) return '#D97706'
  return '#16A34A'
}

function ScoreBar({ score }: { score: number }) {
  const color = scoreColor(score)
  return (
    <div className="flex items-center gap-2 min-w-[100px]">
      <div className="flex-1 h-1.5 rounded-full bg-[#1F2937] overflow-hidden">
        <div
          className="h-full rounded-full transition-all"
          style={{ width: `${score * 100}%`, background: color }}
        />
      </div>
      <span className="text-xs font-mono" style={{ color }}>{score.toFixed(2)}</span>
    </div>
  )
}

function TipSection({ tip }: { tip: RevisionTip }) {
  const [open, setOpen] = useState(true)
  const color = scoreColor(tip.score)

  return (
    <div className="rounded-lg border border-[#1F2937] overflow-hidden">
      <button
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center justify-between px-4 py-3 bg-[#111827] hover:bg-[#1A2233] transition-colors"
      >
        <div className="flex items-center gap-3">
          <span
            className="text-sm font-semibold"
            style={{ color }}
          >
            {tip.roi}
          </span>
          <ScoreBar score={tip.score} />
        </div>
        <svg
          className={`w-4 h-4 text-[#6B7280] transition-transform ${open ? 'rotate-180' : ''}`}
          fill="none" stroke="currentColor" viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {open && (
        <div className="px-4 py-4 bg-[#0D0D0D] space-y-3">
          <p className="text-[#D1D5DB] text-sm leading-relaxed">{tip.tip}</p>
          {tip.hook_templates.length > 0 && (
            <div>
              <p className="text-[#6B7280] text-xs font-medium uppercase tracking-wider mb-2">
                Hook Templates
              </p>
              <ul className="space-y-1.5">
                {tip.hook_templates.map((h, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-[#9CA3AF]">
                    <span className="text-[#6366F1] mt-0.5">▸</span>
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
      <div className="rounded-xl border border-[#16A34A]/30 bg-[#16A34A]/10 px-6 py-4 flex items-center gap-3">
        <svg className="w-5 h-5 text-[#16A34A] flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        <p className="text-[#16A34A] font-medium text-sm">
          All regions strong — this content is primed for engagement
        </p>
      </div>
    )
  }

  return (
    <div className="space-y-2">
      <p className="text-[#9CA3AF] text-xs mb-3">
        Regions below 0.45 need attention. Expand each for revision strategies.
      </p>
      {tips.map((tip) => (
        <TipSection key={tip.roi} tip={tip} />
      ))}
    </div>
  )
}
