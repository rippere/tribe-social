// Map the RunPod handler's output onto what the trial result page renders.
//
// Every number is placed on the pilot corpus's own scale, so "vs. the corpus average"
// compares like with like: each ROI mean is min-max scaled against the corpus's raw
// range for that ROI (exactly how apps/api/scripts/build_corpus_json.py normalised the
// corpus, whose 0-1 means are CORPUS_ROI_MEANS), and composite_raw is scaled onto
// 0-100 the same way (packages/tribe_scoring/composite.py scale_to_100). Values outside
// the corpus range clip to 0 or 1. The per-second curves are the model's own output.

import type { ScoreResult, TemporalPoint } from '../types'

// From apps/api/data/corpus.json stats (pilot corpus, n = 24). Update both together.
export const CORPUS_COMPOSITE_RAW = { min: -0.049873, max: 0.068024 }
// Raw quick_scores() ROI-mean ranges over the same 24 clips (research/scores.csv).
// IFJp in the corpus is 0.9 × IFJa, which min-max scales to the same value as IFJa.
export const CORPUS_ROI_RAW: Record<string, { key: string; min: number; max: number }> = {
  vmPFC: { key: 'valuation_mean', min: -0.044544, max: 0.081476 },
  TPJ: { key: 'social_mean', min: -0.026415, max: 0.085105 },
  IFJa: { key: 'attention_mean', min: -0.062311, max: 0.083713 },
  IFJp: { key: 'attention_mean', min: -0.062311, max: 0.083713 },
  area_45: { key: 'language_mean', min: -0.092807, max: 0.062853 },
  MT_V5: { key: 'motion_mean', min: -0.074706, max: 0.038684 },
}
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

const clamp01 = (v: number) => Math.max(0, Math.min(1, v))
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
  const roi: Record<string, number> = {}
  for (const [name, { key, min, max }] of Object.entries(CORPUS_ROI_RAW)) {
    const v = out[key]
    roi[name] = r4(clamp01(((typeof v === 'number' ? v : 0) - min) / (max - min)))
  }
  const { min, max } = CORPUS_COMPOSITE_RAW
  const composite = Math.max(0, Math.min(100, ((out.composite_raw - min) / (max - min)) * 100))

  const s = out.series
  // Raw TRIBE units (signed, near 0): the chart fits its axis to the data.
  const r6 = (v: number) => Math.round(v * 1e6) / 1e6
  const temporal: TemporalPoint[] = (s.attention ?? []).map((_, i) => ({
    second: i,
    attention: r6(s.attention?.[i] ?? 0),
    social_cognition: r6(s.social?.[i] ?? 0),
    valuation: r6(s.valuation?.[i] ?? 0),
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
