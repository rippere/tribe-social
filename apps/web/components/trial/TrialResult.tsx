'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import ResultsCard from '@/components/scorer/ResultsCard'
import type { ScoreResult } from '@/lib/types'
import TrialCortex from './TrialCortex'
import { ClaimBanner, TrialFooter } from './TrialNotice'

interface Queue {
  position: number
  eta_s: number
  basis: { exec_ms: number; cold_ms: number; samples: number }
}

interface StatusBody {
  status: 'uploading' | 'queued' | 'submitted' | 'running' | 'complete' | 'failed'
  label: string
  created_at: number
  duration_s: number | null
  queue?: Queue
  error?: string
  expires_at?: number
  timings?: { delay_ms: number | null; execution_ms: number | null; cold_start: boolean }
  result?: {
    score: ScoreResult
    n_seconds: number
    activity: { frames: number; vertices: number; hz: number } | null
  } | null
}

type View = { kind: 'loading' } | { kind: 'notfound' } | { kind: 'deleted' } | { kind: 'error'; message: string } | { kind: 'ok'; body: StatusBody }

const fmtEta = (s: number) => (s < 90 ? 'about a minute' : s < 3600 ? `about ${Math.round(s / 60)} minutes` : `about ${(s / 3600).toFixed(1)} hours`)

const pollMs = (elapsed: number) => (elapsed < 5 * 60_000 ? 5000 : 15000)

