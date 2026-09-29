'use client'

import type { ScoreResult } from '@/lib/types'
import ScoreGauge from './ScoreGauge'
import ROIRadar from './ROIRadar'
import TemporalTimeline from './TemporalTimeline'
import RevisionPanel from './RevisionPanel'

interface Props {
  result: ScoreResult
}

function Card({ title, children, className = '' }: { title: string; children: React.ReactNode; className?: string }) {
  return (
    <div className={`rounded-2xl border border-line p-5 ${className}`}>
      <h3 className="mb-4 text-[13px] font-medium text-ink">{title}</h3>
      {children}
    </div>
  )
}

// The API still returns a `verdict` field; it is intentionally not shown. A
// Post/Revise/Rethink call implies a performance forecast the evidence doesn't support.
export default function ResultsCard({ result }: Props) {
  return (
    <div className="space-y-4">
      <div className="grid gap-4 md:grid-cols-[1fr_1.4fr]">
        <Card title="Overall predicted response" className="flex flex-col items-center">
          <ScoreGauge score={result.composite_score} />
          <p className="mt-3 text-center text-[13px] text-muted">A read of the video, not a view forecast.</p>
        </Card>

        <Card title="By brain region, vs. the corpus average">
          <ROIRadar roi={result.roi} corpusMeans={result.corpus_roi_means} />
        </Card>
      </div>

      <Card title="Over time (illustrative)">
        <TemporalTimeline temporal={result.temporal} />
      </Card>

      <Card title="Edits to try">
        <RevisionPanel tips={result.revision_tips} />
      </Card>

      <p className="text-center text-[12px] text-muted">
        Job ID: <span className="font-mono">{result.video_id}</span>
      </p>
    </div>
  )
}
