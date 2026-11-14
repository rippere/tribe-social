import Link from 'next/link'
import { REGION_LABELS, type RegionKey } from '@/components/brain/contract'

export const REPO = 'https://github.com/rippere/tribe-social'
export const PREREG_URL = `${REPO}/blob/main/research/PREREGISTRATION.md`

/** The brain mascot's face in an ink disc, for inline use in headlines. */
export function MascotGlyph({ className = '' }: { className?: string }) {
  return (
    <span
      aria-hidden
      className={`inline-flex items-center justify-center overflow-hidden rounded-full bg-ink align-middle ${className}`}
    >
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src="/mascot/mascot-face.png" alt="" className="h-[86%] w-[86%] translate-y-[4%] object-contain" />
    </span>
  )
}

/* ---------- Part 6: How it works (the non-obvious parts) ---------- */
const REGION_ORDER: RegionKey[] = ['attention', 'social', 'language', 'valuation', 'auditory', 'motion', 'narrative']

export function HowItWorks() {
  return (
    <section id="how-it-works" className="mx-auto max-w-[1232px] px-6 pt-32">
      <div className="mx-auto max-w-2xl text-center">
        <h2 className="type-h2 text-ink">How it works, and why</h2>
        <p className="type-lead mt-4">
          The demo shows what happens. These are the parts that aren&apos;t obvious at first glance.
        </p>
      </div>

      <div className="mt-12 grid gap-4 md:grid-cols-2">
        <Card title="Why a model can stand in for a scanner">
          <p>
            TRIBE v2 was trained on brain scans of people watching and listening to media. It learned which patterns on
            screen and in the audio go with which brain responses. Give it a new video and it predicts the response an
            average viewer&apos;s brain would likely have.
          </p>
          <MiniFlow />
        </Card>

        <Card title="Why seven brain areas instead of one score">
          <p>
            A single number hides the reason. Splitting the read into areas tells you whether a moment works because of
            the visuals, the voice, the people on screen or the story.
          </p>
          <div className="mt-5 flex flex-wrap gap-2">
            {REGION_ORDER.map(key => (
              <span key={key} className="inline-flex items-center gap-2 rounded-full bg-elevated px-3 py-1.5 text-[13px] text-ink">
                <span className="h-2 w-2 rounded-full" style={{ background: `var(--color-roi-${key})` }} />
                {REGION_LABELS[key]}
              </span>
            ))}
          </div>
        </Card>

        <Card title="Why second by second matters">
          <p>
            Short videos are won or lost in moments. The timeline shows where attention is predicted to rise and where
            it&apos;s predicted to fall, so you know which cut, line or shot to change instead of reshooting everything.
          </p>
          <MiniBars />
        </Card>

        <Card title="What it can’t tell you">
          <p>
            It predicts an average brain, not your audience, and it doesn&apos;t predict views. Our first pilot found a
            weak link to engagement that didn&apos;t hold up statistically (r = 0.25, p = 0.24, 24 videos). We&apos;re
            testing it properly now and will publish the answer either way.
          </p>
          <Link href="#science" className="btn-secondary btn-sm mt-5 self-start">
            How we&apos;re testing it
          </Link>
        </Card>
      </div>
    </section>
  )
}

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col rounded-[24px] bg-panel p-8 text-[15px] leading-[24px] text-ink/70">
      <h3 className="type-h3 mb-2 text-ink">{title}</h3>
      {children}
    </div>
  )
}

function MiniFlow() {
  const steps = ['Frames, audio, words', 'TRIBE v2', 'Predicted response']
  return (
    <div className="mt-5 flex flex-wrap items-center gap-2 text-[13px]">
      {steps.map((s, i) => (
        <span key={s} className="flex items-center gap-2">
          <span className={`rounded-full px-3 py-1.5 ${i === 1 ? 'bg-ink text-on-ink' : 'bg-elevated text-ink'}`}>{s}</span>
          {i < steps.length - 1 && <span aria-hidden className="text-muted">→</span>}
        </span>
      ))}
    </div>
  )
}

function MiniBars() {
  const bars = [42, 61, 78, 74, 66, 58, 49, 44, 47, 55, 63, 71, 69, 60, 52]
  return (
    <div aria-hidden className="mt-5 flex h-16 items-end gap-1">
      {bars.map((h, i) => (
        <span key={i} className={`flex-1 rounded-t ${i < 3 ? 'bg-ink' : 'bg-ink/20'}`} style={{ height: `${h}%` }} />
      ))}
    </div>
  )
}

/* ---------- Part 8: demo video ---------- */
export function SeeItInAction() {
  return (
    <section className="mx-auto max-w-[1232px] px-6 pt-32">
      <h2 className="type-h2 text-center text-ink">See it in action</h2>
      <video
        className="mt-10 aspect-video w-full rounded-[24px] bg-ink-2 object-cover"
        src="/demo/fmright-demo.mp4"
        poster="/demo/fmright-demo-poster.jpg"
        controls
        playsInline
        preload="metadata"
        aria-label="fMRIght demo: a predicted brain response to a video, second by second"
      />
    </section>
  )
}

/* ---------- Part 11: the science ---------- */
export function Science() {
  return (
    <section id="science" className="mx-auto max-w-[1232px] px-6 pt-32 text-center">
      <h2 className="type-h2 text-ink">The science, in the open</h2>
      <p className="type-lead mx-auto mt-4 max-w-2xl">
        We&apos;re running a pre-registered test: 72 short videos, each with one of four openings, run as ads with equal
        budgets. It checks whether the brain read predicts which openings keep people watching past three seconds. The
        plan was written before any data came in, and we&apos;ll publish the result whether it works or not.
      </p>
      <a href={PREREG_URL} target="_blank" rel="noopener noreferrer" className="btn-secondary btn-lg mt-8">
        Read the pre-registration
      </a>
    </section>
  )
}

/* ---------- Part 13: final call to action ---------- */
export function FinalCta() {
  return (
    <section className="relative mx-auto max-w-[1232px] overflow-hidden px-6 pt-40 pb-8 text-center">
      <h2 className="type-h2 text-ink">Score your first clip</h2>
      <p className="type-lead mt-3">Drop in a short video and see the read in a few minutes. Free while it&apos;s a research preview.</p>
      <div className="mt-8 flex justify-center gap-2">
        <Link href="/scorer" className="btn-primary btn-lg">
          Score a clip
        </Link>
        <Link href="/clips" className="btn-secondary btn-lg">
          Browse scored clips
        </Link>
      </div>
      <p className="mx-auto mt-6 max-w-md text-[13px] leading-5 text-muted">
        Review creator content for a living?{' '}
        <a href={`${REPO}/issues`} target="_blank" rel="noopener noreferrer" className="text-ink underline-offset-4 hover:underline">
          Tell us what a read like this is worth to you
        </a>
        . fMRIght is non-commercial research: TRIBE v2 is licensed CC BY-NC 4.0.
      </p>
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src="/mascot/mascot-cheer.webp"
        alt=""
        aria-hidden
        loading="lazy"
        className="mx-auto mt-12 block w-[260px] md:w-[320px]"
      />
    </section>
  )
}
