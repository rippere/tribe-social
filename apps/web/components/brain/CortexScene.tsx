'use client'

import { Suspense, useEffect } from 'react'
import { Canvas, useThree } from '@react-three/fiber'
import { OrbitControls } from '@react-three/drei'
import CortexBrain, { type Activity, type CortexClock } from './CortexBrain'

// Mesh axes (see export_cortex.py): x = right, y = superior, z = posterior.
export const VIEWS = {
  left: [-4, 0.4, 0.2],
  right: [4, 0.4, 0.2],
  top: [0, 4.6, 0.01],
  front: [0, 0.4, -4],
  back: [0, 0.4, 4],
} as const satisfies Record<string, readonly [number, number, number]>

export type CortexView = keyof typeof VIEWS

function ViewRig({ view }: { view: CortexView }) {
  const camera = useThree(s => s.camera)
  const controls = useThree(s => s.controls) as { update: () => void } | null
  useEffect(() => {
    const [x, y, z] = VIEWS[view]
    camera.position.set(x, y, z)
    camera.lookAt(0, 0, 0)
    controls?.update()
  }, [camera, controls, view])
  return null
}

interface Props {
  activity: Activity | null
  clock: CortexClock
  view?: CortexView
  autoRotate?: boolean
  threshold?: number
}

export default function CortexScene({
  activity,
  clock,
  view = 'left',
  autoRotate = false,
  threshold,
}: Props) {
  const [x, y, z] = VIEWS[view]
  return (
    <Canvas
      camera={{ position: [x, y, z], fov: 35 }}
      dpr={[1, 2]}
      gl={{ antialias: true, alpha: true }}
    >
      <Suspense fallback={null}>
        <CortexBrain activity={activity} clock={clock} threshold={threshold} />
      </Suspense>
      <OrbitControls
        makeDefault
        enablePan={false}
        minDistance={2.2}
        maxDistance={7}
        autoRotate={autoRotate}
        autoRotateSpeed={0.6}
      />
      <ViewRig view={view} />
    </Canvas>
  )
}
