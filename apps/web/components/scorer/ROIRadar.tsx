'use client'

import {
  RadarChart,
  Radar,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Legend,
  ResponsiveContainer,
  Tooltip,
} from 'recharts'

interface Props {
  roi: Record<string, number>
  corpusMeans: Record<string, number>
}

const ROI_AXIS_LABELS: Record<string, string> = {
  vmPFC:   'vmPFC',
  TPJ:     'TPJ',
  IFJa:    'IFJa',
  IFJp:    'IFJp',
  area_45: 'Area 45',
  MT_V5:   'MT/V5',
}

const ROI_ORDER = ['vmPFC', 'TPJ', 'IFJa', 'IFJp', 'area_45', 'MT_V5']

export default function ROIRadar({ roi, corpusMeans }: Props) {
  const data = ROI_ORDER.map((key) => ({
    subject: ROI_AXIS_LABELS[key] ?? key,
    video: parseFloat((roi[key] ?? 0).toFixed(3)),
    corpus: parseFloat((corpusMeans[key] ?? corpusMeans[`${key}_mean`] ?? 0).toFixed(3)),
  }))

  return (
    <ResponsiveContainer width="100%" height={280}>
      <RadarChart data={data} margin={{ top: 10, right: 30, bottom: 10, left: 30 }}>
        <PolarGrid stroke="#1F2937" />
        <PolarAngleAxis
          dataKey="subject"
          tick={{ fill: '#9CA3AF', fontSize: 11 }}
        />
        <PolarRadiusAxis
          domain={[0, 1]}
          tickCount={3}
          tick={{ fill: '#4B5563', fontSize: 9 }}
          axisLine={false}
        />
        <Tooltip
          contentStyle={{ background: '#111827', border: '1px solid #1F2937', borderRadius: 8 }}
          labelStyle={{ color: '#F9FAFB', fontWeight: 600 }}
          itemStyle={{ color: '#9CA3AF' }}
          formatter={(v) => typeof v === 'number' ? v.toFixed(3) : String(v)}
        />
        <Radar
          name="Corpus Avg"
          dataKey="corpus"
          stroke="#94A3B8"
          fill="#94A3B8"
          fillOpacity={0.12}
          strokeWidth={1.5}
          strokeDasharray="4 2"
        />
        <Radar
          name="This Video"
          dataKey="video"
          stroke="#6366F1"
          fill="#6366F1"
          fillOpacity={0.25}
          strokeWidth={2}
        />
        <Legend
          wrapperStyle={{ fontSize: 12, color: '#9CA3AF', paddingTop: 8 }}
          formatter={(val) => <span style={{ color: '#9CA3AF' }}>{val}</span>}
        />
      </RadarChart>
    </ResponsiveContainer>
  )
}
