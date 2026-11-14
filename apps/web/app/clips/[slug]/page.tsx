import type { Metadata } from 'next'
import Link from 'next/link'
import { notFound } from 'next/navigation'
import ClipWorkspace from '@/components/clips/ClipWorkspace'
import { CLIPS, clock, getClip } from '@/lib/clips'

export const dynamicParams = false

export function generateStaticParams() {
  return CLIPS.map(c => ({ slug: c.slug }))
}

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }): Promise<Metadata> {
  const clip = getClip((await params).slug)
  return clip ? { title: `${clip.title} · fMRIght`, description: clip.blurb } : {}
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

      <ClipWorkspace clip={clip} />
    </div>
  )
}
