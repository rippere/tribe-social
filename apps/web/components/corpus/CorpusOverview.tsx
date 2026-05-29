'use client'

import { CorpusStats } from '@/lib/types'

interface Props {
  stats: CorpusStats
}

function StatCard({ label, value, sub }: { label: string; value: string | number; sub?: string }) {
  return (
    <div className="rounded-xl border border-[#1F2937] bg-[#111827] p-5">
      <p className="text-xs text-[#9CA3AF] font-medium uppercase tracking-wide mb-1">{label}</p>
      <p className="text-3xl font-bold text-[#F9FAFB]">{value}</p>
      {sub && <p className="text-xs text-[#9CA3AF] mt-1">{sub}</p>}
    </div>
  )
}

export default function CorpusOverview({ stats }: Props) {
  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
      <StatCard label="Videos" value={stats.total_videos} sub="scored with TRIBE v2" />
      <StatCard
        label="Avg Neural Score"
        value={`${stats.avg_composite} / 100`}
        sub="composite across corpus"
      />
      <StatCard
        label="Post-worthy ≥ 65"
        value={stats.post_count}
        sub={`${Math.round((stats.post_count / stats.total_videos) * 100)}% of corpus`}
      />
      <StatCard
        label="Median Likes / 1K"
        value={stats.median_likes_per_1k}
        sub="views engagement proxy"
      />
    </div>
  )
}
