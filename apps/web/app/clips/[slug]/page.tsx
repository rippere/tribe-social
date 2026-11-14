import type { Metadata } from 'next'
import Link from 'next/link'
import { notFound } from 'next/navigation'
import ClipWorkspace from '@/components/clips/ClipWorkspace'
import { clipNotes } from '@/lib/clip-notes'
import { CLIPS, clock, getClip } from '@/lib/clips'

export const dynamicParams = false

export function generateStaticParams() {
  return CLIPS.map(c => ({ slug: c.slug }))
}

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }): Promise<Metadata> {
  const clip = getClip((await params).slug)
  return clip ? { title: `${clip.title} · PrePost`, description: clip.blurb } : {}
}

export default async function ClipPage({ params }: { params: Promise<{ slug: string }> }) {
  const clip = getClip((await params).slug)
  if (!clip) notFound()
  const peak = clip.context.whole_cortex.peak_second

  return (
    <div className="mx-auto max-w-[1232px] px-6 pt-8 md:pt-12">
      <Link href="/clips" className="text-[13px] text-muted transition-colors hover:text-ink">
        ← All clips
      </Link>
      <div className="mt-4 mb-6 flex flex-wrap items-end justify-between gap-x-8 gap-y-3">
        <div className="max-w-2xl">
          <h1 className="text-[32px] font-medium leading-[1.1] tracking-[-0.6px] text-ink md:text-[40px]">
            {clip.title}
          </h1>
          <p className="mt-3 text-[15px] leading-6 text-muted">{clip.blurb}</p>
        </div>
        <dl className="flex gap-6 font-mono text-[12px] text-muted">
          <div>
            <dt>Length</dt>
            <dd className="mt-0.5 text-[15px] text-ink">{clock(clip.context.seconds - 1)}</dd>
          </div>
          <div>
            <dt>Strongest overall</dt>
            <dd className="mt-0.5 text-[15px] text-ink">{clock(peak)}</dd>
          </div>
          <div>
            <dt>Model</dt>
            <dd className="mt-0.5 text-[15px] text-ink">TRIBE v2</dd>
          </div>
        </dl>
      </div>

      <section aria-labelledby="summary" className="mb-4 rounded-[22px] bg-panel p-5 md:p-6">
        <h2 id="summary" className="type-h3 text-ink">
          The read in plain English
        </h2>
        <ol className="mt-4 grid gap-3 md:grid-cols-2">
          {clipNotes(clip.context).map(n => (
            <li key={n.title} className="rounded-[16px] bg-elevated p-4">
              <p className="text-[15px] font-medium text-ink">{n.title}</p>
              <p className="mt-1 text-[14px] leading-[22px] text-ink/80">{n.body}</p>
            </li>
          ))}
        </ol>
        <p className="mt-3 text-[12px] leading-5 text-muted">
          Computed from the model&apos;s per-second prediction for an average viewer. A diagnostic, not a forecast of views.
        </p>
      </section>

      <ClipWorkspace clip={clip} />
    </div>
  )
}
