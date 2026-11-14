import Link from 'next/link'

const REPO = 'https://github.com/rippere/tribe-social'

const COLUMNS = [
  {
    title: 'Product',
    links: [
      { label: 'The app', href: '/product' },
      { label: 'Score a clip', href: '/scorer' },
      { label: 'Scored clips', href: '/clips' },
      { label: 'How it works', href: '/#how-it-works' },
      { label: 'FAQ', href: '/#faq' },
    ],
  },
  {
    title: 'Science',
    links: [
      { label: 'Pre-registration', href: `${REPO}/blob/main/research/PREREGISTRATION.md` },
      { label: 'Validation protocol', href: `${REPO}/blob/main/docs/VALIDATION-PROTOCOL-AND-ROADMAP.md` },
      { label: 'TRIBE v2 (Meta FAIR)', href: 'https://github.com/facebookresearch/tribev2' },
    ],
  },
  {
    title: 'Project',
    links: [
      { label: 'About us', href: '/about' },
      { label: 'The team', href: '/about#team' },
      { label: 'GitHub', href: REPO },
      { label: 'License notice', href: `${REPO}/blob/main/NOTICE` },
    ],
  },
]

export default function Footer() {
  return (
    <footer className="mt-24 border-t border-line bg-background">
      <div className="mx-auto grid max-w-[1232px] grid-cols-2 gap-x-6 gap-y-10 px-6 py-12 md:grid-cols-[1fr_auto_auto_auto] md:gap-20 md:py-16">
        <div className="col-span-2 md:col-span-1">
          <p className="text-[17px] font-semibold tracking-[-0.3px] text-ink">fMRIght</p>
          <p className="mt-2 max-w-xs text-[13px] leading-5 text-muted">
            Non-commercial research: TRIBE v2 is licensed CC BY-NC 4.0.
          </p>
          <p className="mt-4 max-w-xs text-[12px] leading-5 text-muted/80">
            © 2026 Ben Rippere. Developed with WSU ENTRP 490 Team 2 as a course project.
          </p>
        </div>

        {COLUMNS.map(col => (
          <div key={col.title}>
            <p className="text-[13px] font-medium text-ink">{col.title}</p>
            <ul className="mt-2 space-y-1">
              {col.links.map(link => (
                <li key={link.label}>
                  {link.href.startsWith('http') ? (
                    <a
                      href={link.href}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-block py-1 text-[13px] text-muted transition-colors hover:text-ink"
                    >
                      {link.label}
                    </a>
                  ) : (
                    <Link href={link.href} className="inline-block py-1 text-[13px] text-muted transition-colors hover:text-ink">
                      {link.label}
                    </Link>
                  )}
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </footer>
  )
}
