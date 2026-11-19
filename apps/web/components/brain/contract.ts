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

/**
 * The scorer API reports anatomical ROI keys (and display names in revision tips).
 * Map each to its functional region so the UI can show plain-language names.
 */
export const ANATOMICAL_TO_REGION: Record<string, RegionKey> = {
  vmPFC: 'valuation',
  TPJ: 'social',
  IFJa: 'attention',
  IFJp: 'attention',
  area_45: 'language',
  'Area 45': 'language',
  MT_V5: 'motion',
  'MT/V5': 'motion',
}

const ANATOMICAL_DISPLAY: Record<string, string> = {
  area_45: 'Area 45',
  MT_V5: 'MT/V5',
}

/** "Value: "is this worth it?" (vmPFC)"; falls back to the raw key when unmapped. */
export function regionLabel(anatomicalKey: string): string {
  const region = ANATOMICAL_TO_REGION[anatomicalKey]
  const anat = ANATOMICAL_DISPLAY[anatomicalKey] ?? anatomicalKey
  return region ? `${REGION_LABELS[region]} (${anat})` : anat
}

/** Short plain name without the anatomical suffix, for tight chart axes. */
export function regionShortLabel(anatomicalKey: string): string {
  const region = ANATOMICAL_TO_REGION[anatomicalKey]
  if (!region) return ANATOMICAL_DISPLAY[anatomicalKey] ?? anatomicalKey
  const short: Record<RegionKey, string> = {
    attention: 'Attention',
    social: 'Social',
    language: 'Language',
    valuation: 'Value',
    auditory: 'Sound',
    motion: 'Motion',
    narrative: 'Story',
  }
  // IFJa and IFJp both map to attention; keep them distinguishable on the radar.
  return anatomicalKey === 'IFJp' ? 'Attention (p)' : anatomicalKey === 'IFJa' ? 'Attention (a)' : short[region]
}
