import type { Metadata } from 'next'
import Link from 'next/link'
import { REGION_LABELS, type RegionKey } from '@/components/brain/contract'
import { PREREG_URL, REGION_DOT, REPO } from '@/components/landing/Sections'

export const metadata: Metadata = {
  title: 'The science · PrePost',
  description:
    'What PrePost measures, what the evidence says so far (including the parts that went against us) and the pre-registered test that will decide whether the brain read adds anything.',
}

// Anatomy per area, as the sample clip's context file names it (lib/clip-context.json).
const AREAS: { key: RegionKey; anatomy: string; plain: string }[] = [
  { key: 'attention', anatomy: 'Inferior frontal junction (IFJ)', plain: 'Holding focus on what matters on screen.' },
  { key: 'social', anatomy: 'Temporo-parietal junction / angular gyrus', plain: 'Reading people: faces, intentions, reactions.' },
  { key: 'language', anatomy: 'Broca’s area (44/45)', plain: 'Processing spoken and written words.' },
  { key: 'valuation', anatomy: 'Ventromedial prefrontal / subgenual cingulate', plain: 'Weighing whether something is worth it.' },
  { key: 'auditory', anatomy: 'Superior temporal cortex / STS', plain: 'Voice, music and sound.' },
  { key: 'motion', anatomy: 'MT/V5 complex', plain: 'Movement on screen.' },
  { key: 'narrative', anatomy: 'Posterior cingulate / precuneus', plain: 'Following a story over time.' },
]

const VERDICTS = [
  { name: 'GO', when: 'Both primary tests clear and the negative control stays clean.', then: 'Replicate on fresh videos before any product claim.' },
  { name: 'NO-GO', when: 'Both primary tests fail.', then: 'The brain layer adds nothing here. We publish that, and the product becomes a content scorer or stops.' },
  { name: 'INCONCLUSIVE', when: 'Mixed results, or the test turns out too small to see the effect.', then: 'One costed re-run with more videos, or stop. No claim either way.' },
  { name: 'INSTRUMENT FAILURE', when: 'Ad delivery breaks the design, or the negative control passes.', then: 'Fix the setup, report the failure, re-run once.' },
]

