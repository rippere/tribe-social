import { CLIPS } from '@/lib/clips'
import { PUBLIC_PAGES, REPO_URL, SITE_DESCRIPTION, SITE_NAME, SITE_URL } from '@/lib/site'

export const dynamic = 'force-static'

// llms.txt (https://llmstxt.org): a plain-text map of the site for AI assistants and
// crawlers. The evidence line stays as plain as the science page; see the repo's
// public-repo contract before softening it.
export function GET() {
  const url = (path: string) => `${SITE_URL}${path === '/' ? '' : path}`
  const body = [
    `# ${SITE_NAME}`,
    '',
    `> ${SITE_DESCRIPTION}`,
    '',
    `${SITE_NAME} is a research preview from a six-person student team. It is aimed at agency and brand teams who review creator video drafts. It predicts how an average viewer's brain responds to a short video, second by second, using Meta FAIR's TRIBE v2 model. It does not scan anyone and does not forecast views.`,
    '',
    'Evidence so far: a 24-video pilot found r = 0.25, p = 0.24 between the brain read and engagement, which is not significant. A pre-registered test will decide whether the read adds anything. TRIBE v2 is licensed CC BY-NC 4.0, so nothing is for sale.',
    '',
    '## Pages',
    '',
    ...PUBLIC_PAGES.map((p) => `- [${p.title}](${url(p.path)}): ${p.summary}`),
    '',
    '## Scored clips',
    '',
    ...CLIPS.map((c) => `- [${c.title}](${url(`/clips/${c.slug}`)}): ${c.blurb}`),
    '',
    '## Optional',
    '',
    `- [Source code](${REPO_URL}): Apache-2.0; TRIBE v2 itself is CC BY-NC 4.0`,
    `- [Pre-registration](${REPO_URL}/blob/main/research/PREREGISTRATION.md)`,
    `- [Validation protocol](${REPO_URL}/blob/main/docs/VALIDATION-PROTOCOL-AND-ROADMAP.md)`,
    '',
  ].join('\n')
  return new Response(body, { headers: { 'Content-Type': 'text/plain; charset=utf-8' } })
}
