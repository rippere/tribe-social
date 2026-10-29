/**
 * The team on /about. Headshots go in
 * public/team/<slug>.{jpg,png,webp}; the page picks them up at build time and falls
 * back to initials until a photo is there.
 */
export type TeamMember = {
  slug: string
  name: string
  role?: string
  bio?: string
}

export const TEAM: TeamMember[] = [
  {
    slug: 'ryan-arnold',
    name: 'Ryan Arnold',
    role: 'Outreach',
    bio: 'Ryan leads our outreach to creative strategists at brands and agencies, the people we want as early users. Ryan has run CRM-driven outreach campaigns before.',
  },
  {
    slug: 'lucas-blais',
    name: 'Lucas Blais',
    role: 'Edit lead',
    bio: "Lucas runs the edit for our study clips and checks every shooter's first take before the rest get filmed. Lucas also makes real-estate social content, so the creator's side of the problem is familiar.",
  },
  {
    slug: 'audrey-kreick',
    name: 'Audrey Kreick',
    role: 'Agency partnerships',
    bio: 'Audrey connects fMRIght with the people who approve creator content at brands and agencies. Audrey has interned in social media and business development at a marketing agency.',
  },
  {
    slug: 'ben-rippere',
    name: 'Ben Rippere',
    role: 'Founder and research lead',
    bio: 'Ben started fMRIght and leads the team. Ben runs the scoring pipeline, the pre-registered study and the write-up.',
  },
  {
    slug: 'cole-watterson',
    name: 'Cole Watterson',
    role: 'Creator partnerships',
    bio: 'Cole leads our outreach to student creators, with a focus on college athletes who do brand deals. Cole spent four years in college sports.',
  },
  {
    slug: 'julie-weninger',
    name: 'Julie Weninger',
    role: 'UI and mobile app',
    bio: 'Julie works on how fMRIght looks and feels, from the interface to the mobile app. The goal is a brain read a creator can take in at a glance.',
  },
]

export function initials(name: string): string {
  return name
    .split(' ')
    .map(part => part[0])
    .join('')
}
