import { existsSync } from 'node:fs'
import { join } from 'node:path'
import type { Metadata } from 'next'
import Link from 'next/link'
import { MascotGlyph, PREREG_URL } from '@/components/landing/Sections'
import { initials, TEAM, type TeamMember } from '@/lib/team'

export const metadata: Metadata = {
  title: 'About us · fMRIght',
  description:
    'fMRIght is a six-person student startup building a brain read for short-form video. Our mission, what we believe and the team behind it.',
}

const VALUES = [
  {
    title: 'Honest',
    body: 'We state the evidence, including the nulls. Every read is labeled a prediction, because that is what it is.',
  },
  {
    title: 'Curious',
    body: 'Every clip is a question worth asking: which second holds a viewer, and why?',
  },
  {
    title: 'Plain-spoken',
    body: 'Neuroscience in the words a creator uses on set. If a term needs a gloss, it gets one.',
  },
  {
    title: 'Rigorous',
    body: 'Pre-registered tests, published methods and real model output only. No made-up demo numbers.',
  },
]

const PHOTO_EXTENSIONS = ['jpg', 'jpeg', 'png', 'webp']

/** The headshot's public path, if one has been dropped into public/team/. Read at build time. */
function photoFor(slug: string): string | undefined {
  const ext = PHOTO_EXTENSIONS.find(e => existsSync(join(process.cwd(), 'public', 'team', `${slug}.${e}`)))
  return ext ? `/team/${slug}.${ext}` : undefined
}

export default function AboutPage() {
  return (
    <>
      <section className="mx-auto max-w-[1232px] px-6 pt-12 md:pt-20">
        <div className="max-w-3xl">
          <h1 className="type-h1 text-ink">
            About <MascotGlyph className="mx-1 h-[0.9em] w-[0.9em] -translate-y-[0.06em]" /> fMRIght
          </h1>
          <p className="type-lead mt-6 max-w-2xl">
            fMRIght predicts how an average viewer&apos;s brain responds to a short video, second by second, and explains
            it in plain English. It runs Meta&apos;s TRIBE v2 brain-encoding model on the video file alone, so a creator or
            the person approving their draft can see what lands before it posts.
          </p>
          <p className="type-lead mt-4 max-w-2xl">
            We&apos;re a six-person team that started in WSU&apos;s ENTRP 490 in fall 2026. Our name joins fMRI, the brain
            scan, with getting the video right.
          </p>
        </div>
      </section>

      <section className="mx-auto max-w-[1232px] px-6 pt-24">
        <div className="rounded-[24px] bg-panel p-8 md:p-12">
          <p className="font-mono text-[13px] text-accent">Our mission</p>
          <p className="mt-4 max-w-3xl text-[28px] leading-[36px] font-medium tracking-[-0.3px] text-ink md:text-[36px] md:leading-[44px]">
            Turn &ldquo;post and pray&rdquo; into &ldquo;look before you leap,&rdquo; and never claim more than we can show.
          </p>
          <p className="mt-6 max-w-2xl text-[16px] leading-[26px] text-ink/70">
            Short videos are won or lost in seconds, and feedback on a draft is usually gut feel. We give creators and
            reviewers a second-by-second read they can point at. We also publish our own evidence, including a weak
            first pilot (r = 0.25, p = 0.24, 24 videos), and we call fMRIght a diagnostic until a{' '}
            <a href={PREREG_URL} target="_blank" rel="noopener noreferrer" className="text-ink underline underline-offset-4">
              pre-registered test
            </a>{' '}
            shows it predicts more.
          </p>
        </div>

        <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {VALUES.map(v => (
            <div key={v.title} className="rounded-[24px] bg-panel p-8">
              <h2 className="type-h3 text-ink">{v.title}</h2>
              <p className="mt-2 text-[15px] leading-[24px] text-ink/70">{v.body}</p>
            </div>
          ))}
        </div>
      </section>

      <section id="team" className="mx-auto max-w-[1232px] px-6 pt-32">
        <div className="mx-auto max-w-2xl text-center">
          <h2 className="type-h2 text-ink">The team</h2>
          <p className="type-lead mt-4">The six people building fMRIght.</p>
        </div>

        <ul className="mt-12 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {TEAM.map(member => (
            <TeamCard key={member.slug} member={member} photo={photoFor(member.slug)} />
          ))}
        </ul>
      </section>

      <section className="mx-auto max-w-[1232px] px-6 pt-32 text-center">
        <h2 className="type-h2 text-ink">See what we&apos;re building</h2>
        <div className="mt-8 flex flex-wrap justify-center gap-2">
          <Link href="/product" className="btn-primary btn-lg">
            Explore the app
          </Link>
          <Link href="/scorer" className="btn-secondary btn-lg">
            Score a clip
          </Link>
        </div>
      </section>
    </>
  )
}

function TeamCard({ member, photo }: { member: TeamMember; photo?: string }) {
  return (
    <li className="flex flex-col rounded-[24px] bg-panel p-3">
      {photo ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={photo}
          alt={member.name}
          loading="lazy"
          className="aspect-square w-full rounded-[18px] bg-elevated object-cover"
        />
      ) : (
        <div
          aria-hidden
          className="flex aspect-square w-full items-center justify-center rounded-[18px] bg-elevated font-mono text-[44px] text-muted"
        >
          {initials(member.name)}
        </div>
      )}
      <div className="px-5 pt-5 pb-6">
        <h3 className="text-[18px] leading-6 font-medium text-ink">{member.name}</h3>
        <p className="mt-3 text-[15px] leading-[24px] text-ink/70">{member.bio}</p>
      </div>
    </li>
  )
}
