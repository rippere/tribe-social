export const ROI_COLS = ['vmPFC', 'TPJ', 'IFJa', 'IFJp', 'area_45', 'MT_V5'] as const
export type ROIKey = typeof ROI_COLS[number]

export const ROI_LABELS: Record<string, string> = {
  vmPFC:   'vmPFC (Valuation)',
  TPJ:     'TPJ (Social Cog.)',
  IFJa:    'IFJa (Attention)',
  IFJp:    'IFJp (Attention)',
  area_45: 'Area 45 (Language)',
  MT_V5:   'MT/V5 (Motion)',
}

export const ROI_COLORS: Record<string, string> = {
  vmPFC:   '#FFB74D',
  TPJ:     '#81C784',
  IFJa:    '#4FC3F7',
  IFJp:    '#4DD0E1',
  area_45: '#CE93D8',
  MT_V5:   '#80DEEA',
}

// Composite score + verdict now come from the API (single source of truth:
// packages/tribe_scoring/composite.py). The web only renders them.

export function pearsonR(xs: number[], ys: number[]): number {
  const n = xs.length
  if (n < 2) return 0
  const mx = xs.reduce((a, b) => a + b, 0) / n
  const my = ys.reduce((a, b) => a + b, 0) / n
  let num = 0, dx2 = 0, dy2 = 0
  for (let i = 0; i < n; i++) {
    const dx = xs[i] - mx
    const dy = ys[i] - my
    num += dx * dy
    dx2 += dx * dx
    dy2 += dy * dy
  }
  const denom = Math.sqrt(dx2 * dy2)
  return denom === 0 ? 0 : num / denom
}

export const VERDICT_COLORS = {
  POST:    '#16A34A',
  REVISE:  '#D97706',
  RETHINK: '#DC2626',
}
