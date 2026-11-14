import type { Metadata } from 'next'
import Link from 'next/link'
import { REGION_LABELS } from '@/components/brain/contract'
import { PREREG_URL, REGION_DOT, REGION_ORDER } from '@/components/landing/Sections'
import { AppStoreBadge } from '@/components/product/AppStoreBadge'
import { PhoneMockup } from '@/components/product/PhoneMockup'
import { CLIPS } from '@/lib/clips'

export const metadata: Metadata = {
  title: 'The app · fMRIght',
  description:
    'Check a short video on your phone before you post it. fMRIght shows, second by second, where an average viewer’s brain is predicted to lock in or drift off.',
}

const FEATURES: { title: string; body: string; extra?: 'regions' }[] = [
  {
    title: 'Second by second',
    body: 'A timeline of the predicted response for every second of your clip, so you can point at the exact moment that slips.',
  },
  {
    title: 'Seven brain areas',
    body: 'See whether a moment works because of the visuals, the voice, the people on screen or the story.',
    extra: 'regions',
  },
  {
    title: 'Revision tips in plain English',
    body: 'Each read comes with notes on what to change and where, written the way you would say it on set.',
  },
  {
    title: 'Ask about any clip',
    body: 'Chat with the read. Ask what happens in the first three seconds and get an answer grounded in the model’s numbers.',
  },
  {
    title: 'From the file alone',
    body: 'No test panel, no eye-tracker, no scanner. Upload the video and the model does the rest in a few minutes.',
  },
  {
    title: 'Honest by design',
    body: 'Every read is labeled a prediction for an average viewer, and our own pilot result is published, weak as it was.',
  },
]

const AUDIENCES = [
  {
    label: 'For creators',
    title: 'Check a draft before you send it',
    body: 'Find the second that loses a viewer while you can still fix it, then send a cut you can stand behind.',
    points: ['Built for one person on a phone', 'A read on the whole clip, not just the first three seconds', 'Plain-English notes you can act on'],
  },
  {
    label: 'For agencies and brands',
    title: 'Review drafts with a reason',
    body: 'Approve a draft or send it back with something specific: “attention dips at 0:04, tighten the open.”',
    points: ['Reads you can drop into the review and the client deck', 'The same read for every creator on the campaign', 'Works in the browser at your desk'],
  },
]

const STEPS = [
  { n: '01', title: 'Add a draft', body: 'Upload a short video from your camera roll or your desktop.' },
  { n: '02', title: 'Get the read', body: 'In a few minutes, see the predicted response second by second across seven brain areas.' },
  { n: '03', title: 'Fix the second that slips', body: 'Use the tips and the chat to tighten the cut before it posts.' },
]