export default function SciencePage() {
  return (
    <div className="mx-auto max-w-[880px] px-6 pt-12 md:pt-20">
      <p className="font-mono text-[13px] text-accent">The science</p>
      <h1 className="type-h1 mt-4 text-ink">What we measure, what we know, and how we&apos;re testing it</h1>
      <p className="type-lead mt-6">
        The homepage keeps it short. This page is the long version, for anyone who wants to check our work before
        trusting a read.
      </p>

      <Section title="In one paragraph">
        <p>
          PrePost runs Meta FAIR&apos;s TRIBE v2, a model trained on brain scans (fMRI) of people watching and listening
          to media. Given a new video, it predicts the brain response an average viewer would likely have, once per
          second, across the cortex. We summarize that into seven brain areas and a timeline. It is a{' '}
          <strong className="font-medium text-ink">diagnostic</strong>: it shows which moments the model expects to land
          and which to fall flat. It is not yet a forecast of views or retention, and we don&apos;t claim it is.
        </p>
      </Section>

      <Section title="What a read contains">
        <ul className="list-disc space-y-2 pl-5">
          <li>
            <strong className="font-medium text-ink">A per-second timeline</strong> of the predicted whole-cortex response.
            The units are the model&apos;s own z-scored scale, so compare moments within a clip, not raw numbers across
            clips.
          </li>
          <li>
            <strong className="font-medium text-ink">Seven brain areas</strong>, so you can see whether a moment works
            through the visuals, the voice, the people on screen or the story.
          </li>
          <li>
            <strong className="font-medium text-ink">Plain-English notes with timestamps</strong>, computed from those
            numbers: the weakest and strongest stretches, how each shot compares, which area does the most work.
          </li>
        </ul>
        <div className="mt-6 overflow-hidden rounded-[16px] shadow-[var(--shadow-hairline)]">
          <table className="w-full text-left text-[14px] leading-[22px]">
            <thead className="bg-elevated text-ink">
              <tr>
                <th className="px-4 py-3 font-medium">Area</th>
                <th className="px-4 py-3 font-medium">Roughly tracks</th>
                <th className="hidden px-4 py-3 font-medium sm:table-cell">Anatomy</th>
              </tr>
            </thead>
            <tbody>
              {AREAS.map(a => (
                <tr key={a.key} className="border-t border-line">
                  <td className="px-4 py-3 text-ink">
                    <span className="inline-flex items-center gap-2">
                      <span className={`h-2 w-2 shrink-0 rounded-full ${REGION_DOT[a.key]}`} />
                      {REGION_LABELS[a.key]}
                    </span>
                  </td>
                  <td className="px-4 py-3">{a.plain}</td>
                  <td className="hidden px-4 py-3 sm:table-cell">{a.anatomy}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-3 text-[13px] text-muted">
          Areas are Destrieux-atlas approximations on the fsaverage surface. &ldquo;Roughly tracks&rdquo; is a
          simplification: no brain area does one job.
        </p>
      </Section>

      <Section title="The evidence so far, including what went against us">
        <ul className="list-disc space-y-3 pl-5">
          <li>
            <strong className="font-medium text-ink">The model itself is well validated</strong> at what it was built
            for: predicting brain responses to movies and audio. It placed first in the Algonauts 2025 challenge.
          </li>
          <li>
            <strong className="font-medium text-ink">Our first pilot did not show a reliable link to engagement.</strong>{' '}
            Across 24 videos, the correlation between the read and engagement was r = 0.25 with p = 0.24. That is weak,
            and with only 24 videos it could easily be chance. It neither proves nor rules out a real effect.
          </li>
          <li>
            <strong className="font-medium text-ink">An outside study points the same way.</strong> Sahu &amp; Pandey
            (arXiv:2607.01400, 2026) found TRIBE&apos;s predicted signal did not predict YouTube re-watching.
          </li>
        </ul>
        <p className="mt-4">
          Put together: a brain response the model predicts well is not the same thing as a video that performs well,
          and so far nobody has shown the second follows from the first for short-form video. That is the gap our test
          is built to close, or to confirm can&apos;t be closed.
        </p>
      </Section>

      <Section title="The pre-registered hook test">
        <p>
          <strong className="font-medium text-ink">The question:</strong> does adding the predicted brain response to a
          content-only model (visuals, loudness, motion, transcript, length) improve prediction of how many people watch
          past the first three seconds? If the brain read only restates things a cheaper model already sees, it adds
          nothing, and the test is designed to catch that.
        </p>
        <ul className="mt-4 list-disc space-y-2 pl-5">
          <li>
            <strong className="font-medium text-ink">Stimuli:</strong> 18 short base videos shot by our team, each cut
            with 4 different openings, for 72 clips. Only the opening changes inside each set.
          </li>
          <li>
            <strong className="font-medium text-ink">Delivery:</strong> each clip runs as its own ad with an equal daily
            budget, all starting and stopping together for at least three days, targeting about 1,000 impressions per
            clip (about $580 in ad spend).
          </li>
          <li>
            <strong className="font-medium text-ink">Outcome:</strong> hook rate, meaning 3-second plays divided by
            impressions, as the platform reports it.
          </li>
          <li>
            <strong className="font-medium text-ink">Blind scoring:</strong> every clip is scored before any performance
            data exists.
          </li>
          <li>
            <strong className="font-medium text-ink">Bars set in advance:</strong> the brain read has to track hook rate
            within each set of openings, and the combined model has to beat the content-only model by a fixed margin
            under cross-validation and a permutation test. A negative control, the same pipeline with random features in
            place of the brain read, must fail. If it passes, the result is void.
          </li>
          <li>
            <strong className="font-medium text-ink">Power:</strong> simulated before freezing, the design detects a
            moderate effect (rho 0.4) with about 90% power.
          </li>
        </ul>

        <h3 className="type-h3 mt-8 text-ink">The four possible verdicts, decided before the data</h3>
        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          {VERDICTS.map(v => (
            <div key={v.name} className="rounded-[16px] bg-panel p-5">
              <p className="font-mono text-[13px] text-accent">{v.name}</p>
              <p className="mt-2 text-[14px] leading-[22px] text-ink">{v.when}</p>
              <p className="mt-1 text-[14px] leading-[22px]">{v.then}</p>
            </div>
          ))}
        </div>
        <p className="mt-4">
          Whatever the verdict, we publish it, with the effect size, its confidence interval and the population it
          applies to.
        </p>
      </Section>

      <Section title="Limits worth knowing">
        <ul className="list-disc space-y-2 pl-5">
          <li>It predicts an average brain from the scan data the model learned on, not your audience.</li>
          <li>Nobody is scanned. These are model predictions, not measurements.</li>
          <li>
            TRIBE v2 is licensed CC BY-NC 4.0, so PrePost is non-commercial research for now. See the{' '}
            <a href={`${REPO}/blob/main/NOTICE`} target="_blank" rel="noopener noreferrer" className="text-ink underline underline-offset-4">
              license notice
            </a>
            .
          </li>
        </ul>
      </Section>

      <Section title="Read the source documents">
        <div className="flex flex-wrap gap-2">
          <a href={PREREG_URL} target="_blank" rel="noopener noreferrer" className="btn-secondary btn-sm">
            Full pre-registration ↗
          </a>
          <a
            href={`${REPO}/blob/main/docs/VALIDATION-PROTOCOL-AND-ROADMAP.md`}
            target="_blank"
            rel="noopener noreferrer"
            className="btn-secondary btn-sm"
          >
            Validation protocol ↗
          </a>
          <a href="https://github.com/facebookresearch/tribev2" target="_blank" rel="noopener noreferrer" className="btn-secondary btn-sm">
            TRIBE v2 (Meta FAIR) ↗
          </a>
          <a href="https://arxiv.org/abs/2607.01400" target="_blank" rel="noopener noreferrer" className="btn-secondary btn-sm">
            arXiv:2607.01400 ↗
          </a>
        </div>
      </Section>

      <div className="mt-20 rounded-[24px] bg-panel p-8 text-center md:p-10">
        <h2 className="type-h2 text-ink">Want to hear the result first?</h2>
        <p className="type-lead mx-auto mt-3 max-w-lg">Waitlist members get the hook-test write-up the day it&apos;s published.</p>
        <Link href="/#waitlist" className="btn-primary btn-lg mt-6">
          Join the waitlist
        </Link>
      </div>
    </div>
  )
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="mt-16">
      <h2 className="text-[24px] leading-[32px] font-medium tracking-[-0.2px] text-ink">{title}</h2>
      <div className="mt-4 text-[16px] leading-[27px] text-ink/80">{children}</div>
    </section>
  )
}
