/**
 * Shared vocabulary for the scoring pipeline and brain regions, used by the landing
 * walkthrough and the scorer. The 3D cortex itself (docs/CORTEX-VIEW.md) renders
 * per-vertex TRIBE output and lives on the processing page, not here.
 */

/** Pipeline stages, in order. Mirrors the scorer's progress stages. */
export type PipelineStage = 'idle' | 'upload' | 'encode' | 'extract' | 'read'

/** Functional regions, keyed exactly as quick_scores() emits them. */
export type RegionKey =
  | 'attention'
  | 'social'
  | 'language'
  | 'valuation'
  | 'auditory'
  | 'motion'
  | 'narrative'

/** Plain-language names used in the page copy and region labels. */
export const REGION_LABELS: Record<RegionKey, string> = {
  attention: 'Attention',
  social: 'Social: reading people',
  language: 'Language',
  valuation: 'Value: "is this worth it?"',
  auditory: 'Sound',
  motion: 'Motion',
  narrative: 'Story',
}
