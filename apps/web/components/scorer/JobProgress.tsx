'use client'

import useSWR from 'swr'
import type { JobResponse, ScoreResult } from '@/lib/types'

const API = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

const STAGES = ['Upload', 'Score', 'Encode', 'Extract', 'Analyze']
const STAGE_PCT = [10, 30, 60, 85, 95]

function stageIndex(pct: number): number {
  for (let i = STAGE_PCT.length - 1; i >= 0; i--) {
    if (pct >= STAGE_PCT[i]) return i
  }
  return -1
}

interface Props {
  jobId: string
  onComplete: (result: ScoreResult) => void
}

const fetcher = (url: string) => fetch(url).then((r) => r.json())

export default function JobProgress({ jobId, onComplete }: Props) {
  const isDone = (data?: JobResponse) =>
    data?.status === 'complete' || data?.status === 'failed'

  const { data } = useSWR<JobResponse>(
    jobId ? `${API}/jobs/${jobId}` : null,
    fetcher,
    {
      refreshInterval: (d) => (isDone(d) ? 0 : 2000),
      onSuccess: (d) => {
        if (d.status === 'complete' && d.result) {
          onComplete(d.result)
        }
      },
    },
  )

  const pct = data?.progress_pct ?? 0
  const activeStage = stageIndex(pct)

  if (data?.status === 'failed') {
    return (
      <div className="mt-8 rounded-xl border border-[#DC2626]/40 bg-[#DC2626]/10 p-8 text-center">
        <p className="text-[#DC2626] font-medium mb-2">Processing failed</p>
        <p className="text-[#9CA3AF] text-sm mb-4">{data.error ?? 'Unknown error'}</p>
        <button
          onClick={() => window.location.reload()}
          className="px-4 py-2 rounded-lg bg-[#1F2937] text-[#F9FAFB] text-sm hover:bg-[#374151] transition-colors"
        >
          Try Again
        </button>
      </div>
    )
  }

  return (
    <div className="mt-8 rounded-xl border border-[#1F2937] bg-[#111827] p-8">
      {/* Stage labels */}
      <div className="flex justify-between mb-3">
        {STAGES.map((s, i) => (
          <span
            key={s}
            className={`text-xs font-medium transition-colors ${
              i <= activeStage ? 'text-[#6366F1]' : 'text-[#4B5563]'
            }`}
          >
            {s}
          </span>
        ))}
      </div>

      {/* Progress bar */}
      <div className="w-full h-2 rounded-full bg-[#1F2937] overflow-hidden">
        <div
          className="h-full rounded-full bg-[#6366F1] transition-all duration-700"
          style={{ width: `${pct}%` }}
        />
      </div>

      {/* Status message */}
      <p className="mt-3 text-[#9CA3AF] text-sm text-center">
        {data?.message ?? 'Queued…'}{' '}
        <span className="text-[#6366F1] font-mono">{pct}%</span>
      </p>

      {/* Animated dots */}
      <div className="flex justify-center gap-1.5 mt-4">
        {[0, 1, 2].map((i) => (
          <div
            key={i}
            className="w-1.5 h-1.5 rounded-full bg-[#6366F1] animate-bounce"
            style={{ animationDelay: `${i * 150}ms` }}
          />
        ))}
      </div>
    </div>
  )
}
