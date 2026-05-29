'use client'

interface Props {
  score: number
  verdict: 'POST' | 'REVISE' | 'RETHINK'
}

const VERDICT_CONFIG = {
  POST:    { color: '#16A34A', label: 'POST',    bg: 'rgba(22,163,74,0.15)' },
  REVISE:  { color: '#D97706', label: 'REVISE',  bg: 'rgba(217,119,6,0.15)' },
  RETHINK: { color: '#DC2626', label: 'RETHINK', bg: 'rgba(220,38,38,0.15)' },
}

// SVG gauge constants
const CX = 200
const CY = 160
const R = 120
const STROKE = 18

// Convert score 0–100 to angle in degrees (arc spans 180° from 180° to 0°)
// At score 0 → needle points left (180°). At score 100 → points right (0°).
function scoreToAngle(score: number): number {
  return 180 - (score / 100) * 180 // degrees from positive x-axis
}

// Polar to cartesian
function polar(cx: number, cy: number, r: number, angleDeg: number) {
  const rad = (angleDeg * Math.PI) / 180
  return {
    x: cx + r * Math.cos(rad),
    y: cy - r * Math.sin(rad),
  }
}

// SVG arc path for a segment of the gauge
function arcPath(
  cx: number,
  cy: number,
  r: number,
  startDeg: number,
  endDeg: number,
): string {
  const s = polar(cx, cy, r, startDeg)
  const e = polar(cx, cy, r, endDeg)
  const large = Math.abs(endDeg - startDeg) > 180 ? 1 : 0
  // Going from startDeg down to endDeg (clockwise in SVG)
  return `M ${s.x} ${s.y} A ${r} ${r} 0 ${large} 0 ${e.x} ${e.y}`
}

export default function ScoreGauge({ score, verdict }: Props) {
  const cfg = VERDICT_CONFIG[verdict]
  const needleAngle = scoreToAngle(Math.max(0, Math.min(100, score)))

  // Needle tip
  const tip = polar(CX, CY, R - 10, needleAngle)
  // Needle base (short stub in opposite direction)
  const base = polar(CX, CY, 18, needleAngle + 180)

  // Zone boundaries (score 0 at 180°, 100 at 0°)
  // Rethink: 180° → 108° (0–40), Revise: 108° → 63° (40–65), Post: 63° → 0°
  const rethinkEnd = scoreToAngle(40)  // 108°
  const reviseEnd  = scoreToAngle(65)  // 63°

  return (
    <div className="flex flex-col items-center">
      <svg viewBox="0 0 400 200" className="w-full max-w-xs">
        <defs>
          <filter id="needle-glow">
            <feGaussianBlur stdDeviation="2" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        {/* Background track */}
        <path
          d={arcPath(CX, CY, R, 180, 0)}
          fill="none"
          stroke="#1F2937"
          strokeWidth={STROKE + 4}
          strokeLinecap="butt"
        />

        {/* Rethink zone (180° → rethinkEnd) */}
        <path
          d={arcPath(CX, CY, R, 180, rethinkEnd)}
          fill="none"
          stroke="#DC2626"
          strokeWidth={STROKE}
          strokeLinecap="butt"
          opacity={0.7}
        />

        {/* Revise zone (rethinkEnd → reviseEnd) */}
        <path
          d={arcPath(CX, CY, R, rethinkEnd, reviseEnd)}
          fill="none"
          stroke="#D97706"
          strokeWidth={STROKE}
          strokeLinecap="butt"
          opacity={0.7}
        />

        {/* Post zone (reviseEnd → 0°) */}
        <path
          d={arcPath(CX, CY, R, reviseEnd, 0)}
          fill="none"
          stroke="#16A34A"
          strokeWidth={STROKE}
          strokeLinecap="butt"
          opacity={0.7}
        />

        {/* Needle */}
        <line
          x1={base.x}
          y1={base.y}
          x2={tip.x}
          y2={tip.y}
          stroke={cfg.color}
          strokeWidth={3}
          strokeLinecap="round"
          filter="url(#needle-glow)"
        />

        {/* Center hub */}
        <circle cx={CX} cy={CY} r={8} fill={cfg.color} />
        <circle cx={CX} cy={CY} r={4} fill="#0D0D0D" />

        {/* Score text */}
        <text
          x={CX}
          y={CY - 28}
          textAnchor="middle"
          fill="#F9FAFB"
          fontSize="36"
          fontWeight="700"
          fontFamily="var(--font-geist-sans)"
        >
          {score.toFixed(1)}
        </text>

        {/* /100 label */}
        <text
          x={CX}
          y={CY - 10}
          textAnchor="middle"
          fill="#9CA3AF"
          fontSize="12"
          fontFamily="var(--font-geist-sans)"
        >
          / 100
        </text>

        {/* Zone labels */}
        <text x="28" y={CY + 24} fill="#DC2626" fontSize="10" textAnchor="middle" opacity={0.7}>Rethink</text>
        <text x={CX} y={CY - R - 10} fill="#D97706" fontSize="10" textAnchor="middle" opacity={0.7}>Revise</text>
        <text x={CX * 2 - 28} y={CY + 24} fill="#16A34A" fontSize="10" textAnchor="middle" opacity={0.7}>Post</text>
      </svg>

      {/* Verdict badge */}
      <div
        className="mt-2 px-5 py-1.5 rounded-full text-sm font-bold tracking-wider"
        style={{ color: cfg.color, background: cfg.bg, border: `1px solid ${cfg.color}40` }}
      >
        {cfg.label}
      </div>
    </div>
  )
}
