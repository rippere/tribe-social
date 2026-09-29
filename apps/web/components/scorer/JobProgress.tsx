'use client'

import { useEffect, useRef } from 'react'
import useSWR from 'swr'
import { API_BASE } from '@/lib/api'
import type { JobResponse, ScoreResult } from '@/lib/types'
import { DEMO_STAGES } from '@/components/landing/demo-data'

// Backend progress thresholds (Upload, Score, Encode, Extract, Analyze) folded onto
// the four stages the UI shows (Upload, Encode, Extract, Read).
const DISPLAY_STAGE_PCT = [0, 30, 85, 95]

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

/** Map backend progress_pct to a display stage index (0–3). */
export function displayStageIndex(pct: number): number {
  for (let i = DISPLAY_STAGE_PCT.length - 1; i >= 0; i--) {
    if (pct >= DISPLAY_STAGE_PCT[i]) return i
  }
  return 0
}

interface Props {
  jobId: string
  onComplete: (result: ScoreResult) => void
  /** Optional: reports the active display stage (0–3) so the page rail can follow. */
  onStageChange?: (index: number) => void
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
    <div className="rounded-2xl bg-[#F87171]/10 p-8 text-center">
      <p className="mb-2 font-medium text-[#F87171]">{title}</p>
      <p className="mb-5 text-[14px] text-muted">{detail}</p>
      <button type="button" onClick={onAction} className="btn-secondary btn-sm">
        {actionLabel}
      </button>
    </div>
  )
}

export default function JobProgress({ jobId, onComplete, onStageChange }: Props) {
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

  const pct = data?.progress_pct ?? 0
  const activeStage = displayStageIndex(pct)
  useEffect(() => {
    onStageChange?.(activeStage)
  }, [activeStage, onStageChange])

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

  const stage = DEMO_STAGES[activeStage]

  return (
    <div className="grid gap-4">
      <div className="grid gap-4 md:grid-cols-[1fr_1.1fr]">
        {/* CortexViewer slot: see docs/CORTEX-VIEW.md on feat/cortex-render */}
        <div className="relative flex h-[240px] items-center justify-center overflow-hidden rounded-2xl bg-panel">
          <p className="px-6 text-center text-[13px] text-muted">The live 3D cortex view will appear here.</p>
        </div>

        {/* Plain-language explainer for the active stage */}
        <div key={stage.key} className="flex flex-col justify-center rounded-2xl bg-fill p-5 animate-in fade-in duration-500">
          <p className="text-[12px] font-medium uppercase tracking-wide text-muted">
            Step {activeStage + 1} of {DEMO_STAGES.length}
          </p>
          <h3 className="mt-2 text-[18px] font-medium leading-6 text-ink">{stage.heading}</h3>
          <p className="mt-2 text-[14px] leading-[22px] text-ink/70">{stage.body}</p>
        </div>
      </div>

      <div className="rounded-2xl border border-line p-4">
        <div className="h-1.5 w-full overflow-hidden rounded-full bg-fill">
          <div className="h-full rounded-full bg-accent transition-all duration-700" style={{ width: `${pct}%` }} />
        </div>
        <p className="mt-3 text-center text-[13px] text-muted">
          {data?.message ?? (isLoading ? 'Loading…' : 'Queued…')}{' '}
          <span className="font-mono text-ink">{pct}%</span>
        </p>
        <p className="mt-1 text-center text-[12px] text-muted/80">
          Usually a few minutes; longer if the GPU has to start up.
        </p>
      </div>
    </div>
  )
}
