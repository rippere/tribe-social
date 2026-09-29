'use client'

import { useState, useEffect, useCallback } from 'react'
import VideoDropzone from '@/components/scorer/VideoDropzone'
import JobProgress from '@/components/scorer/JobProgress'
import ResultsCard from '@/components/scorer/ResultsCard'
import { DEMO_STAGES } from '@/components/landing/demo-data'
import { fetchHealth } from '@/lib/api'
import type { ScoreResult, InferenceMode } from '@/lib/types'

const MODE_LABEL: Record<InferenceMode, string> = {
  mock: 'Mock inference (no GPU)',
  pod: 'TRIBE v2 · warm GPU pod',
  real: 'TRIBE v2 · serverless GPU',
}

export default function ScorerPage() {
  const [jobId, setJobId] = useState<string | null>(null)
  const [result, setResult] = useState<ScoreResult | null>(null)
  const [inferenceMode, setInferenceMode] = useState<InferenceMode>('mock')
  const [processingStage, setProcessingStage] = useState(0)

  useEffect(() => {
    fetchHealth().then(h => setInferenceMode(h.mode)).catch(() => {})
  }, [])

  const isReal = inferenceMode !== 'mock'

  const handleReset = () => {
    setJobId(null)
    setResult(null)
    setProcessingStage(0)
  }

  const onStageChange = useCallback((i: number) => setProcessingStage(i), [])

  // Rail position: 0 while choosing a clip, the reported stage while scoring, all done after.
  const railIndex = result ? DEMO_STAGES.length : jobId ? processingStage : 0

  return (
    <div className="mx-auto max-w-[1232px] px-6 pt-12 md:pt-16">
      {/* Header */}
      <div className="mx-auto max-w-[976px]">
        <div className="mb-5 inline-flex items-center gap-2 rounded-full px-3 py-1.5 text-[13px] text-muted shadow-[var(--shadow-hairline)]">
          <span className={`h-1.5 w-1.5 rounded-full ${isReal ? 'bg-[#34D399]' : 'bg-muted'} animate-pulse`} />
          {MODE_LABEL[inferenceMode]}
        </div>
        <h1 className="type-h2 text-ink">Score a clip</h1>
        <p className="type-lead mt-3 max-w-2xl">
          Drop in a short video or paste a Shorts or Reel link. TRIBE v2 predicts how an average brain responds to it,
          and we explain what that means. It&apos;s a read of the video, not a view forecast.
        </p>
      </div>

      {/* App window */}
      <div className="mx-auto mt-10 w-full max-w-[976px] overflow-hidden rounded-[22px] bg-elevated shadow-[var(--shadow-window),var(--shadow-hairline)]">
        <div className="flex h-11 items-center justify-between border-b border-line px-4">
          <div className="flex items-center gap-2">
            <span className="h-3 w-3 rounded-full bg-[#FF5F57]" />
            <span className="h-3 w-3 rounded-full bg-[#FEBC2E]" />
            <span className="h-3 w-3 rounded-full bg-[#28C840]" />
            <span className="ml-3 text-[13px] text-muted">fMRIght scorer</span>
          </div>
          {result && (
            <button type="button" onClick={handleReset} className="rounded-full px-3 py-1 text-[13px] text-ink hover:bg-fill">
              Score another clip
            </button>
          )}
        </div>

        <div className="grid md:grid-cols-[200px_1fr]">
          {/* Stage rail */}
          <ol className="flex gap-1 border-b border-line p-3 md:flex-col md:border-r md:border-b-0">
            {DEMO_STAGES.map((s, i) => {
              const state = i < railIndex ? 'done' : i === railIndex ? 'active' : 'todo'
              return (
                <li
                  key={s.key}
                  aria-current={state === 'active' ? 'step' : undefined}
                  className={`flex flex-1 items-center gap-2.5 rounded-xl px-3 py-2 text-[13px] transition-colors md:flex-none ${
                    state === 'active' ? 'bg-fill text-ink' : state === 'done' ? 'text-ink' : 'text-muted'
                  }`}
                >
                  <span
                    aria-hidden
                    className={`flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-[11px] ${
                      state === 'todo' ? 'bg-fill text-muted' : 'bg-ink text-on-ink'
                    }`}
                  >
                    {state === 'done' ? '✓' : i + 1}
                  </span>
                  <span className="font-medium">{s.label}</span>
                </li>
              )
            })}
          </ol>

          <div className="p-4 md:p-5">
            {!jobId && !result && <VideoDropzone onJobCreated={setJobId} />}

            {jobId && !result && (
              <JobProgress jobId={jobId} onComplete={setResult} onStageChange={onStageChange} />
            )}

            {result && <ResultsCard result={result} />}
          </div>
        </div>
      </div>
    </div>
  )
}
