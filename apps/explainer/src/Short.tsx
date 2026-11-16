import { buildScenes, ExplainerCut, scenesDuration, type Narration, type Orientation, type SceneSpec } from './Explainer'
import narration from './data/narration_short.json'

/*
 * The ~30 s short for a LinkedIn post: four of v6's beats with their v6 visuals,
 * then a silent end card. Narration is Ben's takes cut by scripts/short_vo.py
 * (b1 without the old product name, b2's first sentence, b6 and b8 whole).
 * b3, b4, b5, b7 (the lag, so the read line never slides here) and b9 are left out.
 */
const SPECS: SceneSpec[] = [
  { key: 'intro', lines: ['s1_intro'], mascot: 'walk-in' },
  { key: 'upload', lines: ['s2_upload'], mascot: 'idle' },
  { key: 'read', lines: ['b6_read', 'b8_read2'], mascot: 'idle' },
  { key: 'end', seconds: 3.5, mascot: 'idle' },
]

const NARRATION = narration as Narration
const SCENES = buildScenes(SPECS, NARRATION)

// Lines are mono at -16 LUFS; the stereo render doubles the channel (+3 LU), so take
// 3 dB off to land the short itself near -16 LUFS integrated.
const VOLUME = 10 ** (-3 / 20)

export function shortDuration(): number {
  return scenesDuration(SCENES)
}

export function Short({ orientation }: { orientation: Orientation }) {
  return <ExplainerCut orientation={orientation} scenes={SCENES} narr={NARRATION} brand="PrePost" volume={VOLUME} />
}
