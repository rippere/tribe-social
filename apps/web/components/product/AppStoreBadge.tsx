import { Smartphone } from 'lucide-react'

/**
 * The iPhone app isn't in the App Store yet. Set this to the listing (or a TestFlight
 * invite) when it is: the badge then becomes a "Download on the App Store" link. Swap in
 * Apple's official badge artwork at that point; Apple only allows it for live apps.
 */
export const APP_STORE_URL: string | null = null

export function AppStoreBadge() {
  const inner = (
    <>
      <Smartphone aria-hidden className="h-6 w-6 shrink-0" strokeWidth={1.75} />
      <span className="flex flex-col items-start leading-none">
        <span className="text-[11px] font-normal opacity-80">{APP_STORE_URL ? 'Download on the' : 'Coming soon to the'}</span>
        <span className="mt-1 text-[18px] font-semibold tracking-[-0.2px]">App Store</span>
      </span>
    </>
  )
  const className = 'inline-flex h-[52px] items-center gap-3 rounded-[14px] px-5'

  return APP_STORE_URL ? (
    <a
      href={APP_STORE_URL}
      target="_blank"
      rel="noopener noreferrer"
      className={`${className} bg-ink text-on-ink transition-opacity hover:opacity-85`}
    >
      {inner}
    </a>
  ) : (
    <span
      aria-label="iPhone app coming soon to the App Store"
      className={`${className} cursor-default text-ink shadow-[var(--shadow-hairline)]`}
    >
      {inner}
    </span>
  )
}
