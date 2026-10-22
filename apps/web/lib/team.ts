/**
 * The team on /about. Headshots go in
 * public/team/<slug>.{jpg,png,webp}; the page picks them up at build time and falls
 * back to initials until a photo is there.
 */
export type TeamMember = {
  slug: string
  name: string
}

export const TEAM: TeamMember[] = [
  {
    slug: 'ryan-arnold',
    name: 'Ryan Arnold',
  },
  {
    slug: 'lucas-blais',
    name: 'Lucas Blais',
  },
  {
    slug: 'audrey-kreick',
    name: 'Audrey Kreick',
  },
  {
    slug: 'ben-rippere',
    name: 'Ben Rippere',
  },
  {
    slug: 'cole-watterson',
    name: 'Cole Watterson',
  },
  {
    slug: 'julie-weninger',
    name: 'Julie Weninger',
  },
]

export function initials(name: string): string {
  return name
    .split(' ')
    .map(part => part[0])
    .join('')
}
