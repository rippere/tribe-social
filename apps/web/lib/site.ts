import type { Metadata } from 'next'

/**
 * Public site identity, shared by page metadata, robots.txt, sitemap.xml, llms.txt and
 * the JSON-LD block. Set NEXT_PUBLIC_SITE_URL at build time once a custom domain is live;
 * every canonical URL, sitemap entry and social card follows it.
 */
export const SITE_URL = (process.env.NEXT_PUBLIC_SITE_URL ?? 'https://prepost-clw.pages.dev').replace(/\/$/, '')
export const SITE_NAME = 'PrePost'
export const SITE_TAGLINE = 'See what a video does to a brain'
export const SITE_DESCRIPTION =
  "PrePost runs Meta's TRIBE v2 brain-encoding model on a short video and shows, second by second, the predicted brain response. A research diagnostic, not a view forecast."
export const REPO_URL = 'https://github.com/rippere/tribe-social'

/** Indexable pages, in sitemap order. Clip pages are added from lib/clips.ts. */
export const PUBLIC_PAGES: { path: string; title: string; summary: string; priority: number }[] = [
  { path: '/', title: 'Home', summary: 'What PrePost does, who it is for, a sample read and the waitlist.', priority: 1 },
  { path: '/product', title: 'The app', summary: 'The phone app: check a short video before you post it.', priority: 0.8 },
  { path: '/clips', title: 'Scored clips', summary: 'Example videos with their predicted brain response, second by second.', priority: 0.8 },
  { path: '/science', title: 'The science', summary: 'The model, the evidence so far (r = 0.25, p = 0.24, n = 24) and the pre-registered test.', priority: 0.7 },
  { path: '/about', title: 'About us', summary: 'The six-person team building PrePost and what we believe.', priority: 0.6 },
]

/** Pages that only work against the local scoring API. Kept out of search. */
export const PRIVATE_PATHS = ['/scorer', '/dashboard', '/cortex']

/**
 * Full metadata for one page: title, description, canonical URL, Open Graph and Twitter
 * card. Next replaces (not merges) openGraph from the layout, so every page sets its own.
 * Without `image`, pages use the card from app/opengraph-image.tsx. It has to be named
 * explicitly: a page-level openGraph drops the file-based image.
 */
export function pageMeta({
  title,
  description,
  path,
  image,
}: {
  title: string
  description: string
  path: string
  image?: string
}): Metadata {
  const images = [image ? { url: image } : { url: '/opengraph-image', width: 1200, height: 630, alt: `${SITE_NAME}: ${SITE_TAGLINE}` }]
  return {
    title,
    description,
    alternates: { canonical: path },
    openGraph: { type: 'website', siteName: SITE_NAME, title, description, url: path, locale: 'en_US', images },
    twitter: { card: 'summary_large_image', title, description, images },
  }
}

export const NOINDEX: Metadata = { robots: { index: false, follow: false } }
