'use client'

import useSWR from 'swr'
import { fetchCorpus, fetchStats } from '@/lib/api'
import { CorpusStats, CorpusVideo } from '@/lib/types'

import CorpusOverview       from '@/components/corpus/CorpusOverview'
import ScoreDistribution    from '@/components/corpus/ScoreDistribution'
import TopVideosTable       from '@/components/corpus/TopVideosTable'
import ROIBarChart          from '@/components/corpus/ROIBarChart'
import CorrelationScatter   from '@/components/corpus/CorrelationScatter'
import CorrelationHeatmap   from '@/components/corpus/CorrelationHeatmap'
import GoNoGoVerdict        from '@/components/corpus/GoNoGoVerdict'

function LoadingCard() {
  return (
    <div className="rounded-xl border border-[#1F2937] bg-[#111827] p-5 animate-pulse h-64" />
  )
}

function ErrorBanner({ message }: { message: string }) {
  return (
    <div className="rounded-xl border border-[#DC2626]/40 bg-[#DC2626]/10 p-4 text-[#DC2626] text-sm">
      Failed to load: {message}. Make sure the API is running at{' '}
      <code className="font-mono">{process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'}</code>.
    </div>
  )
}

export default function DashboardPage() {
  const {
    data: corpusData,
    error: corpusError,
    isLoading: corpusLoading,
  } = useSWR<{ videos: CorpusVideo[] }>('/corpus', fetchCorpus)

  const {
    data: stats,
    error: statsError,
    isLoading: statsLoading,
  } = useSWR<CorpusStats>('/corpus/stats', fetchStats)

  const videos = corpusData?.videos ?? []
  const isLoading = corpusLoading || statsLoading
  const hasError = corpusError || statsError

  return (
    <div className="mx-auto max-w-7xl px-6 py-8 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-[#F9FAFB]">Corpus Dashboard</h1>
          <p className="text-[#9CA3AF] text-sm mt-0.5">
            TRIBE v2 neural scores · {videos.length} videos
          </p>
        </div>
        {stats && (
          <div
            className="px-3 py-1 rounded-full text-sm font-semibold"
            style={{
              background: stats.go_no_go === 'GO' ? '#16A34A22' : '#DC262622',
              color:      stats.go_no_go === 'GO' ? '#16A34A' : '#DC2626',
              border:     `1px solid ${stats.go_no_go === 'GO' ? '#16A34A44' : '#DC262644'}`,
            }}
          >
            {stats.go_no_go}
          </div>
        )}
      </div>

      {hasError && (
        <ErrorBanner message={corpusError?.message ?? statsError?.message ?? 'Unknown error'} />
      )}

      {/* Row 1: Stat cards */}
      {statsLoading ? (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="rounded-xl border border-[#1F2937] bg-[#111827] p-5 animate-pulse h-24" />
          ))}
        </div>
      ) : stats ? (
        <CorpusOverview stats={stats} />
      ) : null}

      {/* Row 2: Distribution + Top videos */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {corpusLoading ? <LoadingCard /> : <ScoreDistribution videos={videos} />}
        {corpusLoading ? <LoadingCard /> : <TopVideosTable videos={videos} />}
      </div>

      {/* Row 3: ROI bar chart */}
      {statsLoading ? (
        <LoadingCard />
      ) : stats ? (
        <ROIBarChart stats={stats} />
      ) : null}

      {/* Row 4: Scatter + Heatmap */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {corpusLoading ? <LoadingCard /> : <CorrelationScatter videos={videos} />}
        {corpusLoading ? <LoadingCard /> : <CorrelationHeatmap videos={videos} />}
      </div>

      {/* Row 5: Go/No-Go verdict */}
      {statsLoading ? (
        <LoadingCard />
      ) : stats ? (
        <GoNoGoVerdict stats={stats} />
      ) : null}
    </div>
  )
}
