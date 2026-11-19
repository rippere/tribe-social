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
import { regionShortLabel } from '@/components/brain/contract'

interface Props {
  roi: Record<string, number>
  corpusMeans: Record<string, number>
}

// Anatomical keys as the API reports them; shown with plain-language labels.
const ROI_ORDER = ['vmPFC', 'TPJ', 'IFJa', 'IFJp', 'area_45', 'MT_V5']

export default function ROIRadar({ roi, corpusMeans }: Props) {
  const data = ROI_ORDER.map((key) => ({
    subject: regionShortLabel(key),
    video: parseFloat((roi[key] ?? 0).toFixed(3)),
    corpus: parseFloat((corpusMeans[key] ?? corpusMeans[`${key}_mean`] ?? 0).toFixed(3)),
  }))

  return (
    <ResponsiveContainer width="100%" height={280}>
      <RadarChart data={data} margin={{ top: 10, right: 30, bottom: 10, left: 30 }}>
        <PolarGrid stroke="var(--line)" />
        <PolarAngleAxis dataKey="subject" tick={{ fill: 'var(--muted)', fontSize: 11 }} />
        <PolarRadiusAxis domain={[0, 1]} tickCount={3} tick={{ fill: 'var(--muted)', fontSize: 9 }} axisLine={false} />
        <Tooltip
          contentStyle={{ background: 'var(--ink-2)', border: '1px solid var(--line)', borderRadius: 12 }}
          labelStyle={{ color: 'var(--ink)', fontWeight: 500 }}
          itemStyle={{ color: 'var(--muted)' }}
          formatter={(v) => (typeof v === 'number' ? v.toFixed(3) : String(v))}
        />
        <Radar
          name="Corpus average"
          dataKey="corpus"
          stroke="var(--muted)"
          fill="var(--muted)"
          fillOpacity={0.1}
          strokeWidth={1.5}
          strokeDasharray="4 2"
        />
        <Radar name="This clip" dataKey="video" stroke="var(--accent)" fill="var(--accent)" fillOpacity={0.22} strokeWidth={2} />
        <Legend
          wrapperStyle={{ fontSize: 12, paddingTop: 8 }}
          formatter={(val) => <span style={{ color: 'var(--muted)' }}>{val}</span>}
        />
      </RadarChart>
    </ResponsiveContainer>
  )
}
