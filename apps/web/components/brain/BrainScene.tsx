'use client'

import { Canvas } from '@react-three/fiber'
import { OrbitControls, MeshDistortMaterial } from '@react-three/drei'
import { Suspense } from 'react'

// Placeholder brain: a lumpy, slowly-morphing icosahedron standing in for the
// real GLB. Swap in the model when it lands (see BrainModel below).
function PlaceholderBrain() {
  return (
    <mesh scale={1.6}>
      <icosahedronGeometry args={[1, 6]} />
      <MeshDistortMaterial
        color="#6366F1"
        emissive="#4338CA"
        emissiveIntensity={0.35}
        roughness={0.35}
        metalness={0.15}
        distort={0.38}
        speed={1.4}
      />
    </mesh>
  )
}

// When the real asset is ready, drop it in apps/web/public/ and swap
// <PlaceholderBrain /> for <BrainModel url="/brain.glb" />:
//
//   import { useGLTF } from '@react-three/drei'
//   function BrainModel({ url }: { url: string }) {
//     const { scene } = useGLTF(url)
//     return <primitive object={scene} scale={2} />
//   }
//   useGLTF.preload('/brain.glb')

export default function BrainScene() {
  return (
    <Canvas
      camera={{ position: [0, 0, 5], fov: 45 }}
      dpr={[1, 2]}
      gl={{ antialias: true, alpha: true }}
    >
      <ambientLight intensity={0.4} />
      <directionalLight position={[4, 6, 5]} intensity={1.1} />
      <pointLight position={[-5, -3, -4]} intensity={0.6} color="#818CF8" />
      <Suspense fallback={null}>
        <PlaceholderBrain />
      </Suspense>
      <OrbitControls
        enableZoom={false}
        enablePan={false}
        autoRotate
        autoRotateSpeed={0.8}
      />
    </Canvas>
  )
}
