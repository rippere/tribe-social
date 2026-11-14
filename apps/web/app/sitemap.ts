import type { MetadataRoute } from 'next'
import { CLIPS } from '@/lib/clips'
import { PUBLIC_PAGES, SITE_URL } from '@/lib/site'

export const dynamic = 'force-static'

export default function sitemap(): MetadataRoute.Sitemap {
  return [
    ...PUBLIC_PAGES.map((p) => ({ url: `${SITE_URL}${p.path === '/' ? '' : p.path}`, changeFrequency: 'weekly' as const, priority: p.priority })),
    ...CLIPS.map((c) => ({ url: `${SITE_URL}/clips/${c.slug}`, changeFrequency: 'monthly' as const, priority: 0.6 })),
  ]
}
