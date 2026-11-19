import type { Metadata } from 'next'
import { NOINDEX } from '@/lib/site'

// Invite-only research trial. Private links (invite code / result token in the URL
// fragment), so kept out of search, robots.txt and the sitemap. public/_headers adds
// X-Robots-Tag: noindex and Referrer-Policy: no-referrer for /trial*.
export const metadata: Metadata = { title: 'Research trial · PrePost', ...NOINDEX, referrer: 'no-referrer' }

export default function Layout({ children }: { children: React.ReactNode }) {
  return children
}
