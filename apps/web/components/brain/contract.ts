/**
 * Integration contract between the fMRIght page and the 3D brain / mascot model.
 *
 * The hero runs a guided, real-time scoring demo. As the job moves through its
 * stages the page passes the current stage and per-region intensities down to
 * the 3D brain, which lights the matching cortical regions. Any brain component
 * that accepts `BrainSceneProps` (default export, client-only, no SSR) drops into
 * the hero and the "How it works" section unchanged.
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

export interface BrainSceneProps {
  /** Current pipeline stage; 'idle' before a clip is dropped in. */
  stage?: PipelineStage
  /** 0–1 intensity per region for the current moment; omitted regions stay dark. */
  regions?: Partial<Record<RegionKey, number>>
  /** Region to spotlight (e.g. the one the mascot is explaining). */
  focus?: RegionKey | null
  className?: string
}

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
