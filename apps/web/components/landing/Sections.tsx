import Link from 'next/link'
import { REGION_LABELS, type RegionKey } from '@/components/brain/contract'
import { DemoVideo } from '@/components/landing/Interactive'
import { WaitlistForm } from '@/components/landing/WaitlistForm'
import { clipNotes } from '@/lib/clip-notes'
import { CLIPS } from '@/lib/clips'

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
export const REGION_ORDER: RegionKey[] = ['attention', 'social', 'language', 'valuation', 'auditory', 'motion', 'narrative']

/** Literal class names, so Tailwind emits every region color (it drops theme vars no class uses). */
export const REGION_DOT: Record<RegionKey, string> = {
  attention: 'bg-roi-attention',
  social: 'bg-roi-social',
  language: 'bg-roi-language',
  valuation: 'bg-roi-valuation',
  auditory: 'bg-roi-auditory',
  motion: 'bg-roi-motion',
  narrative: 'bg-roi-narrative',
}

export function HowItWorks() {
  return (
    <section id="how-it-works" className="mx-auto max-w-[1232px] px-6 pt-20 md:pt-32">
      <div className="mx-auto max-w-2xl text-center">
        <h2 className="type-h2 text-ink">How it works, and why</h2>
        <p className="type-lead mt-4">
          For the curious: the four ideas behind the read. The full method is on{' '}
          <Link href="/science" className="text-ink underline-offset-4 hover:underline">
            the science page
          </Link>
          .
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
                <span className={`h-2 w-2 rounded-full ${REGION_DOT[key]}`} />
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

        <Card title="What it can’t tell you, yet">
          <p>
            It predicts an average brain, not your audience, and it doesn&apos;t predict views. Whether the read
            tracks real engagement is not proven: in our first 24-video pilot the link was weak and could have been
            chance (r = 0.25, p = 0.24). So we offer it as a diagnostic, not a forecast, and a larger pre-registered
            test is under way. We&apos;ll publish the answer either way.
          </p>
          <Link href="/science" className="btn-secondary btn-sm mt-5 self-start">
            How we&apos;re testing it
          </Link>
        </Card>
      </div>
    </section>
  )
}

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col rounded-[24px] bg-panel p-6 text-[15px] md:p-8 leading-[24px] text-ink/80">
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
    <section className="mx-auto max-w-[1232px] px-6 pt-20 md:pt-32">
      <h2 className="type-h2 text-center text-ink">See it in action</h2>
      <DemoVideo
        src="/demo/prepost-demo.mp4"
        poster="/demo/prepost-demo-poster.jpg"
        label="PrePost demo: a predicted brain response to a video, second by second"
      />
    </section>
  )
}

/* ---------- Part 11: the science ---------- */
export function Science() {
  return (
    <section id="science" className="mx-auto max-w-[1232px] px-6 pt-20 md:pt-32 text-center">
      <h2 className="type-h2 text-ink">The science, in the open</h2>
      <p className="type-lead mx-auto mt-4 max-w-2xl">
        We&apos;re running a pre-registered test: 72 short videos, each with one of four openings, run as ads with equal
        budgets. It checks whether the brain read predicts which openings keep people watching past three seconds. The
        plan was written before any data came in, and we&apos;ll publish the result whether it works or not.
      </p>
      <Link href="/science" className="btn-secondary btn-lg mt-8">
        Read the science
      </Link>
    </section>
  )
}

/* ---------- Part 5: who it's for, and what a read looks like ---------- */
const BENEFITS = [
  {
    title: 'Send notes with a timestamp',
    body: 'Swap “it feels slow” for “the predicted response sags at 0:04, tighten the open.” Creators know exactly what to fix.',
  },
  {
    title: 'The same read for every creator',
    body: 'Every draft on a campaign gets the same second-by-second read, so approvals rest on one standard instead of whoever reviewed it.',
  },
  {
    title: 'Plain English first, the science underneath',
    body: 'Each read opens with a short summary of where to look. The brain-area detail is there when you or the client want it.',
  },
]

export function ForReviewers() {
  const clip = CLIPS[0]
  const notes = clipNotes(clip.context).slice(0, 3)
  return (
    <section id="for-teams" className="mx-auto max-w-[1232px] px-6 pt-20 md:pt-32">
      <div className="mx-auto max-w-2xl text-center">
        <p className="font-mono text-[13px] text-accent">For agencies and brand creator teams</p>
        <h2 className="type-h2 mt-3 text-ink">Review creator drafts with a reason</h2>
        <p className="type-lead mt-4">
          If you approve or send back 20 or more creator videos a month, PrePost gives every draft a second-by-second
          read before it posts, so feedback points at a moment, not a feeling.
        </p>
      </div>

      <div className="mt-12 grid gap-4 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]">
        <ul className="grid gap-4">
          {BENEFITS.map(b => (
            <li key={b.title} className="rounded-[24px] bg-panel p-6 md:p-8">
              <h3 className="type-h3 text-ink">{b.title}</h3>
              <p className="mt-2 text-[15px] leading-[24px] text-ink/80">{b.body}</p>
            </li>
          ))}
        </ul>

        <div className="rounded-[24px] bg-panel p-6 md:p-8">
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <h3 className="type-h3 text-ink">What a read looks like</h3>
            <span className="rounded-full bg-accent-bg px-2.5 py-0.5 text-[12px] font-medium text-accent">
              Real TRIBE v2 output
            </span>
          </div>
          <p className="mt-1 text-[14px] leading-6 text-muted">{clip.title}, a 25-second sample creator clip.</p>
          <ol className="mt-5 space-y-3">
            {notes.map(n => (
              <li key={n.title} className="rounded-[16px] bg-elevated p-4">
                <p className="text-[15px] font-medium text-ink">{n.title}</p>
                <p className="mt-1 text-[14px] leading-[22px] text-ink/80">{n.body}</p>
              </li>
            ))}
          </ol>
          <Link href={`/clips/${clip.slug}`} className="btn-secondary btn-sm mt-5">
            Open the full read →
          </Link>
        </div>
      </div>
    </section>
  )
}

/* ---------- Part 13: final call to action, the waitlist ---------- */
export function FinalCta() {
  return (
    <section id="waitlist" className="relative mx-auto max-w-[1232px] overflow-hidden px-6 pt-24 pb-8 text-center md:pt-40">
      <h2 className="type-h2 text-ink">Join the waitlist</h2>
      <p className="type-lead mx-auto mt-3 max-w-xl">
        We&apos;re opening early access to a small group of agency and brand teams first. Tell us a little about your
        review workload and we&apos;ll be in touch.
      </p>
      <div className="mt-8">
        <WaitlistForm />
      </div>
      <p className="mx-auto mt-6 max-w-md text-[13px] leading-5 text-muted">
        PrePost is a research preview. TRIBE v2 is licensed CC BY-NC 4.0, so nothing is for sale yet.
      </p>
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src="/mascot/mascot-cheer.webp"
        alt=""
        aria-hidden
        loading="lazy"
        className="mx-auto mt-12 block w-[220px] md:w-[280px]"
      />
    </section>
  )
}
