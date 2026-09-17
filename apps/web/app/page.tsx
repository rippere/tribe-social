import BrainHero from '@/components/brain/BrainHero'

// Stripped hero: off-black canvas, 3D brain centerpiece, no copy yet.
// Language + CTAs return once the feature set is cemented.
export default function HomePage() {
  return (
    <section className="flex min-h-[calc(100vh-3.5rem)] items-center justify-center overflow-hidden bg-bg px-6">
      <BrainHero />
    </section>
  )
}
