import { CLIPS, clock } from '@/lib/clips'

const W = 240
const H = 64

/**
 * A phone showing the sample clip and its real TRIBE v2 attention line (IFJ, per second).
 * Server-rendered from the clip's context file, so the numbers on screen are model output.
 */
export function PhoneMockup() {
  const clip = CLIPS[0]
  const attention = clip.context.regions.attention
  const values = attention.per_second
  const min = Math.min(...values)
  const max = Math.max(...values)
  const x = (i: number) => (i / (values.length - 1)) * W
  const y = (v: number) => H - 4 - ((v - min) / (max - min || 1)) * (H - 8)
  const points = values.map((v, i) => `${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(' ')
  const peak = attention.peak_second
  const low = attention.low_second

  return (
    <div className="mx-auto w-[300px] rounded-[48px] bg-ink-2 p-3 shadow-[var(--shadow-window)] ring-1 ring-line">
      <div className="overflow-hidden rounded-[38px] bg-elevated">
        <div className="relative">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={clip.poster} alt="" className="aspect-[4/5] w-full object-cover" />
          <span className="absolute top-3 left-1/2 h-6 w-24 -translate-x-1/2 rounded-full bg-black" aria-hidden />
          <span className="absolute bottom-3 left-3 rounded-full bg-black/70 px-2.5 py-1 font-mono text-[11px] text-accent backdrop-blur">
            Real TRIBE v2 prediction
          </span>
        </div>

        <div className="px-4 pt-4 pb-6">
          <div className="flex items-center justify-between">
            <span className="flex items-center gap-2 text-[13px] text-ink">
              <span className="h-2 w-2 rounded-full bg-roi-attention" />
              Attention
            </span>
            <span className="font-mono text-[11px] text-muted">0:00 to {clock(values.length - 1)}</span>
          </div>

          <svg viewBox={`0 0 ${W} ${H}`} className="mt-3 h-16 w-full" role="img" aria-label={`Predicted attention, lowest at ${clock(low)}, highest at ${clock(peak)}`}>
            <polyline points={points} fill="none" stroke="var(--color-roi-attention)" strokeWidth={2} strokeLinejoin="round" />
            <circle cx={x(peak)} cy={y(values[peak])} r={4} fill="var(--accent)" />
            <circle cx={x(low)} cy={y(values[low])} r={3} fill="var(--muted)" />
          </svg>

          <p className="mt-3 rounded-2xl bg-fill px-3 py-2.5 text-[13px] leading-5 text-ink/80">
            I predict an average viewer&apos;s attention is lowest at{' '}
            <span className="font-mono text-ink">{clock(low)}</span> and peaks at{' '}
            <span className="font-mono text-accent">{clock(peak)}</span>.
          </p>
        </div>
      </div>
    </div>
  )
}
