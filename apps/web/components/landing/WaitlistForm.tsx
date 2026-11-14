'use client'

import { useState } from 'react'
import { ROLES, VOLUMES } from '@/lib/waitlist'

type Status =
  | { kind: 'idle' }
  | { kind: 'sending' }
  | { kind: 'done' }
  | { kind: 'error'; message: string; field?: 'email' | 'role' }

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

const field =
  'h-11 w-full rounded-[12px] bg-elevated px-3.5 text-[15px] text-ink shadow-[var(--shadow-hairline)] placeholder:text-muted focus:outline-none focus-visible:ring-2 focus-visible:ring-accent'

export function WaitlistForm() {
  const [status, setStatus] = useState<Status>({ kind: 'idle' })

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    const data = Object.fromEntries(new FormData(e.currentTarget)) as Record<string, string>
    // Our own checks (the form is noValidate), so the error shows in the page in our
    // words, not as a browser tooltip that screen readers and screenshots miss.
    const email = (data.email ?? '').trim()
    if (!EMAIL_RE.test(email)) {
      setStatus({ kind: 'error', field: 'email', message: email ? 'That email address doesn’t look right.' : 'Add your work email.' })
      e.currentTarget.querySelector<HTMLInputElement>('input[name=email]')?.focus()
      return
    }
    if (!data.role) {
      setStatus({ kind: 'error', field: 'role', message: 'Choose what you do.' })
      e.currentTarget.querySelector<HTMLSelectElement>('select[name=role]')?.focus()
      return
    }
    setStatus({ kind: 'sending' })
    try {
      const res = await fetch('/api/waitlist', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify(data),
      })
      const out = (await res.json().catch(() => ({}))) as { error?: string }
      if (!res.ok) throw new Error(out.error ?? 'Something went wrong. Try again in a minute.')
      setStatus({ kind: 'done' })
    } catch (err) {
      setStatus({ kind: 'error', message: err instanceof Error ? err.message : 'Something went wrong.' })
    }
  }

  const fieldError = status.kind === 'error' ? status.field : undefined

  if (status.kind === 'done') {
    return (
      <div role="status" className="mx-auto max-w-md rounded-[24px] bg-panel p-8 text-center">
        <p className="type-h3 text-ink">You&apos;re on the list.</p>
        <p className="mt-2 text-[15px] leading-6 text-ink/80">
          We&apos;ll reach out when early access opens, starting with teams that review creator drafts every week.
        </p>
      </div>
    )
  }

  return (
    <form onSubmit={onSubmit} noValidate className="mx-auto grid max-w-xl gap-3 text-left sm:grid-cols-2">
      <label className="sm:col-span-2">
        <span className="mb-1.5 block text-[13px] text-ink/80">Work email</span>
        <input
          name="email"
          type="email"
          required
          autoComplete="email"
          placeholder="you@agency.com"
          aria-invalid={fieldError === 'email' || undefined}
          aria-describedby={fieldError === 'email' ? 'waitlist-error' : undefined}
          onChange={() => fieldError === 'email' && setStatus({ kind: 'idle' })}
          className={field}
        />
      </label>
      <label>
        <span className="mb-1.5 block text-[13px] text-ink/80">What do you do?</span>
        <select
          name="role"
          required
          defaultValue=""
          aria-invalid={fieldError === 'role' || undefined}
          aria-describedby={fieldError === 'role' ? 'waitlist-error' : undefined}
          onChange={() => fieldError === 'role' && setStatus({ kind: 'idle' })}
          className={field}
        >
          <option value="" disabled>
            Choose one
          </option>
          {ROLES.map(r => (
            <option key={r}>{r}</option>
          ))}
        </select>
      </label>
      <label>
        <span className="mb-1.5 block text-[13px] text-ink/80">Creator videos you review a month</span>
        <select name="volume" defaultValue="" className={field}>
          <option value="">Prefer not to say</option>
          {VOLUMES.map(v => (
            <option key={v}>{v}</option>
          ))}
        </select>
      </label>
      <label className="sm:col-span-2">
        <span className="mb-1.5 block text-[13px] text-ink/80">Company (optional)</span>
        <input name="company" autoComplete="organization" className={field} />
      </label>
      {/* Honeypot, hidden from people and screen readers. */}
      <input name="website" tabIndex={-1} autoComplete="off" aria-hidden className="hidden" />
      <div className="mt-2 flex flex-col items-center gap-3 sm:col-span-2">
        <button type="submit" disabled={status.kind === 'sending'} className="btn-primary btn-lg disabled:opacity-60">
          {status.kind === 'sending' ? 'Joining…' : 'Join the waitlist'}
        </button>
        {status.kind === 'error' && (
          <p id="waitlist-error" role="alert" className="text-[14px] text-roi-valuation">
            {status.message}
          </p>
        )}
      </div>
    </form>
  )
}
