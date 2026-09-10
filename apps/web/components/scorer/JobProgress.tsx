'use client'

import { useRef } from 'react'
import useSWR from 'swr'
import { API_BASE } from '@/lib/api'
import type { JobResponse, ScoreResult } from '@/lib/types'

const STAGES = ['Upload', 'Score', 'Encode', 'Extract', 'Analyze']
const STAGE_PCT = [10, 30, 60, 85, 95]

// Hard polling ceiling — matches the backend job TIMEOUT (~30 min). Past this we
// stop polling and surface a timeout state rather than hammering the API forever.
const MAX_POLL_MS = 30 * 60 * 1000

class FetchError extends Error {
  status: number
  constructor(message: string, status: number) {
    super(message)
    this.name = 'FetchError'
    this.status = status
  }
}

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

const fetcher = async (url: string): Promise<JobResponse> => {
  const r = await fetch(url)
  if (!r.ok) {
    throw new FetchError(`Request failed (${r.status})`, r.status)
  }
  return r.json()
}

function ErrorCard({
  title,
  detail,
  actionLabel,
  onAction,
}: {
  title: string
  detail: string
  actionLabel: string
  onAction: () => void
}) {
  return (
    <div className="mt-8 rounded-xl border border-[#DC2626]/40 bg-[#DC2626]/10 p-8 text-center">
      <p className="text-[#DC2626] font-medium mb-2">{title}</p>
      <p className="text-[#9CA3AF] text-sm mb-4">{detail}</p>
      <button
        onClick={onAction}
        className="px-4 py-2 rounded-lg bg-[#1F2937] text-[#F9FAFB] text-sm hover:bg-[#374151] transition-colors"
      >
        {actionLabel}
      </button>
    </div>
  )
}

export default function JobProgress({ jobId, onComplete }: Props) {
  const startRef = useRef(Date.now())
  // Latch a terminal 404 and any request error so polling doesn't restart.
  const notFoundRef = useRef(false)
  const errorRef = useRef(false)

  const isDone = (data?: JobResponse) =>
    data?.status === 'complete' || data?.status === 'failed'

  const { data, error, isLoading, mutate } = useSWR<JobResponse, FetchError>(
    jobId ? `${API_BASE}/jobs/${jobId}` : null,
    fetcher,
    {
      refreshInterval: (d) => {
        if (errorRef.current || notFoundRef.current) return 0
        if (Date.now() - startRef.current > MAX_POLL_MS) return 0
        return isDone(d) ? 0 : 2000
      },
      shouldRetryOnError: false,
      onError: (err) => {
        errorRef.current = true
        if (err?.status === 404) notFoundRef.current = true
      },
      onSuccess: (d) => {
        errorRef.current = false
        if (d.status === 'complete' && d.result) {
          onComplete(d.result)
        }
      },
    },
  )

  // Terminal: the job genuinely does not exist.
  if (error?.status === 404) {
    return (
      <ErrorCard
        title="Job not found"
        detail="This job no longer exists or the ID is invalid. Start over to score another clip."
        actionLabel="Start over"
        onAction={() => window.location.reload()}
      />
    )
  }

  // Non-terminal request error (network / 5xx / timeout) — distinct from a
  // backend job that reported status === 'failed'. Offer a retry.
  if (error) {
    return (
      <ErrorCard
        title="Couldn't reach the scorer"
        detail={error.message || 'The request failed. Check your connection and try again.'}
        actionLabel="Retry"
        onAction={() => {
          errorRef.current = false
          mutate()
        }}
      />
    )
  }

  // Backend reported the job itself failed.
  if (data?.status === 'failed') {
    return (
      <ErrorCard
        title="Processing failed"
        detail={data.error ?? 'Unknown error'}
        actionLabel="Try Again"
        onAction={() => window.location.reload()}
      />
    )
  }

  // Exceeded the hard ceiling without completing.
  const timedOut = Date.now() - startRef.current > MAX_POLL_MS
  if (timedOut && !isDone(data)) {
    return (
      <ErrorCard
        title="Scoring timed out"
        detail="This job ran longer than the 30-minute limit without completing. Start over to try again."
        actionLabel="Start over"
        onAction={() => window.location.reload()}
      />
    )
  }

  const pct = data?.progress_pct ?? 0
  const activeStage = stageIndex(pct)

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
        {data?.message ?? (isLoading ? 'Loading…' : 'Queued…')}{' '}
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
