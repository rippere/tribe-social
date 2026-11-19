'use client'

import { Menu, X } from 'lucide-react'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { useEffect, useState } from 'react'

const NAV_LINKS = [
  { label: 'For teams', href: '/#for-teams' },
  { label: 'The app', href: '/product' },
  { label: 'Clips', href: '/clips' },
  { label: 'The science', href: '/science' },
  { label: 'About', href: '/about' },
]

export default function NavBar() {
  const pathname = usePathname()
  const [open, setOpen] = useState(false)

  // Close the mobile menu after navigating, and on Escape.
  useEffect(() => setOpen(false), [pathname])
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(false)
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [open])

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
          <Link href="/#waitlist" onClick={() => setOpen(false)} className="btn-primary btn-sm">
            Join the waitlist
          </Link>
          <button
            type="button"
            onClick={() => setOpen(o => !o)}
            aria-expanded={open}
            aria-controls="mobile-nav"
            aria-label={open ? 'Close menu' : 'Open menu'}
            className="flex h-10 w-10 items-center justify-center rounded-full text-ink transition-colors hover:bg-fill md:hidden"
          >
            {open ? <X aria-hidden className="h-5 w-5" /> : <Menu aria-hidden className="h-5 w-5" />}
          </button>
        </div>
      </div>

      {open && (
        <div id="mobile-nav" className="border-t border-line bg-background md:hidden">
          <ul className="mx-auto max-w-[1232px] px-6 py-2">
            {NAV_LINKS.map(link => (
              <li key={link.href}>
                <Link
                  href={link.href}
                  onClick={() => setOpen(false)}
                  aria-current={pathname === link.href ? 'page' : undefined}
                  className="flex h-12 items-center text-[17px] text-ink/80 transition-colors hover:text-ink aria-[current=page]:text-ink"
                >
                  {link.label}
                </Link>
              </li>
            ))}
          </ul>
        </div>
      )}
    </nav>
  )
}
