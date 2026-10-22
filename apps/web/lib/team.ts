/**
 * The team on /about. Seats follow the Team 2 Hub (Seats tab). Headshots go in
 * public/team/<slug>.{jpg,png,webp}; the page picks them up at build time and falls
 * back to initials until a photo is there.
 */
export type TeamMember = {
  slug: string
  name: string
  role: string
  bio: string
}

export const TEAM: TeamMember[] = [
  {
    slug: 'ryan-arnold',
    name: 'Ryan Arnold',
    role: 'Product Lead',
    bio: "Keeps the team pointed at what's next. Owns the roadmap, the deadlines and the weekly sync, so everyone knows who's doing what.",
  },
  {
    slug: 'lucas-blais',
    name: 'Lucas Blais',
    role: 'Design & Brand',
    bio: 'Owns how fMRIght looks and sounds, from the brand system and our presentations to the edit template every test clip is cut with.',
  },
  {
    slug: 'audrey-kreick',
    name: 'Audrey Kreick',
    role: 'Go-to-Market & User Research',
    bio: "Finds out who the customer is and what they'd pay, through customer interviews, the competitor audit and our pricing work.",
  },
  {
    slug: 'ben-rippere',
    name: 'Ben Rippere',
    role: 'Engineering & Scoring',
    bio: 'Builds and runs the product: the app, the scoring pipeline and the TRIBE v2 model behind every read. Named investigator on the hook test.',
  },
  {
    slug: 'cole-watterson',
    name: 'Cole Watterson',
    role: 'Research & Validation',
    bio: 'Runs the test that checks whether the read predicts anything: the shoot calendar, the 72-clip log and the guess round.',
  },
  {
    slug: 'julie-weninger',
    name: 'Julie Weninger',
    role: 'Operations & Compliance',
    bio: 'Makes sure nothing quietly sinks us: clip permissions, licensing questions, the ad account and the budget.',
  },
]

export function initials(name: string): string {
  return name
    .split(' ')
    .map(part => part[0])
    .join('')
}
