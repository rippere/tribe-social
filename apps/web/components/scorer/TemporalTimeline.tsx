'use client'

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ReferenceArea,
  ReferenceLine,
  ResponsiveContainer,
} from 'recharts'
import type { TemporalPoint } from '@/lib/types'

interface Props {
  temporal: TemporalPoint[]
}

const SERIES = [
  { key: 'Attention', color: 'var(--color-roi-attention)' },
  { key: 'Social', color: 'var(--color-roi-social)' },
  { key: 'Value', color: 'var(--color-roi-valuation)' },
] as const

export default function TemporalTimeline({ temporal }: Props) {
  const data = temporal.map((p) => ({
    second: p.second,
    Attention: parseFloat(p.attention.toFixed(3)),
    Social: parseFloat(p.social_cognition.toFixed(3)),
    Value: parseFloat(p.valuation.toFixed(3)),
  }))

  return (
    <div>
      <div className="mb-2 flex flex-wrap gap-4 text-[12px] text-muted">
        {SERIES.map((s) => (
          <span key={s.key} className="flex items-center gap-1.5">
            <span className="inline-block h-0.5 w-3 rounded" style={{ background: s.color }} /> {s.key}
          </span>
        ))}
      </div>

      <ResponsiveContainer width="100%" height={240}>
        <LineChart data={data} margin={{ top: 4, right: 12, bottom: 4, left: 0 }}>
          <CartesianGrid stroke="var(--line)" strokeDasharray="3 3" />
          <XAxis dataKey="second" tick={{ fill: 'var(--muted)', fontSize: 11 }} />
          <YAxis domain={[0, 1]} tick={{ fill: 'var(--muted)', fontSize: 11 }} width={30} />
          <Tooltip
            contentStyle={{ background: 'var(--ink-2)', border: '1px solid var(--line)', borderRadius: 12 }}
            labelStyle={{ color: 'var(--ink)' }}
            itemStyle={{ color: 'var(--muted)' }}
            labelFormatter={(v) => `${v}s`}
            formatter={(v) => (typeof v === 'number' ? v.toFixed(3) : String(v))}
          />

          {/* Hook window 0–3s */}
          <ReferenceArea x1={0} x2={3} fill="var(--accent)" fillOpacity={0.06} />
          <ReferenceLine x={3} stroke="var(--line)" strokeDasharray="3 3" />

          {SERIES.map((s) => (
            <Line key={s.key} type="monotone" dataKey={s.key} stroke={s.color} strokeWidth={1.5} dot={false} />
          ))}
          <Legend wrapperStyle={{ display: 'none' }} />
        </LineChart>
      </ResponsiveContainer>

      <p className="mt-2 text-[12px] leading-5 text-muted">
        Shaded: the first 3 seconds, the hook window. This curve is an illustrative shape built from the clip&apos;s
        region averages, not yet a second-by-second readout from the model.
      </p>
    </div>
  )
}
