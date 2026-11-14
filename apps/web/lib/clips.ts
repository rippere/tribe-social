import macAndCheese from './clip-context.json'

/**
 * Clips with a real TRIBE v2 prediction, shown in the gallery (/clips) and on each
 * clip's page. Each context file is built by research/clip_chat_context.py from the
 * clip's per-second prediction; only clips we own or have permission to show go here.
 */
export type ClipContext = typeof macAndCheese

export type Clip = {
  slug: string
  title: string
  blurb: string
  video: string
  poster: string
  /** Directory holding the cortex activity.{json,bin} for this clip. */
  cortexBase: string
  context: ClipContext
  suggestions: string[]
}

export const CLIPS: Clip[] = [
  {
    slug: 'mac-and-cheese',
    title: 'The boxed mac and cheese hack',
    blurb: 'A fast hook, a flat how-to middle, a cheese-pull payoff. AI-generated creator clip, three 8-second shots.',
    video: '/media/mac-and-cheese.mp4',
    poster: '/media/mac-and-cheese.jpg',
    cortexBase: '/cortex',
    context: macAndCheese,
    suggestions: [
      'What happens in the first 3 seconds?',
      'Where is the predicted response strongest?',
      'Does the flat instructions shot lose anything?',
      "What can't this model tell me?",
    ],
  },
]

export function getClip(slug: string): Clip | undefined {
  return CLIPS.find(c => c.slug === slug)
}

export const REGION_KEYS = Object.keys(macAndCheese.regions) as (keyof ClipContext['regions'])[]
export type ClipRegion = (typeof REGION_KEYS)[number]

/** m:ss for a whole number of seconds. */
export function clock(s: number): string {
  const t = Math.max(0, Math.round(s))
  return `${Math.floor(t / 60)}:${String(t % 60).padStart(2, '0')}`
}
