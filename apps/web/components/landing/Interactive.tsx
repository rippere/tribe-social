'use client'

import { useState } from 'react'

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
