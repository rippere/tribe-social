// Inference backend mode reported by GET /health.
// "mock" = no inference backend, "pod" = warm-pod (POD_URL) path active,
// "real" = RunPod serverless key+endpoint active. Precedence when both set: "real".
export type InferenceMode = 'mock' | 'pod' | 'real'

export interface TemporalPoint {
  second: number
  attention: number
  social_cognition: number
  valuation: number
}

export interface RevisionTip {
  roi: string
  score: number
  tip: string
  hook_templates: string[]
}

export interface ScoreResult {
  video_id: string
  composite_score: number
  verdict: 'POST' | 'REVISE' | 'RETHINK'
  roi: Record<string, number>
  corpus_roi_means: Record<string, number>
  weak_rois: string[]
  revision_tips: RevisionTip[]
  temporal: TemporalPoint[]
}

export interface JobResponse {
  job_id: string
  status: 'queued' | 'uploading' | 'scoring' | 'downloading' | 'analyzing' | 'complete' | 'failed'
  progress_pct: number
  message: string
  result?: ScoreResult
  error?: string
}

export interface CorpusVideo {
  video_id: string
  creator: string
  filename: string
  views?: number
  likes?: number
  shares?: number
  saves?: number
  comments?: number
  likes_per_1k?: number
  vmPFC_mean: number
  TPJ_mean: number
  IFJa_mean: number
  IFJp_mean: number
  area_45_mean: number
  MT_V5_mean: number
  composite_score: number
}

export interface CorrelationPair {
  r: number | null
  p: number | null
}

export interface CorpusStats {
  total_videos: number
  avg_composite: number
  post_count: number
  median_likes_per_1k: number
  roi_means: Record<string, number>
  correlations: Record<string, CorrelationPair>
  go_no_go: string
  composite_r: number
  rois_above_threshold: number
}
