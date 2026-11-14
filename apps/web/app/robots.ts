import type { MetadataRoute } from 'next'
import { PRIVATE_PATHS, SITE_URL } from '@/lib/site'

export const dynamic = 'force-static'

// Everything public is crawlable, AI crawlers included (llms.txt points them at the
// right pages). Dev-only pages that need the local scoring API and the JSON endpoints
// stay out.
export default function robots(): MetadataRoute.Robots {
  return {
    rules: [{ userAgent: '*', allow: '/', disallow: [...PRIVATE_PATHS, '/api/'] }],
    sitemap: `${SITE_URL}/sitemap.xml`,
    host: SITE_URL,
  }
}
