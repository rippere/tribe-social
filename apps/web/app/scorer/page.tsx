'use client'

import { useState, useEffect } from 'react'
import VideoDropzone from '@/components/scorer/VideoDropzone'
import JobProgress from '@/components/scorer/JobProgress'
import ResultsCard from '@/components/scorer/ResultsCard'
import { fetchHealth } from '@/lib/api'
import type { ScoreResult } from '@/lib/types'

export default function ScorerPage() {
  const [jobId, setJobId] = useState<string | null>(null)
  const [result, setResult] = useState<ScoreResult | null>(null)
  const [inferenceMode, setInferenceMode] = useState<'mock' | 'real'>('mock')

  useEffect(() => {
    fetchHealth().then(h => setInferenceMode(h.mode)).catch(() => {})
  }, [])

  const handleReset = () => {
    setJobId(null)
    setResult(null)
  }

  return (
    <main className="max-w-4xl mx-auto px-6 py-12">
      {/* Header */}
      <div className="mb-8">
        <div className="inline-flex items-center gap-2 rounded-full border border-[#1F2937] bg-[#111827] px-4 py-1.5 text-sm text-[#9CA3AF] mb-4">
          <span className={`h-1.5 w-1.5 rounded-full animate-pulse ${inferenceMode === 'real' ? 'bg-[#10B981]' : 'bg-[#6366F1]'}`} />
          {inferenceMode === 'real' ? 'TRIBE v2 Real Inference' : 'TRIBE v2 Mock Inference'}
        </div>
        <h1 className="text-3xl font-bold text-[#F9FAFB] mb-2">Score a Reel</h1>
        <p className="text-[#9CA3AF] max-w-xl">
          Drop a clip or paste a YouTube Shorts / Instagram Reel URL — TRIBE v2 will score it
          against 6 brain regions that predict viral engagement.
        </p>
      </div>

      {/* Step 1: Upload */}
      {!jobId && !result && (
        <VideoDropzone onJobCreated={setJobId} />
      )}

      {/* Step 2: Processing */}
      {jobId && !result && (
        <JobProgress jobId={jobId} onComplete={setResult} />
      )}

      {/* Step 3: Results */}
      {result && (
        <>
          <ResultsCard result={result} />
          <div className="mt-8 text-center">
            <button
              onClick={handleReset}
              className="px-6 py-2.5 rounded-lg border border-[#374151] text-[#9CA3AF] text-sm font-medium hover:border-[#6366F1] hover:text-[#F9FAFB] transition-colors"
            >
              Score another clip
            </button>
          </div>
        </>
      )}
    </main>
  )
}
