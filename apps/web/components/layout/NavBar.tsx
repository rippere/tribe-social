'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'

const NAV_LINKS = [
  { label: 'For teams', href: '/#for-teams' },
  { label: 'The app', href: '/product' },
  { label: 'Clips', href: '/clips' },
  { label: 'The science', href: '/science' },
  { label: 'About', href: '/about' },
]

export default function NavBar() {
  const pathname = usePathname()

  return (
    <nav className="sticky top-0 z-50 bg-background/85 backdrop-blur-md">
      <div className="mx-auto flex h-16 max-w-[1232px] items-center justify-between px-6">
        <div className="flex items-center gap-10">
          <Link href="/" className="text-[19px] font-semibold tracking-[-0.3px] text-ink">
            PrePost
          </Link>

          <div className="hidden items-center gap-7 md:flex">
            {NAV_LINKS.map(link => (
              <Link
                key={link.href}
                href={link.href}
                aria-current={pathname === link.href ? 'page' : undefined}
                className="text-sm text-ink/80 transition-colors hover:text-ink aria-[current=page]:text-ink"
              >
                {link.label}
              </Link>
            ))}
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Link href="/product" className="flex h-10 items-center px-2 text-sm text-ink/80 transition-colors hover:text-ink md:hidden">
            App
          </Link>
          <Link href="/about" className="flex h-10 items-center px-2 text-sm text-ink/80 transition-colors hover:text-ink md:hidden">
            About
          </Link>
          <Link href="/#waitlist" className="btn-primary btn-sm">
            Join the waitlist
          </Link>
        </div>
      </div>
    </nav>
  )
}
