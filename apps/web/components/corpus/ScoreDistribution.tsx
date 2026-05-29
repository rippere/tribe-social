'use client'

import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ReferenceLine, Cell, ResponsiveContainer,
} from 'recharts'
import { CorpusVideo } from '@/lib/types'
import { computeVerdict, VERDICT_COLORS } from '@/lib/scoring'

interface Props {
  videos: CorpusVideo[]
}

export default function ScoreDistribution({ videos }: Props) {
  // Build 10-point buckets: 0–10, 10–20, ..., 90–100
  const buckets: { label: string; count: number; midpoint: number }[] = []
  for (let i = 0; i < 10; i++) {
    const lo = i * 10
    const hi = lo + 10
    const count = videos.filter(v =>
      lo === 0
        ? v.composite_score >= lo && v.composite_score <= hi
        : v.composite_score > lo && v.composite_score <= hi
    ).length
    buckets.push({ label: `${lo}–${hi}`, count, midpoint: lo + 5 })
  }

  const bucketColor = (midpoint: number) => {
    if (midpoint >= 65) return VERDICT_COLORS.POST
    if (midpoint >= 40) return VERDICT_COLORS.REVISE
    return VERDICT_COLORS.RETHINK
  }

  return (
    <div className="rounded-xl border border-[#1F2937] bg-[#111827] p-5">
      <h3 className="text-sm font-semibold text-[#F9FAFB] mb-4">Score Distribution</h3>
      <ResponsiveContainer width="100%" height={260}>
        <BarChart data={buckets} margin={{ top: 5, right: 10, left: -20, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#1F2937" />
          <XAxis
            dataKey="label"
            tick={{ fill: '#9CA3AF', fontSize: 11 }}
            angle={-35}
            textAnchor="end"
            height={50}
          />
          <YAxis tick={{ fill: '#9CA3AF', fontSize: 11 }} />
          <Tooltip
            contentStyle={{ background: '#111827', border: '1px solid #1F2937', borderRadius: 8 }}
            labelStyle={{ color: '#F9FAFB' }}
            itemStyle={{ color: '#9CA3AF' }}
          />
          <ReferenceLine x="40–50" stroke={VERDICT_COLORS.RETHINK} strokeDasharray="4 2" label={{ value: 'Rethink', fill: VERDICT_COLORS.RETHINK, fontSize: 11 }} />
          <ReferenceLine x="60–70" stroke={VERDICT_COLORS.POST} strokeDasharray="4 2" label={{ value: 'Post', fill: VERDICT_COLORS.POST, fontSize: 11 }} />
          <Bar dataKey="count" radius={[4, 4, 0, 0]}>
            {buckets.map((b, i) => (
              <Cell key={i} fill={bucketColor(b.midpoint)} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
