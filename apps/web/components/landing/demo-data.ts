import type { PipelineStage, RegionKey } from '@/components/brain/contract'

/**
 * SAMPLE data for the hero's guided demo. Illustrative only: not a real scored
 * clip. Every surface that renders it shows a "Sample" label. Replace with the
 * saved result of the team's demo clip once it is filmed and scored.
 */
export const IS_SAMPLE = true

export const DEMO_CLIP = {
  title: 'Sample clip',
  seconds: 18,
}

export interface DemoStage {
  key: Exclude<PipelineStage, 'idle'>
  label: string
  /** How long the stage plays in the demo, in ms. */
  duration: number
  /** Plain-language explanation shown while the stage runs. */
  heading: string
  body: string
  /** Regions lit on the brain during this stage (0–1). */
  regions: Partial<Record<RegionKey, number>>
}

export const DEMO_STAGES: DemoStage[] = [
  {
    key: 'upload',
    label: 'Upload',
    duration: 3500,
    heading: 'Your video goes to a rented GPU',
    body: 'Brain models need a lot of computing power, so the video is sent to a graphics card we rent in the cloud by the second.',
    regions: {},
  },
  {
    key: 'encode',
    label: 'Encode',
    duration: 5000,
    heading: 'A model predicts the brain’s response',
    body: 'Meta’s TRIBE v2 watches the frames, hears the audio and reads the words. It learned from brain scans of people watching videos, so it can predict a response without a scanner.',
    regions: { attention: 0.35, auditory: 0.3, motion: 0.3, language: 0.25, social: 0.25, valuation: 0.2, narrative: 0.2 },
  },
  {
    key: 'extract',
    label: 'Extract',
    duration: 5000,
    heading: 'We zoom in on seven brain areas',
    body: 'The prediction covers thousands of points on the brain’s surface. We average them into seven areas tied to watching a video: attention, reading people, language, sound, motion, story and value.',
    regions: { attention: 0.9, social: 0.7, language: 0.5, valuation: 0.6, auditory: 0.5, motion: 0.6, narrative: 0.4 },
  },
  {
    key: 'read',
    label: 'Read',
    duration: 7000,
    heading: 'You get a second-by-second read',
    body: 'Rises are where an average brain is predicted to lock in; dips are where it’s predicted to drift. It’s a read of the video, not a promise of views.',
    regions: { attention: 0.8, social: 0.6, valuation: 0.5 },
  },
]

/** Sample predicted-attention curve, one point per second (0–1). */
export const DEMO_TIMELINE: number[] = [
  0.42, 0.61, 0.78, 0.74, 0.66, 0.58, 0.49, 0.44, 0.47, 0.55,
  0.63, 0.71, 0.69, 0.6, 0.52, 0.5, 0.57, 0.62,
]

/** Sample callouts pinned to the timeline. */
export const DEMO_CALLOUTS = [
  { second: 2, text: 'Hook lands' },
  { second: 7, text: 'Talking stretch: attention drifts' },
  { second: 11, text: 'Reveal pulls it back' },
]
