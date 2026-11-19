import type { Metadata } from 'next'
import { NOINDEX } from '@/lib/site'

// Dev page: needs the local scoring API or is a work-in-progress view. Kept out of
// search (also disallowed in robots.txt) and out of the sitemap.
export const metadata: Metadata = { title: 'Cortex view · PrePost', ...NOINDEX }

export default function Layout({ children }: { children: React.ReactNode }) {
  return children
}
