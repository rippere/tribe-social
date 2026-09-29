import Link from 'next/link'

const REPO = 'https://github.com/rippere/tribe-social'

const COLUMNS = [
  {
    title: 'Product',
    links: [
      { label: 'Score a clip', href: '/scorer' },
      { label: 'How it works', href: '/#how-it-works' },
      { label: 'Pricing', href: '/#pricing' },
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
      { label: 'GitHub', href: REPO },
      { label: 'License notice', href: `${REPO}/blob/main/NOTICE` },
    ],
  },
]

export default function Footer() {
  return (
    <footer className="mt-24 border-t border-line bg-background">
      <div className="mx-auto grid max-w-[1232px] gap-10 px-6 py-16 md:grid-cols-[1fr_auto_auto_auto] md:gap-20">
        <div>
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
            <ul className="mt-3 space-y-2">
              {col.links.map(link => (
                <li key={link.label}>
                  {link.href.startsWith('http') ? (
                    <a
                      href={link.href}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-[13px] text-muted transition-colors hover:text-ink"
                    >
                      {link.label}
                    </a>
                  ) : (
                    <Link href={link.href} className="text-[13px] text-muted transition-colors hover:text-ink">
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
