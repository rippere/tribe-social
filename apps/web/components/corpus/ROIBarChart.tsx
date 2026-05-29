'use client'

import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  Cell, ResponsiveContainer,
} from 'recharts'
import { ROI_LABELS, ROI_COLORS } from '@/lib/scoring'
import { CorpusStats } from '@/lib/types'

interface Props {
  stats: CorpusStats
}

export default function ROIBarChart({ stats }: Props) {
  const data = [
    { roi: 'vmPFC', label: ROI_LABELS.vmPFC, value: stats.roi_means.vmPFC ?? 0, color: ROI_COLORS.vmPFC },
    { roi: 'TPJ', label: ROI_LABELS.TPJ, value: stats.roi_means.TPJ ?? 0, color: ROI_COLORS.TPJ },
    { roi: 'IFJa', label: ROI_LABELS.IFJa, value: stats.roi_means.IFJa ?? 0, color: ROI_COLORS.IFJa },
    { roi: 'IFJp', label: ROI_LABELS.IFJp, value: stats.roi_means.IFJp ?? 0, color: ROI_COLORS.IFJp },
    { roi: 'area_45', label: ROI_LABELS.area_45, value: stats.roi_means.area_45 ?? 0, color: ROI_COLORS.area_45 },
    { roi: 'MT_V5', label: ROI_LABELS.MT_V5, value: stats.roi_means.MT_V5 ?? 0, color: ROI_COLORS.MT_V5 },
  ]

  return (
    <div className="rounded-xl border border-[#1F2937] bg-[#111827] p-5">
      <h3 className="text-sm font-semibold text-[#F9FAFB] mb-4">
        Mean Activation per Brain Region
      </h3>
      <ResponsiveContainer width="100%" height={260}>
        <BarChart
          layout="vertical"
          data={data}
          margin={{ top: 5, right: 30, left: 10, bottom: 5 }}
        >
          <CartesianGrid strokeDasharray="3 3" stroke="#1F2937" horizontal={false} />
          <XAxis
            type="number"
            domain={[0, 1]}
            tick={{ fill: '#9CA3AF', fontSize: 11 }}
          />
          <YAxis
            type="category"
            dataKey="label"
            width={140}
            tick={{ fill: '#9CA3AF', fontSize: 11 }}
          />
          <Tooltip
            contentStyle={{ background: '#111827', border: '1px solid #1F2937', borderRadius: 8 }}
            labelStyle={{ color: '#F9FAFB' }}
            itemStyle={{ color: '#9CA3AF' }}
            formatter={(v: unknown) => typeof v === 'number' ? v.toFixed(4) : String(v)}
          />
          <Bar dataKey="value" radius={[0, 4, 4, 0]}>
            {data.map((d, i) => (
              <Cell key={i} fill={d.color} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