export default function TrialResult() {
  const [token, setToken] = useState<string | null>(null)
  const [view, setView] = useState<View>({ kind: 'loading' })
  const [confirming, setConfirming] = useState(false)
  const [copied, setCopied] = useState(false)
  const started = useRef(Date.now())

  const load = useCallback(async (tok: string): Promise<StatusBody | null> => {
    const r = await fetch('/api/trial/result', { headers: { authorization: `Bearer ${tok}` }, cache: 'no-store' })
    if (r.status === 404) {
      setView({ kind: 'notfound' })
      return null
    }
    if (!r.ok) throw new Error(`The result service answered ${r.status}.`)
    const body = (await r.json()) as StatusBody
    setView({ kind: 'ok', body })
    return body
  }, [])

  // A different link pasted into the same tab only changes the fragment: start over.
  useEffect(() => {
    const onHash = () => window.location.reload()
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
  }, [])

  useEffect(() => {
    const tok = window.location.hash.slice(1)
    if (!/^[A-Za-z0-9_-]{43}$/.test(tok)) {
      setView({ kind: 'notfound' })
      return
    }
    setToken(tok)
    let timer: ReturnType<typeof setTimeout> | undefined
    let alive = true
    const step = async () => {
      try {
        const body = await load(tok)
        if (!alive || !body || body.status === 'complete' || body.status === 'failed') return
      } catch (e) {
        if (alive) setView({ kind: 'error', message: e instanceof Error ? e.message : 'Could not load the result.' })
      }
      if (alive) timer = setTimeout(step, pollMs(Date.now() - started.current))
    }
    step()
    return () => {
      alive = false
      if (timer) clearTimeout(timer)
    }
  }, [load])

  const remove = async () => {
    if (!token) return
    const r = await fetch('/api/trial/result', { method: 'DELETE', headers: { authorization: `Bearer ${token}` } })
    if (r.ok || r.status === 404) {
      setView({ kind: 'deleted' })
      history.replaceState(null, '', '/trial/result')
    } else setView({ kind: 'error', message: `Delete failed (${r.status}). Try again.` })
  }

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(window.location.href)
      setCopied(true)
    } catch {
      /* clipboard blocked: the URL bar still has it */
    }
  }

  const body = view.kind === 'ok' ? view.body : null
  const active = body && body.status !== 'complete' && body.status !== 'failed'

  return (
    <div className="mx-auto max-w-[976px] px-4 pt-12 pb-16 md:px-6 md:pt-16">
      <p className="mb-3 text-[13px] font-medium text-muted">Free research trial · private result</p>
      <h1 className="type-h2 text-ink">Your clip</h1>

      <div className="mt-6">
        <ClaimBanner />
      </div>

      {view.kind === 'loading' && <p className="mt-8 text-[14px] text-muted">Loading…</p>}
      {view.kind === 'notfound' && (
        <div className="mt-8 rounded-2xl bg-fill p-8 text-center" data-testid="trial-notfound">
          <p className="text-[16px] font-medium text-ink">Result not found</p>
          <p className="mt-2 text-[14px] text-muted">
            This link is wrong, the result was deleted, or its 30 days are up.
          </p>
        </div>
      )}
      {view.kind === 'deleted' && (
        <div className="mt-8 rounded-2xl bg-fill p-8 text-center">
          <p className="text-[16px] font-medium text-ink">Deleted</p>
          <p className="mt-2 text-[14px] text-muted">The result and anything left of the upload are gone.</p>
        </div>
      )}
      {view.kind === 'error' && <p className="mt-8 text-[14px] text-[#F87171]">{view.message}</p>}

      {body && (
        <>
          {active && (
            <div className="mt-6 rounded-[22px] bg-elevated p-6 shadow-[var(--shadow-window),var(--shadow-hairline)]" data-testid="trial-progress">
              <p className="text-[12px] font-medium uppercase tracking-wide text-muted">{body.label}</p>
              {body.queue && (
                <>
                  <p className="mt-2 text-[20px] font-medium text-ink">
                    {body.status === 'running' ? 'Scoring now' : `Number ${body.queue.position} in line`}
                  </p>
                  <p className="mt-1 text-[14px] text-muted">
                    Ready in {fmtEta(body.queue.eta_s)} (estimate from{' '}
                    {body.queue.basis.samples > 0 ? `the last ${body.queue.basis.samples} scored clips` : 'test runs'}; the
                    GPU starts from cold when it has been idle, which adds about {Math.round(body.queue.basis.cold_ms / 60000)} minutes).
                  </p>
                </>
              )}
              <p className="mt-4 text-[14px] leading-6 text-ink/80">
                You can close this page. We will email you when the result is ready, and this link keeps working for 30
                days. Save it: it is the only way back to the result.
              </p>
              <button type="button" onClick={copy} className="btn-secondary btn-sm mt-4">
                {copied ? 'Link copied' : 'Copy result link'}
              </button>
            </div>
          )}

          {body.status === 'failed' && (
            <div className="mt-6 rounded-2xl bg-[#F87171]/10 p-8 text-center">
              <p className="font-medium text-[#F87171]">Could not score this clip</p>
              <p className="mt-2 text-[14px] text-muted">{body.error}</p>
            </div>
          )}

          {body.status === 'complete' && body.result && (
            <div className="mt-6 space-y-4" data-testid="trial-complete">
              <div className="rounded-2xl border border-line p-5">
                <h3 className="mb-1 text-[13px] font-medium text-ink">Predicted cortical response</h3>
                <p className="mb-4 text-[12px] text-muted">
                  TRIBE v2&apos;s prediction for this clip, {body.result.n_seconds} frames at one per second. Brighter means
                  a stronger predicted response.
                </p>
                {body.result.activity && token ? (
                  <TrialCortex token={token} frames={body.result.activity.frames} label="Your clip" />
                ) : (
                  <p className="text-[13px] text-muted">No cortex view was saved for this clip.</p>
                )}
              </div>
              <ResultsCard result={body.result.score} temporalSource="model" />
              {body.timings?.execution_ms != null && (
                <p className="text-center text-[12px] text-muted">
                  Scored in {Math.round(body.timings.execution_ms / 1000)} s on the GPU
                  {body.timings.delay_ms != null ? ` after ${Math.round(body.timings.delay_ms / 1000)} s in the queue` : ''}.
                  {body.expires_at ? ` Kept until ${new Date(body.expires_at).toISOString().slice(0, 10)}.` : ''}
                </p>
              )}
            </div>
          )}

          <div className="mt-8 flex flex-col items-center gap-3">
            {confirming ? (
              <div className="flex items-center gap-3">
                <span className="text-[14px] text-ink">Delete this result for good?</span>
                <button type="button" onClick={remove} className="btn-primary btn-sm">
                  Yes, delete
                </button>
                <button type="button" onClick={() => setConfirming(false)} className="btn-secondary btn-sm">
                  Cancel
                </button>
              </div>
            ) : (
              <button type="button" onClick={() => setConfirming(true)} className="btn-secondary btn-sm">
                Delete my result
              </button>
            )}
          </div>
        </>
      )}

      <TrialFooter />
    </div>
  )
}
