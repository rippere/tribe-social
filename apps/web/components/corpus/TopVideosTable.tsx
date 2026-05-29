'use client'

import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '@/components/ui/table'
import { Badge } from '@/components/ui/badge'
import { CorpusVideo } from '@/lib/types'
import { computeVerdict, VERDICT_COLORS } from '@/lib/scoring'

interface Props {
  videos: CorpusVideo[]
}

export default function TopVideosTable({ videos }: Props) {
  const top10 = [...videos]
    .sort((a, b) => b.composite_score - a.composite_score)
    .slice(0, 10)

  const verdictStyle = (verdict: string) => {
    const color = VERDICT_COLORS[verdict as keyof typeof VERDICT_COLORS]
    return { border: `1px solid ${color}33`, color, background: `${color}11` }
  }

  return (
    <div className="rounded-xl border border-[#1F2937] bg-[#111827] p-5">
      <h3 className="text-sm font-semibold text-[#F9FAFB] mb-4">Top 10 Videos</h3>
      <div className="overflow-x-auto">
        <Table>
          <TableHeader>
            <TableRow className="border-[#1F2937]">
              <TableHead className="text-[#9CA3AF]">Video</TableHead>
              <TableHead className="text-[#9CA3AF]">Creator</TableHead>
              <TableHead className="text-[#9CA3AF]">Score</TableHead>
              <TableHead className="text-[#9CA3AF]">Likes/1K</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {top10.map(v => {
              const verdict = computeVerdict(v.composite_score)
              return (
                <TableRow key={v.video_id} className="border-[#1F2937] hover:bg-[#1F2937]/30">
                  <TableCell className="text-[#F9FAFB] text-sm font-mono">{v.video_id}</TableCell>
                  <TableCell className="text-[#9CA3AF] text-sm capitalize">{v.creator}</TableCell>
                  <TableCell>
                    <div className="flex items-center gap-2">
                      <span className="text-[#F9FAFB] font-semibold">{v.composite_score.toFixed(1)}</span>
                      <span
                        className="px-2 py-0.5 rounded-full text-xs font-medium"
                        style={verdictStyle(verdict)}
                      >
                        {verdict}
                      </span>
                    </div>
                  </TableCell>
                  <TableCell className="text-[#9CA3AF]">
                    {v.likes_per_1k != null ? v.likes_per_1k.toFixed(1) : '—'}
                  </TableCell>
                </TableRow>
              )
            })}
          </TableBody>
        </Table>
      </div>
    </div>
  )
}
