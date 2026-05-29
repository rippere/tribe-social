'use client'

import type { ScoreResult } from '@/lib/types'
import ScoreGauge from './ScoreGauge'
import ROIRadar from './ROIRadar'
import TemporalTimeline from './TemporalTimeline'
import RevisionPanel from './RevisionPanel'

interface Props {
  result: ScoreResult
}

const VERDICT_CONFIG = {
  POST:    { color: '#16A34A', bg: 'rgba(22,163,74,0.15)',   border: 'rgba(22,163,74,0.3)',   label: 'POST — Neural threshold cleared' },
  REVISE:  { color: '#D97706', bg: 'rgba(217,119,6,0.15)',   border: 'rgba(217,119,6,0.3)',   label: 'REVISE — Strengthen weak regions' },
  RETHINK: { color: '#DC2626', bg: 'rgba(220,38,38,0.15)',   border: 'rgba(220,38,38,0.3)',   label: 'RETHINK — Fundamental content issues' },
}

export default function ResultsCard({ result }: Props) {
  const cfg = VERDICT_CONFIG[result.verdict]

  return (
    <div className="space-y-6 mt-6">
      {/* Verdict banner */}
      <div
        className="rounded-xl px-6 py-4 flex items-center justify-between"
        style={{ background: cfg.bg, border: `1px solid ${cfg.border}` }}
      >
        <div className="flex items-center gap-3">
          <span
            className="text-2xl font-black tracking-widest"
            style={{ color: cfg.color }}
          >
            {result.verdict}
          </span>
          <span className="text-[#D1D5DB] text-sm">{cfg.label}</span>
        </div>
        <span
          className="text-3xl font-bold tabular-nums"
          style={{ color: cfg.color }}
        >
          {result.composite_score.toFixed(1)}
        </span>
      </div>

      {/* Two-col: gauge + radar */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="rounded-xl border border-[#1F2937] bg-[#111827] p-5">
          <h3 className="text-sm font-semibold text-[#9CA3AF] uppercase tracking-wider mb-4">
            Composite Neural Score
          </h3>
          <ScoreGauge score={result.composite_score} verdict={result.verdict} />
        </div>

        <div className="rounded-xl border border-[#1F2937] bg-[#111827] p-5">
          <h3 className="text-sm font-semibold text-[#9CA3AF] uppercase tracking-wider mb-4">
            ROI Radar vs. Corpus Avg
          </h3>
          <ROIRadar roi={result.roi} corpusMeans={result.corpus_roi_means} />
        </div>
      </div>

      {/* Temporal timeline */}
      <div className="rounded-xl border border-[#1F2937] bg-[#111827] p-5">
        <h3 className="text-sm font-semibold text-[#9CA3AF] uppercase tracking-wider mb-4">
          Temporal Activation Breakdown
        </h3>
        <TemporalTimeline temporal={result.temporal} />
      </div>

      {/* Revision panel */}
      <div className="rounded-xl border border-[#1F2937] bg-[#111827] p-5">
        <h3 className="text-sm font-semibold text-[#9CA3AF] uppercase tracking-wider mb-4">
          Revision Recommendations
        </h3>
        <RevisionPanel tips={result.revision_tips} />
      </div>

      {/* Video ID footer */}
      <p className="text-center text-[#4B5563] text-xs">
        Job ID: <span className="font-mono">{result.video_id}</span>
      </p>
    </div>
  )
}