export default function ProductPage() {
  return (
    <>
      <section className="mx-auto grid max-w-[1232px] items-center gap-12 px-6 pt-12 md:pt-20 lg:grid-cols-[minmax(0,7fr)_minmax(0,5fr)]">
        <div className="text-center lg:text-left">
          <span className="inline-flex rounded-full bg-accent-bg px-3 py-1 text-[13px] font-medium text-accent">
            The fMRIght app
          </span>
          <h1 className="type-h1 mt-6 text-ink">A brain scan, without the scanner.</h1>
          <p className="type-lead mx-auto mt-5 max-w-xl lg:mx-0">
            Check a short video before you post it. fMRIght predicts which second an average viewer&apos;s brain locks in
            and which second it drifts off, and tells you why in plain English.
          </p>
          <div className="mt-8 flex flex-wrap items-center justify-center gap-3 lg:justify-start">
            <AppStoreBadge />
            <Link href="/scorer" className="btn-primary btn-lg">
              Try it free on the web
            </Link>
          </div>
          <p className="mt-4 text-[13px] text-muted">
            The iPhone app is in development. Every feature on this page works in your browser today.
          </p>
        </div>

        <PhoneMockup />
      </section>

      <section id="features" className="mx-auto max-w-[1232px] px-6 pt-32">
        <div className="mx-auto max-w-2xl text-center">
          <h2 className="type-h2 text-ink">What you get in every read</h2>
          <p className="type-lead mt-4">Specific seconds, named brain areas and a note on what to change.</p>
        </div>

        <ul className="mt-12 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map(f => (
            <li key={f.title} className="flex flex-col rounded-[24px] bg-panel p-8 text-[15px] leading-[24px] text-ink/70">
              <h3 className="type-h3 mb-2 text-ink">{f.title}</h3>
              <p>{f.body}</p>
              {f.extra === 'regions' && (
                <div className="mt-5 flex flex-wrap gap-2">
                  {REGION_ORDER.map(key => (
                    <span key={key} className="inline-flex items-center gap-2 rounded-full bg-elevated px-3 py-1.5 text-[13px] text-ink">
                      <span className={`h-2 w-2 rounded-full ${REGION_DOT[key]}`} />
                      {REGION_LABELS[key]}
                    </span>
                  ))}
                </div>
              )}
            </li>
          ))}
        </ul>
      </section>

      <section className="mx-auto max-w-[1232px] px-6 pt-32">
        <h2 className="type-h2 text-center text-ink">Built for both sides of the draft</h2>
        <div className="mt-12 grid gap-4 md:grid-cols-2">
          {AUDIENCES.map(a => (
            <div key={a.label} className="rounded-[24px] bg-panel p-8 md:p-10">
              <p className="font-mono text-[13px] text-accent">{a.label}</p>
              <h3 className="mt-3 text-[24px] leading-[32px] font-medium tracking-[-0.2px] text-ink">{a.title}</h3>
              <p className="mt-3 text-[16px] leading-[26px] text-ink/70">{a.body}</p>
              <ul className="mt-6 space-y-3">
                {a.points.map(p => (
                  <li key={p} className="flex gap-3 text-[15px] leading-[24px] text-ink/80">
                    <span aria-hidden className="mt-[9px] h-1.5 w-1.5 shrink-0 rounded-full bg-accent" />
                    {p}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </section>

      <section className="mx-auto max-w-[1232px] px-6 pt-32">
        <h2 className="type-h2 text-center text-ink">How it works</h2>
        <ol className="mt-12 grid gap-4 md:grid-cols-3">
          {STEPS.map(s => (
            <li key={s.n} className="rounded-[24px] bg-panel p-8">
              <span className="font-mono text-[13px] text-muted">{s.n}</span>
              <h3 className="type-h3 mt-3 text-ink">{s.title}</h3>
              <p className="mt-2 text-[15px] leading-[24px] text-ink/70">{s.body}</p>
            </li>
          ))}
        </ol>
        <p className="mx-auto mt-8 max-w-2xl text-center text-[13px] leading-5 text-muted">
          fMRIght predicts an average brain, not your audience, and it doesn&apos;t predict views. Our first pilot found a
          weak link to engagement that didn&apos;t hold up (r = 0.25, p = 0.24, 24 videos). A{' '}
          <a href={PREREG_URL} target="_blank" rel="noopener noreferrer" className="text-ink underline-offset-4 hover:underline">
            pre-registered test
          </a>{' '}
          is running now.
        </p>
      </section>

      <section className="mx-auto max-w-[1232px] px-6 pt-40 pb-8 text-center">
        <h2 className="type-h2 text-ink">See what lands before you post</h2>
        <p className="type-lead mt-3">Free while fMRIght is a research preview.</p>
        <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
          <AppStoreBadge />
          <Link href="/scorer" className="btn-primary btn-lg">
            Score a clip
          </Link>
          <Link href={`/clips/${CLIPS[0].slug}`} className="btn-secondary btn-lg">
            See a sample read
          </Link>
        </div>
      </section>
    </>
  )
}
