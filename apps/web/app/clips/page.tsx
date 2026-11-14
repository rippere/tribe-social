import type { Metadata } from 'next'
import Link from 'next/link'
import { CLIPS, clock } from '@/lib/clips'

export const metadata: Metadata = {
  title: 'Scored clips · fMRIght',
  description: 'Short videos with their real TRIBE v2 predicted brain response, second by second. Open one to scrub it and ask about it.',
}

export default function ClipsPage() {
  return (
    <div className="mx-auto max-w-[1232px] px-6 pt-12 md:pt-20">
      <div className="max-w-2xl">
        <h1 className="type-h2 text-ink">Scored clips</h1>
        <p className="type-lead mt-4">
          Each clip here has its real TRIBE v2 prediction: the response the model expects from an average viewer,
          second by second. Open one to play it against the cortex and ask what the numbers say.
        </p>
      </div>

      <ul className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {CLIPS.map(c => (
          <li key={c.slug}>
            <Link
              href={`/clips/${c.slug}`}
              className="group flex h-full cursor-pointer gap-4 rounded-[22px] bg-elevated p-3 shadow-[var(--shadow-hairline)] transition-colors hover:bg-ink-2"
            >
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={c.poster}
                alt=""
                loading="lazy"
                className="aspect-[9/16] w-[38%] shrink-0 rounded-[14px] bg-ink-2 object-cover"
              />
              <div className="flex min-w-0 flex-col py-1 pr-1">
                <span className="w-fit rounded-full bg-accent-bg px-2 py-0.5 text-[11px] font-medium text-accent">
                  Real TRIBE v2 prediction
                </span>
                <h2 className="mt-3 text-[18px] font-medium leading-6 text-ink">{c.title}</h2>
                <p className="mt-2 text-[13px] leading-5 text-muted">{c.blurb}</p>
                <p className="mt-auto pt-4 font-mono text-[12px] text-muted">
                  {clock(c.context.seconds - 1)} · strongest at {clock(c.context.whole_cortex.peak_second)}
                </p>
                <span className="mt-3 text-[14px] text-ink transition-colors group-hover:text-accent">
                  Open and ask →
                </span>
              </div>
            </Link>
          </li>
        ))}
        <li>
          <Link
            href="/scorer"
            className="flex h-full min-h-[240px] cursor-pointer flex-col justify-center rounded-[22px] border border-dashed border-line p-6 transition-colors hover:bg-fill"
          >
            <h2 className="text-[18px] font-medium text-ink">Score your own</h2>
            <p className="mt-2 text-[13px] leading-5 text-muted">
              Upload a short clip and get the same read. Your video isn&apos;t kept, and it isn&apos;t added here.
            </p>
            <span className="mt-4 text-[14px] text-ink">Score a clip →</span>
          </Link>
        </li>
      </ul>

      <p className="mt-8 max-w-2xl text-[13px] leading-5 text-muted">
        Only clips we made or have permission to show appear here. Predictions are for an average viewer, not a
        measurement of anyone, and they haven&apos;t been validated against views or retention.
      </p>
    </div>
  )
}
