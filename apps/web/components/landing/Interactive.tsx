'use client'

import { useState } from 'react'

/* ---------- Part 7: use cases (chip picker + phone mock) ---------- */
const USE_CASES = [
  {
    key: 'agency',
    label: 'Agency review',
    lead: 'Check a draft before it reaches the client.',
    body: 'See where a creator’s hook lands and where attention is predicted to drift, and send notes on specific seconds instead of a gut call.',
    tip: 'Attention is predicted to drop at 0:07 during the talking stretch. Try cutting to the product sooner.',
  },
  {
    key: 'hooks',
    label: 'Creator hooks',
    lead: 'Compare openings on the same video.',
    body: 'Film one body and a few different first three seconds, then compare how each opening is predicted to land.',
    tip: 'The motion opening is predicted to hold attention best through 0:03.',
  },
  {
    key: 'paid',
    label: 'Paid social',
    lead: 'Screen ad versions before you spend.',
    body: 'Use the read as one input next to your own judgment when deciding which versions are worth testing with real budget.',
    tip: 'Version B’s opening is predicted to land stronger; version C drifts early.',
  },
  {
    key: 'brand',
    label: 'Brand check',
    lead: 'See what’s carrying a video.',
    body: 'Find out whether a piece works because of the visuals, the voice or the music before it represents your brand.',
    tip: 'Sound is doing most of the work here; the visuals are quieter than you might think.',
  },
]

export function UseCases() {
  const [active, setActive] = useState(USE_CASES[0].key)
  const uc = USE_CASES.find(u => u.key === active) ?? USE_CASES[0]

  return (
    <section className="mx-auto grid max-w-[1232px] items-center gap-12 px-6 pt-32 md:grid-cols-2">
      <div className="md:pl-12">
        <h2 className="type-h2 text-ink">Built for every draft</h2>
        <div className="mt-6 flex max-w-md flex-wrap gap-2" role="tablist" aria-label="Use cases">
          {USE_CASES.map(u => (
            <button
              key={u.key}
              type="button"
              role="tab"
              aria-selected={u.key === active}
              onClick={() => setActive(u.key)}
              className={`rounded-full px-3.5 py-1.5 text-[14px] font-medium transition-colors ${
                u.key === active
                  ? 'bg-accent-bg text-accent shadow-[inset_0_0_0_1px_rgba(74,216,236,0.28)]'
                  : 'text-ink shadow-[var(--shadow-hairline)] hover:bg-fill'
              }`}
            >
              {u.label}
            </button>
          ))}
        </div>
        <p className="mt-8 max-w-md text-[16px] leading-6 text-ink">
          <span className="font-medium">{uc.lead}</span> <span className="text-muted">{uc.body}</span>
        </p>
      </div>

      {/* Phone mock */}
      <div className="mx-auto w-[280px] rounded-[44px] border-[10px] border-[#2A2A29] bg-elevated p-4 shadow-[var(--shadow-window)]">
        <div className="mx-auto mb-4 h-5 w-24 rounded-full bg-black" />
        <p className="text-center text-[12px] font-medium text-ink">fMRIght</p>
        <div className="mt-4 rounded-2xl bg-fill p-3">
          <p className="text-[11px] text-muted">Predicted attention</p>
          <div aria-hidden className="mt-2 flex h-14 items-end gap-[3px]">
            {[42, 61, 78, 74, 66, 58, 49, 44, 47, 55, 63, 71, 69, 60].map((h, i) => (
              <span key={i} className="flex-1 rounded-t bg-ink/70" style={{ height: `${h}%` }} />
            ))}
          </div>
        </div>
        <div key={uc.key} className="mt-3 rounded-2xl bg-ink-2 p-3 text-[12px] leading-[18px] text-ink animate-in fade-in duration-300">
          {uc.tip}
        </div>
        <p className="mt-3 text-center text-[10px] text-muted">Sample read</p>
      </div>
    </section>
  )
}

/* ---------- Part 12: FAQ ---------- */
const FAQS = [
  {
    q: 'What is fMRI?',
    a: 'A brain scan that tracks blood flow to show which parts of the brain are working. fMRIght doesn’t scan anyone. It uses a model that learned from fMRI scans.',
  },
  {
    q: 'Does this predict views or virality?',
    a: 'No. It predicts how an average brain responds to a video. Whether that relates to views is exactly what our current study is testing.',
  },
  {
    q: 'How accurate is it?',
    a: 'For this use, we don’t know yet. Our pilot found a weak relationship that wasn’t statistically significant (r = 0.25, p = 0.24, 24 videos). The pre-registered hook test will give a clearer answer.',
  },
  {
    q: 'Whose brain is it predicting?',
    a: 'An average of the people in the scan data the model learned from, not your audience specifically.',
  },
  {
    q: 'What happens to my video?',
    a: 'It’s sent to a rented cloud GPU to be scored, and fMRIght doesn’t keep the video file. The resulting scores are saved to our research dataset. Only upload videos you have the rights to.',
  },
  {
    q: 'Can I use it for commercial work?',
    a: 'Not yet. TRIBE v2 is licensed for non-commercial use only, so fMRIght is a research preview.',
  },
]

export function Faq() {
  const [open, setOpen] = useState<number | null>(0)

  return (
    <section id="faq" className="mx-auto grid max-w-[976px] gap-10 px-6 pt-32 md:grid-cols-[1fr_1.4fr]">
      <h2 className="type-h2 text-ink">FAQs</h2>
      <div>
        {FAQS.map((f, i) => {
          const isOpen = open === i
          return (
            <div key={f.q} className="border-b border-line">
              <button
                type="button"
                aria-expanded={isOpen}
                onClick={() => setOpen(isOpen ? null : i)}
                className="flex w-full items-center justify-between gap-6 py-4 text-left text-[16px] text-ink"
              >
                {f.q}
                <span aria-hidden className="text-[20px] leading-none text-muted">{isOpen ? '×' : '+'}</span>
              </button>
              {isOpen && <p className="pb-5 text-[15px] leading-6 text-ink/70">{f.a}</p>}
            </div>
          )
        })}
      </div>
    </section>
  )
}
