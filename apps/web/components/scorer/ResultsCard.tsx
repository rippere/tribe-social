'use client'

import type { ScoreResult } from '@/lib/types'
import ScoreGauge from './ScoreGauge'
import ROIRadar from './ROIRadar'
import TemporalTimeline from './TemporalTimeline'

interface Props {
  result: ScoreResult
  /** 'model': the curves are TRIBE's per-second output (trial). Default: illustrative shape. */
  temporalSource?: 'model' | 'illustrative'
}

function Card({ title, children, className = '' }: { title: string; children: React.ReactNode; className?: string }) {
  return (
    <div className={`rounded-2xl border border-line p-5 ${className}`}>
      <h3 className="mb-4 text-[13px] font-medium text-ink">{title}</h3>
      {children}
    </div>
  )
}

// The API still returns a `verdict` and `revision_tips`; neither is shown. A
// Post/Revise/Rethink call or a list of "edits to try" implies a performance claim
// the evidence doesn't support (pilot: r = 0.25, p = 0.24, n = 24).
export default function ResultsCard({ result, temporalSource = 'illustrative' }: Props) {
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

      <Card title={temporalSource === 'model' ? 'Over time, second by second' : 'Over time (illustrative)'}>
        <TemporalTimeline temporal={result.temporal} source={temporalSource} />
      </Card>

      <p className="text-center text-[12px] text-muted">
        Job ID: <span className="font-mono">{result.video_id}</span>
      </p>
    </div>
  )
}
