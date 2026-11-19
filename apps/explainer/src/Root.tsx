import { Composition } from 'remotion'
import { Explainer, explainerDuration } from './Explainer'
import { FPS } from './theme'

export function Root() {
  const durationInFrames = explainerDuration()
  return (
    <>
      <Composition
        id="Explainer-16x9"
        component={Explainer}
        width={1920}
        height={1080}
        fps={FPS}
        durationInFrames={durationInFrames}
        defaultProps={{ orientation: 'landscape' as const }}
      />
      <Composition
        id="Explainer-9x16"
        component={Explainer}
        width={1080}
        height={1920}
        fps={FPS}
        durationInFrames={durationInFrames}
        defaultProps={{ orientation: 'portrait' as const }}
      />
    </>
  )
}
