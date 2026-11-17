// Map the RunPod handler's output onto what the trial result page renders.
//
// The mapping mirrors apps/api (services/inference.py): ROI means go through the same
// provisional (v + 0.5) / 2 squash, and composite_raw is min-max scaled onto 0-100
// against the pilot corpus range (packages/tribe_scoring/composite.py scale_to_100).
// Unlike the API, the per-second curves here are the model's own output.

import type { ScoreResult, TemporalPoint } from '../types'

// From apps/api/data/corpus.json stats (pilot corpus, n = 24). Update both together.
export const CORPUS_COMPOSITE_RAW = { min: -0.049873, max: 0.068024 }
export const CORPUS_ROI_MEANS: Record<string, number> = {
  vmPFC: 0.5965,
  TPJ: 0.5643,
  IFJa: 0.5686,
  IFJp: 0.5686,
  area_45: 0.5982,
  MT_V5: 0.5698,
}

export const ROI_DIMS = ['attention', 'social', 'language', 'valuation', 'auditory', 'motion', 'narrative'] as const

export interface HandlerOutput {
  n_seconds: number
  composite_raw: number
  label?: string
  series: Partial<Record<(typeof ROI_DIMS)[number] | 'gfp', number[]>>
  activity?: { frames: number; vertices: number; hz: number; scale: number; uploaded: boolean }
  timings?: Record<string, number | boolean | null>
  [k: string]: unknown
}

export interface TrialResult {
  score: ScoreResult
  n_seconds: number
  /** Raw per-second TRIBE means per ROI (and global field power). */
  series: HandlerOutput['series']
  activity: { frames: number; vertices: number; hz: number } | null
}

const squash = (v: number) => Math.max(0, Math.min(1, (v + 0.5) / 2))
const r4 = (v: number) => Math.round(v * 1e4) / 1e4

export function isHandlerOutput(o: unknown): o is HandlerOutput {
  if (!o || typeof o !== 'object') return false
  const h = o as HandlerOutput
  return (
    typeof h.n_seconds === 'number' &&
    typeof h.composite_raw === 'number' &&
    !!h.series &&
    Array.isArray(h.series.attention) &&
    Array.isArray(h.series.social) &&
    Array.isArray(h.series.valuation)
  )
}

export function buildTrialResult(jobId: string, out: HandlerOutput, hasActivity: boolean): TrialResult {
  const mean = (k: string) => {
    const v = out[`${k}_mean`]
    return typeof v === 'number' ? v : 0
  }
  const roi = {
    vmPFC: r4(squash(mean('valuation'))),
    TPJ: r4(squash(mean('social'))),
    IFJa: r4(squash(mean('attention'))),
    IFJp: r4(squash(mean('attention'))), // proxy, no dedicated mask (same as the API)
    area_45: r4(squash(mean('language'))),
    MT_V5: r4(squash(mean('motion'))),
  }
  const { min, max } = CORPUS_COMPOSITE_RAW
  const composite = Math.max(0, Math.min(100, ((out.composite_raw - min) / (max - min)) * 100))

  const s = out.series
  const temporal: TemporalPoint[] = (s.attention ?? []).map((_, i) => ({
    second: i,
    attention: r4(squash(s.attention?.[i] ?? 0)),
    social_cognition: r4(squash(s.social?.[i] ?? 0)),
    valuation: r4(squash(s.valuation?.[i] ?? 0)),
  }))

  return {
    score: {
      video_id: `trial_${jobId.slice(0, 8)}`,
      composite_score: Math.round(composite * 10) / 10,
      // Required by the shared type; never shown (it implies a performance forecast).
      verdict: 'REVISE',
      roi,
      corpus_roi_means: CORPUS_ROI_MEANS,
      weak_rois: [],
      revision_tips: [],
      temporal,
    },
    n_seconds: out.n_seconds,
    series: s,
    activity:
      hasActivity && out.activity ? { frames: out.activity.frames, vertices: out.activity.vertices, hz: out.activity.hz } : null,
  }
}
