import Link from 'next/link'
import CortexHero from '@/components/landing/CortexHero'
import HeroDemo from '@/components/landing/HeroDemo'
import { Faq, UseCases } from '@/components/landing/Interactive'
import {
  BrainScanPanel,
  FinalCta,
  HowItWorks,
  MascotGlyph,
  PREREG_URL,
  Pricing,
  Science,
  SeeItInAction,
} from '@/components/landing/Sections'

// Landing page, laid out part by part on the x.ai/bot format
// (business/lanes/design-ref/DESIGN-SPEC.md), dark variant per docs/CORTEX-VIEW.md.
// Hero: the real cortex playing TRIBE v2's per-second prediction for the sample clip
// (decided with Ben 2026-10-01; supersedes "scorer is the hero"). The scorer replay
// follows directly below.
export default function HomePage() {
  return (
    <>
      {/* Parts 2–4: announcement, headline, the cortex as the hero */}
      <section className="mx-auto grid max-w-[1232px] items-center gap-4 px-6 pt-10 md:pt-16 lg:min-h-[min(820px,calc(100svh-64px))] lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)] lg:gap-4 lg:pt-0">
        <div className="text-center lg:text-left">
          <a
            href={PREREG_URL}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-2 rounded-full py-1.5 pr-1.5 pl-3 text-[14px] text-ink shadow-[var(--shadow-hairline)] transition-colors hover:bg-fill"
          >
            The hook test is pre-registered · Read the plan
            <span aria-hidden className="flex h-5 w-5 items-center justify-center rounded-full bg-fill text-[11px]">
              ↗
            </span>
          </a>

          <h1 className="type-h1 mt-6 text-ink md:mt-8">
            Meet <MascotGlyph className="mx-1 h-[0.9em] w-[0.9em] -translate-y-[0.06em]" /> fMRIght
          </h1>
          <p className="type-lead mx-auto mt-5 max-w-xl lg:mx-0 lg:max-w-[440px]">
            See what a video does to a brain before you post it. fMRIght predicts how an average viewer&apos;s brain
            responds, second by second, and explains it in plain English.
          </p>

          <div className="mt-7 flex justify-center gap-2 md:mt-8 lg:justify-start">
            <Link href="/scorer" className="btn-primary btn-lg">
              Score a clip
            </Link>
            <Link href="#how-it-works" className="btn-secondary btn-lg">
              How it works
            </Link>
          </div>
        </div>

        <CortexHero />
      </section>

      {/* The scorer, replayed on sample data, right under the hero */}
      <section className="mx-auto max-w-[1232px] px-6 pt-20 md:pt-28">
        <HeroDemo />
      </section>

      <BrainScanPanel />
      <HowItWorks />
      <UseCases />
      <SeeItInAction />
      <Pricing />
      <Science />
      <Faq />
      <FinalCta />
    </>
  )
}
