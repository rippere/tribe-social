'use client'

import {
  ScatterChart, Scatter, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Line, ComposedChart, ReferenceLine,
} from 'recharts'
import { CorpusVideo } from '@/lib/types'
import { pearsonR } from '@/lib/scoring'

interface Props {
  videos: CorpusVideo[]
}

const CREATOR_COLORS: Record<string, string> = {
  ali:      '#6366F1',
  huberman: '#F59E0B',
  sahil:    '#10B981',
}

function getCreatorColor(creator: string): string {
  return CREATOR_COLORS[creator] ?? '#9CA3AF'
}

// Compute linear regression (slope + intercept)
function linReg(xs: number[], ys: number[]) {
  const n = xs.length
  if (n < 2) return { slope: 0, intercept: 0 }
  const mx = xs.reduce((a, b) => a + b, 0) / n
  const my = ys.reduce((a, b) => a + b, 0) / n
  let num = 0, denom = 0
  for (let i = 0; i < n; i++) {
    num += (xs[i] - mx) * (ys[i] - my)
    denom += (xs[i] - mx) ** 2
  }
  const slope = denom === 0 ? 0 : num / denom
  const intercept = my - slope * mx
  return { slope, intercept }
}

export default function CorrelationScatter({ videos }: Props) {
  const valid = videos.filter(
    v => v.likes_per_1k != null && !isNaN(v.likes_per_1k!)
  )

  const xs = valid.map(v => v.composite_score)
  const ys = valid.map(v => v.likes_per_1k!)
  const r  = pearsonR(xs, ys)

  const { slope, intercept } = linReg(xs, ys)
  const xMin = Math.min(...xs)
  const xMax = Math.max(...xs)
  const trendData = [
    { x: xMin, y: slope * xMin + intercept },
    { x: xMax, y: slope * xMax + intercept },
  ]

  // Group by creator for coloring
  const creatorGroups: Record<string, { x: number; y: number }[]> = {}
  valid.forEach(v => {
    if (!creatorGroups[v.creator]) creatorGroups[v.creator] = []
    creatorGroups[v.creator].push({ x: v.composite_score, y: v.likes_per_1k! })
  })

  return (
    <div className="rounded-xl border border-[#1F2937] bg-[#111827] p-5">
      <div className="flex justify-between items-start mb-4">
        <h3 className="text-sm font-semibold text-[#F9FAFB]">Composite vs Likes / 1K</h3>
        <span className="text-xs text-[#9CA3AF]">r = {r.toFixed(3)}</span>
      </div>
      <ResponsiveContainer width="100%" height={260}>
        <ComposedChart margin={{ top: 5, right: 20, left: -20, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#1F2937" />
          <XAxis
            type="number"
            dataKey="x"
            name="Score"
            domain={[0, 100]}
            tick={{ fill: '#9CA3AF', fontSize: 11 }}
            label={{ value: 'Composite Score', fill: '#9CA3AF', fontSize: 11, position: 'insideBottom', offset: -2 }}
          />
          <YAxis
            type="number"
            dataKey="y"
            name="Likes/1K"
            tick={{ fill: '#9CA3AF', fontSize: 11 }}
          />
          <Tooltip
            contentStyle={{ background: '#111827', border: '1px solid #1F2937', borderRadius: 8 }}
            labelStyle={{ color: '#F9FAFB' }}
            itemStyle={{ color: '#9CA3AF' }}
            cursor={{ strokeDasharray: '3 3', stroke: '#1F2937' }}
          />
          {Object.entries(creatorGroups).map(([creator, pts]) => (
            <Scatter
              key={creator}
              name={creator}
              data={pts}
              fill={getCreatorColor(creator)}
              opacity={0.85}
            />
          ))}
          {/* Trendline */}
          <Line
            data={trendData}
            dataKey="y"
            dot={false}
            stroke="#6366F1"
            strokeWidth={1.5}
            strokeDasharray="4 2"
            type="linear"
          />
        </ComposedChart>
      </ResponsiveContainer>
      <div className="flex gap-3 mt-2 flex-wrap">
        {Object.keys(creatorGroups).map(c => (
          <div key={c} className="flex items-center gap-1.5">
            <div className="h-2.5 w-2.5 rounded-full" style={{ background: getCreatorColor(c) }} />
            <span className="text-xs text-[#9CA3AF] capitalize">{c}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
