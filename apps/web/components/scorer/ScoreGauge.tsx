'use client'

interface Props {
  /** Composite predicted response, 0–100 (from the API's composite_score). */
  score: number
}

// SVG gauge constants
const CX = 200
const CY = 170
const R = 130
const STROKE = 14

// Score 0 → 180° (left), 100 → 0° (right)
function scoreToAngle(score: number): number {
  return 180 - (score / 100) * 180
}

function polar(cx: number, cy: number, r: number, angleDeg: number) {
  const rad = (angleDeg * Math.PI) / 180
  return { x: cx + r * Math.cos(rad), y: cy - r * Math.sin(rad) }
}

function arcPath(cx: number, cy: number, r: number, startDeg: number, endDeg: number): string {
  const s = polar(cx, cy, r, startDeg)
  const e = polar(cx, cy, r, endDeg)
  const large = Math.abs(endDeg - startDeg) > 180 ? 1 : 0
  // sweep-flag 1: clockwise on screen, i.e. left → over the top → right
  return `M ${s.x} ${s.y} A ${r} ${r} 0 ${large} 1 ${e.x} ${e.y}`
}

/**
 * Neutral gauge for the overall predicted response. Deliberately has no
 * good/bad zones: the number is a read of the video, not a forecast of views.
 */
export default function ScoreGauge({ score }: Props) {
  const clamped = Math.max(0, Math.min(100, score))
  const end = scoreToAngle(clamped)

  return (
    <svg viewBox="0 0 400 190" className="w-full max-w-[260px]" role="img" aria-label={`Overall predicted response ${clamped.toFixed(1)} out of 100`}>
      <path d={arcPath(CX, CY, R, 180, 0)} fill="none" stroke="var(--line)" strokeWidth={STROKE} strokeLinecap="round" />
      {clamped > 0.5 && (
        <path d={arcPath(CX, CY, R, 180, end)} fill="none" stroke="var(--accent)" strokeWidth={STROKE} strokeLinecap="round" />
      )}
      <text x={CX} y={CY - 34} textAnchor="middle" fill="var(--ink)" fontSize="56" fontWeight="500" fontFamily="var(--font-geist-sans)">
        {clamped.toFixed(1)}
      </text>
      <text x={CX} y={CY - 6} textAnchor="middle" fill="var(--muted)" fontSize="15" fontFamily="var(--font-geist-sans)">
        out of 100
      </text>
    </svg>
  )
}
