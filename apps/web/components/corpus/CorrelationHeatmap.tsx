'use client'

import { CorpusVideo } from '@/lib/types'
import { pearsonR, ROI_LABELS } from '@/lib/scoring'

interface Props {
  videos: CorpusVideo[]
}

const ENGAGEMENT_COLS: { key: keyof CorpusVideo; label: string }[] = [
  { key: 'likes_per_1k', label: 'Likes/1K' },
  { key: 'likes',        label: 'Likes' },
  { key: 'views',        label: 'Views' },
  { key: 'comments',     label: 'Comments' },
]

const ROI_FIELD_MAP: Record<string, keyof CorpusVideo> = {
  vmPFC:   'vmPFC_mean',
  TPJ:     'TPJ_mean',
  IFJa:    'IFJa_mean',
  IFJp:    'IFJp_mean',
  area_45: 'area_45_mean',
  MT_V5:   'MT_V5_mean',
}

const ROI_KEYS = Object.keys(ROI_FIELD_MAP)

// Interpolate between red (-0.6), white (0), blue (+0.6)
function rToColor(r: number): string {
  const clamped = Math.max(-0.6, Math.min(0.6, r))
  if (clamped >= 0) {
    // white → blue
    const t = clamped / 0.6
    const R = Math.round(249 * (1 - t) + 99 * t)
    const G = Math.round(250 * (1 - t) + 102 * t)
    const B = Math.round(251 * (1 - t) + 241 * t)
    return `rgb(${R},${G},${B})`
  } else {
    // red → white
    const t = (-clamped) / 0.6
    const R = Math.round(249 * (1 - t) + 220 * t)
    const G = Math.round(250 * (1 - t) + 38 * t)
    const B = Math.round(251 * (1 - t) + 38 * t)
    return `rgb(${R},${G},${B})`
  }
}

function textColor(r: number): string {
  // Use dark text for lighter cells (near 0), white text for strong colors
  return Math.abs(r) > 0.25 ? '#0D0D0D' : '#9CA3AF'
}

export default function CorrelationHeatmap({ videos }: Props) {
  // Pre-filter valid rows per engagement col
  const getValidPairs = (roiKey: string, engKey: keyof CorpusVideo) => {
    const roiField = ROI_FIELD_MAP[roiKey]
    return videos.filter(
      v => v[roiField] != null && v[engKey] != null && !isNaN(v[engKey] as number)
    )
  }

  return (
    <div className="rounded-xl border border-[#1F2937] bg-[#111827] p-5">
      <h3 className="text-sm font-semibold text-[#F9FAFB] mb-4">ROI × Engagement Correlations</h3>

      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr>
              <th className="text-left text-[#9CA3AF] py-1 pr-3 font-medium w-32">ROI</th>
              {ENGAGEMENT_COLS.map(col => (
                <th key={col.key} className="text-center text-[#9CA3AF] py-1 px-2 font-medium">
                  {col.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {ROI_KEYS.map(roi => (
              <tr key={roi}>
                <td className="text-[#9CA3AF] py-1 pr-3 font-medium">
                  {ROI_LABELS[roi] ?? roi}
                </td>
                {ENGAGEMENT_COLS.map(col => {
                  const valid = getValidPairs(roi, col.key)
                  const xs = valid.map(v => v[ROI_FIELD_MAP[roi]] as number)
                  const ys = valid.map(v => v[col.key] as number)
                  const r  = valid.length >= 3 ? pearsonR(xs, ys) : 0
                  return (
                    <td key={col.key} className="py-1 px-1">
                      <div
                        className="rounded text-center py-2 px-1 font-mono font-semibold min-w-[52px]"
                        style={{
                          background: rToColor(r),
                          color: textColor(r),
                        }}
                      >
                        {r.toFixed(2)}
                      </div>
                    </td>
                  )
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Legend */}
      <div className="mt-4 flex items-center gap-2 text-xs text-[#9CA3AF]">
        <span>−0.6</span>
        <div
          className="h-2 flex-1 rounded"
          style={{
            background: 'linear-gradient(to right, #DC2626, #F9FAFB, #6366F1)',
          }}
        />
        <span>+0.6</span>
      </div>
    </div>
  )
}
