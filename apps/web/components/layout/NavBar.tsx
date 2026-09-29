'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'

const PREREG_URL =
  'https://github.com/rippere/tribe-social/blob/main/research/PREREGISTRATION.md'

const NAV_LINKS = [
  { label: 'How it works', href: '/#how-it-works' },
  { label: 'The science', href: '/#science' },
  { label: 'Pricing', href: '/#pricing' },
  { label: 'FAQ', href: '/#faq' },
]

export default function NavBar() {
  const pathname = usePathname()

  return (
    <nav className="sticky top-0 z-50 bg-white/85 backdrop-blur-md">
      <div className="mx-auto flex h-16 max-w-[1232px] items-center justify-between px-6">
        <div className="flex items-center gap-10">
          <Link href="/" className="text-[19px] font-semibold tracking-[-0.3px] text-ink">
            fMRIght
          </Link>

          <div className="hidden items-center gap-7 md:flex">
            {NAV_LINKS.map(link => (
              <Link
                key={link.href}
                href={link.href}
                className="text-sm text-ink/70 transition-colors hover:text-ink"
              >
                {link.label}
              </Link>
            ))}
          </div>
        </div>

        <div className="flex items-center gap-2">
          <a
            href={PREREG_URL}
            target="_blank"
            rel="noopener noreferrer"
            className="btn-secondary btn-sm hidden sm:inline-flex"
          >
            Pre-registration
          </a>
          <Link
            href="/scorer"
            aria-current={pathname === '/scorer' ? 'page' : undefined}
            className="btn-primary btn-sm"
          >
            Score a clip
          </Link>
        </div>
      </div>
    </nav>
  )
}
