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

export default function TemporalTimeline({ temporal }: Props) {
  const data = temporal.map((p) => ({
    second: p.second,
    Attention: parseFloat(p.attention.toFixed(3)),
    'Social Cognition': parseFloat(p.social_cognition.toFixed(3)),
    Valuation: parseFloat(p.valuation.toFixed(3)),
  }))

  return (
    <div>
      <div className="flex gap-3 mb-2 text-xs text-[#9CA3AF]">
        <span className="flex items-center gap-1">
          <span className="inline-block w-3 h-0.5 bg-[#4FC3F7]" /> Attention
        </span>
        <span className="flex items-center gap-1">
          <span className="inline-block w-3 h-0.5 bg-[#81C784]" /> Social Cognition
        </span>
        <span className="flex items-center gap-1">
          <span className="inline-block w-3 h-0.5 bg-[#FFB74D]" /> Valuation
        </span>
      </div>

      <ResponsiveContainer width="100%" height={240}>
        <LineChart data={data} margin={{ top: 4, right: 12, bottom: 4, left: 0 }}>
          <CartesianGrid stroke="#1F2937" strokeDasharray="3 3" />
          <XAxis
            dataKey="second"
            tick={{ fill: '#9CA3AF', fontSize: 11 }}
            label={{ value: 'Second', position: 'insideBottomRight', offset: -4, fill: '#6B7280', fontSize: 11 }}
          />
          <YAxis
            domain={[0, 1]}
            tick={{ fill: '#9CA3AF', fontSize: 11 }}
            width={30}
          />
          <Tooltip
            contentStyle={{ background: '#111827', border: '1px solid #1F2937', borderRadius: 8 }}
            labelStyle={{ color: '#F9FAFB' }}
            itemStyle={{ color: '#9CA3AF' }}
            labelFormatter={(v) => `${v}s`}
            formatter={(v) => typeof v === 'number' ? v.toFixed(3) : String(v)}
          />

          {/* Hook zone 0–3s */}
          <ReferenceArea x1={0} x2={3} fill="#3B82F6" fillOpacity={0.06} />
          {/* CTA zone 45–60s */}
          <ReferenceArea x1={45} x2={59} fill="#22C55E" fillOpacity={0.06} />

          {/* Vertical labels */}
          <ReferenceLine x={0}  stroke="#3B82F6" strokeOpacity={0.4} label={{ value: 'Hook', position: 'insideTopRight', fill: '#3B82F6', fontSize: 10 }} />
          <ReferenceLine x={3}  stroke="#3B82F6" strokeOpacity={0.2} strokeDasharray="3 3" />
          <ReferenceLine x={45} stroke="#22C55E" strokeOpacity={0.4} label={{ value: 'CTA', position: 'insideTopRight', fill: '#22C55E', fontSize: 10 }} />

          <Line type="monotone" dataKey="Attention"        stroke="#4FC3F7" strokeWidth={1.5} dot={false} />
          <Line type="monotone" dataKey="Social Cognition" stroke="#81C784" strokeWidth={1.5} dot={false} />
          <Line type="monotone" dataKey="Valuation"        stroke="#FFB74D" strokeWidth={1.5} dot={false} />
          <Legend wrapperStyle={{ display: 'none' }} />
        </LineChart>
      </ResponsiveContainer>

      <p className="text-[#6B7280] text-xs mt-2">
        Hook (0–3s): attention should spike · Body (3–45s): social cognition builds · CTA (45–60s): valuation + social should peak
      </p>
    </div>
  )
}
