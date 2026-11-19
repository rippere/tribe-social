// Claims banner and licence/attribution footer shared by the trial pages.

import { CLAIM } from '@/lib/trial/claim'

export function ClaimBanner() {
  return (
    <div role="note" className="rounded-2xl border border-[#D97706]/40 bg-[#D97706]/10 px-4 py-3 text-[13px] leading-5 text-[#FBBF24]">
      {CLAIM}. A read of the video, not a forecast of views or engagement.
    </div>
  )
}

export function TrialFooter() {
  return (
    <p className="mt-8 text-center text-[12px] leading-5 text-muted">
      Free research trial, not a paid service. Predictions come from{' '}
      <a href="https://github.com/facebookresearch/tribev2" className="underline underline-offset-2 hover:text-ink">
        TRIBE v2
      </a>{' '}
      by Meta FAIR, used under{' '}
      <a href="https://creativecommons.org/licenses/by-nc/4.0/" className="underline underline-offset-2 hover:text-ink">
        CC BY-NC 4.0
      </a>{' '}
      for non-commercial research.
    </p>
  )
}
