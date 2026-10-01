'use client'

import { Suspense, useEffect, useRef } from 'react'
import { Canvas, useFrame, useThree } from '@react-three/fiber'
import * as THREE from 'three'
import CortexBrain, { useActivity, type CortexClock } from './CortexBrain'
import { HERO_SPIN, type HeroRig } from './hero-rig'

// Landing-hero cortex. Loaded only through next/dynamic (ssr: false), so three.js
// and the GLB never touch first paint. No OrbitControls: they set
// `touch-action: none` and a wheel handler, which would hijack page scroll.
// Rotation is a plain yaw/pitch rig driven by the parent's pointer handlers.

// World-space box the camera keeps in frame (mesh is unit-scaled, see
// export_cortex.py). The static fallback image is captured at exactly this
// aspect, so `object-fit: contain` on it matches the live framing.
const FRAME_W = 2.2
const FRAME_H = 2.0
const ELEVATION = 0.26 // rad, camera sits slightly above the brain
const TARGET_Y = -0.06 // the elevated view reads the brain a touch low; recentre

function Fit() {
  const camera = useThree(s => s.camera) as THREE.PerspectiveCamera
  const size = useThree(s => s.size)
  const invalidate = useThree(s => s.invalidate)
  useEffect(() => {
    const span = 2 * Math.tan(THREE.MathUtils.degToRad(camera.fov / 2))
    const aspect = size.width / Math.max(size.height, 1)
    const d = Math.max(FRAME_H / span, FRAME_W / (span * aspect))
    camera.position.set(0, TARGET_Y + Math.sin(ELEVATION) * d, Math.cos(ELEVATION) * d)
    camera.lookAt(0, TARGET_Y, 0)
    camera.updateProjectionMatrix()
    invalidate()
  }, [camera, size, invalidate])
  return null
}

function Rig({ rig, children }: { rig: HeroRig; children: React.ReactNode }) {
  const group = useRef<THREE.Group>(null)
  const invalidate = useThree(s => s.invalidate)
  useEffect(() => {
    rig.invalidate = invalidate
    return () => {
      rig.invalidate = undefined
    }
  }, [rig, invalidate])

  useFrame((_, delta) => {
    const g = group.current
    if (!g) return
    const dt = Math.min(delta, 0.05)
    if (!rig.dragging) {
      // Fling inertia eases back into the idle spin (or to rest when paused).
      const target = rig.spin ? HERO_SPIN : 0
      rig.vel += (target - rig.vel) * Math.min(1, dt * 2)
      rig.yaw += rig.vel * dt
      if (rig.spin) rig.pitch += (0 - rig.pitch) * Math.min(1, dt * 1.2)
    }
    g.rotation.set(rig.pitch, rig.yaw, 0)
  })

  return <group ref={group}>{children}</group>
}

/** Fires once the mesh and the first TRIBE frame have actually been drawn. */
function Ready({ armed, onReady }: { armed: boolean; onReady: () => void }) {
  const fired = useRef(false)
  useFrame(() => {
    if (fired.current || !armed) return
    fired.current = true
    requestAnimationFrame(() => onReady())
  })
  return null
}

interface Props {
  clock: CortexClock
  rig: HeroRig
  frameloop: 'always' | 'demand' | 'never'
  threshold: number
  onReady: () => void
}

export default function CortexHeroScene({ clock, rig, frameloop, threshold, onReady }: Props) {
  const activity = useActivity()
  return (
    <Canvas
      frameloop={frameloop}
      camera={{ fov: 30, near: 0.1, far: 50, position: [0, 1, 5] }}
      dpr={[1, 1.75]}
      gl={{ antialias: true, alpha: true }}
      style={{ touchAction: 'pan-y' }}
      aria-hidden
    >
      <Fit />
      <Suspense fallback={null}>
        <Rig rig={rig}>
          <CortexBrain activity={activity} clock={clock} threshold={threshold} />
        </Rig>
        <Ready armed={activity !== null} onReady={onReady} />
      </Suspense>
    </Canvas>
  )
}
