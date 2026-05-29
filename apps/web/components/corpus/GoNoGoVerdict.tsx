'use client'

import { CorpusStats } from '@/lib/types'

interface Props {
  stats: CorpusStats
}

export default function GoNoGoVerdict({ stats }: Props) {
  const isGo = stats.go_no_go === 'GO'
  const r    = stats.correlations['composite_vs_likes_per_1k']?.r ?? stats.composite_r

  return (
    <div
      className="rounded-xl border p-6 flex flex-col sm:flex-row items-center justify-between gap-4"
      style={{
        borderColor: isGo ? '#16A34A44' : '#DC262644',
        background:  isGo ? '#16A34A0A' : '#DC26260A',
      }}
    >
      <div className="flex items-center gap-4">
        <div
          className="text-5xl font-black tracking-tighter"
          style={{ color: isGo ? '#16A34A' : '#DC2626' }}
        >
          {stats.go_no_go}
        </div>
        <div>
          <p className="text-[#F9FAFB] font-semibold text-lg">
            {isGo ? 'Hypothesis supported — proceed to Phase 2' : 'Insufficient signal — expand corpus first'}
          </p>
          <p className="text-[#9CA3AF] text-sm mt-0.5">
            r = {typeof r === 'number' ? r.toFixed(2) : '—'} composite vs Likes/1K
            &nbsp;·&nbsp;
            {stats.rois_above_threshold} ROI{stats.rois_above_threshold !== 1 ? 's' : ''} exceed r &gt; 0.3
          </p>
        </div>
      </div>

      <div className="flex gap-3 text-sm flex-wrap justify-center">
        <div className="text-center">
          <p className="text-2xl font-bold" style={{ color: isGo ? '#16A34A' : '#DC2626' }}>
            {stats.post_count}
          </p>
          <p className="text-[#9CA3AF] text-xs">post-worthy</p>
        </div>
        <div className="text-center">
          <p className="text-2xl font-bold text-[#F9FAFB]">{stats.total_videos}</p>
          <p className="text-[#9CA3AF] text-xs">total videos</p>
        </div>
        <div className="text-center">
          <p className="text-2xl font-bold text-[#F9FAFB]">{stats.avg_composite}</p>
          <p className="text-[#9CA3AF] text-xs">avg score</p>
        </div>
      </div>
    </div>
  )
}
