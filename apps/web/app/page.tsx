import Link from 'next/link'
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
export default function HomePage() {
  return (
    <>
      {/* Parts 2–4: announcement, headline, the scorer as the hero */}
      <section className="mx-auto max-w-[1232px] px-6 pt-16 text-center md:pt-24">
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

        <h1 className="type-h1 mt-8 text-ink">
          Meet <MascotGlyph className="mx-1 h-[0.9em] w-[0.9em] -translate-y-[0.06em]" /> fMRIght
        </h1>
        <p className="type-lead mx-auto mt-5 max-w-xl">
          See what a video does to a brain before you post it. fMRIght predicts how an average viewer&apos;s brain
          responds, second by second, and explains it in plain English.
        </p>

        <div className="mt-8 flex justify-center gap-2">
          <Link href="/scorer" className="btn-primary btn-lg">
            Score a clip
          </Link>
          <Link href="#how-it-works" className="btn-secondary btn-lg">
            How it works
          </Link>
        </div>

        <div className="mt-16">
          <HeroDemo />
        </div>
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
