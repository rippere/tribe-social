'use client'

import dynamic from 'next/dynamic'

// three.js / r3f are client-only — load the scene without SSR.
const BrainScene = dynamic(() => import('./BrainScene'), { ssr: false })

export default function BrainHero() {
  return (
    <div className="h-[70vh] w-full max-w-3xl">
      <BrainScene />
    </div>
  )
}
