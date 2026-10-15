'use client'

import { Fragment, useEffect, useRef, useState } from 'react'
import type { Clip } from '@/lib/clips'

type Turn = { role: 'user' | 'assistant'; content: string }

// "11 s", "11s", "11 sec", "second 11", "0:11"
const TIME_RE = /\b(?:(\d):(\d{2})|seconds? (\d{1,2})|(\d{1,2})(?:\.\d+)? ?(?:s|sec|secs|seconds?)\b)/g

/** Turns second references in an answer into buttons that jump the video there. */
function Linked({ text, max, onSeek }: { text: string; max: number; onSeek?: (s: number) => void }) {
  if (!onSeek) return <>{text}</>
  const out: React.ReactNode[] = []
  let at = 0
  for (const m of text.matchAll(TIME_RE)) {
    const s = m[1] ? Number(m[1]) * 60 + Number(m[2]) : Number(m[3] ?? m[4])
    if (!(s >= 0 && s < max)) continue
    out.push(<Fragment key={`t${at}`}>{text.slice(at, m.index)}</Fragment>)
    out.push(
      <button
        key={`b${m.index}`}
        type="button"
        onClick={() => onSeek(s)}
        className="cursor-pointer rounded-[6px] bg-accent-bg px-1 text-accent underline-offset-2 hover:underline"
        title={`Jump the video to ${s} s`}
      >
        {m[0]}
      </button>,
    )
    at = m.index + m[0].length
  }
  out.push(<Fragment key="end">{text.slice(at)}</Fragment>)
  return <>{out}</>
}

// Chat about one scored clip. Answers come from TRIBE v2's real per-second
// prediction for that clip (app/api/clip-chat/route.ts).
export default function ClipChat({
  clip,
  onSeek,
  className = '',
}: {
  clip: Clip
  onSeek?: (s: number) => void
  className?: string
}) {
  const [turns, setTurns] = useState<Turn[]>([])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const listRef = useRef<HTMLDivElement>(null)
  const abortRef = useRef<AbortController | null>(null)

  useEffect(() => {
    const el = listRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [turns])

  useEffect(() => () => abortRef.current?.abort(), [])

  async function ask(question: string) {
    const q = question.trim()
    if (!q || busy) return
    const history: Turn[] = [...turns, { role: 'user', content: q }]
    setTurns([...history, { role: 'assistant', content: '' }])
    setInput('')
    setError(null)
    setBusy(true)

    const ctrl = new AbortController()
    abortRef.current = ctrl
    try {
      const res = await fetch('/api/clip-chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ clip: clip.slug, messages: history.slice(-12) }),
        signal: ctrl.signal,
      })
      if (!res.ok || !res.body) {
        const err = await res.json().catch(() => ({}))
        throw new Error(err.error ?? `Request failed (${res.status})`)
      }
      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let answer = ''
      for (;;) {
        const { done, value } = await reader.read()
        if (done) break
        // The panel renders plain text; drop any markdown emphasis the model slips in.
        answer += decoder.decode(value, { stream: true }).replace(/[`*]/g, '')
        setTurns([...history, { role: 'assistant', content: answer }])
      }
      if (!answer.trim()) throw new Error('The model returned an empty answer. Try again.')
    } catch (e) {
      if (ctrl.signal.aborted) return
      setTurns(history.slice(0, -1))
      setInput(q)
      setError(e instanceof Error ? e.message : 'Something went wrong.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <section
      aria-label="Ask about this clip"
      className={`flex min-h-[480px] flex-col overflow-hidden rounded-[22px] bg-elevated text-left shadow-[var(--shadow-window),var(--shadow-hairline)] ${className}`}
    >
      <div className="flex h-12 shrink-0 items-center gap-2 border-b border-line px-4">
        <span className="truncate text-[14px] font-medium text-ink">Ask about this clip</span>
        <span className="ml-auto shrink-0 whitespace-nowrap rounded-full bg-accent-bg px-2 py-0.5 text-[11px] font-medium text-accent">
          Real TRIBE v2 prediction
        </span>
      </div>

      <div ref={listRef} className="min-h-0 flex-1 space-y-4 overflow-y-auto px-4 py-5" aria-live="polite">
        {turns.length === 0 && (
          <p className="text-[14px] leading-relaxed text-muted">
            Ask which second the model predicts the strongest response, what the hook does, or where it goes flat.
            Answers come from this clip&apos;s per-second prediction, and any second they mention jumps the video
            there.
          </p>
        )}
        {turns.map((t, i) => (
          <div key={i} className={t.role === 'user' ? 'flex justify-end' : 'flex justify-start'}>
            <div
              className={
                t.role === 'user'
                  ? 'max-w-[88%] rounded-[16px] bg-ink px-3.5 py-2 text-[14px] text-on-ink'
                  : 'max-w-[92%] whitespace-pre-wrap rounded-[16px] bg-fill px-3.5 py-2 text-[14px] leading-relaxed text-ink'
              }
            >
              {t.role === 'assistant' && t.content ? (
                <Linked
                  text={t.content}
                  max={clip.context.seconds}
                  onSeek={busy && i === turns.length - 1 ? undefined : onSeek}
                />
              ) : (
                t.content || <span className="text-muted">Reading the prediction…</span>
              )}
            </div>
          </div>
        ))}
        {error && (
          <p role="alert" className="text-[13px] text-[#FF8A80]">
            {error}
          </p>
        )}
      </div>

      <div className="shrink-0 border-t border-line px-4 py-3">
        {turns.length === 0 && (
          <div className="mb-3 flex flex-wrap gap-2">
            {clip.suggestions.map(s => (
              <button
                key={s}
                type="button"
                onClick={() => ask(s)}
                disabled={busy}
                className="cursor-pointer rounded-full bg-btn-2 px-3 py-1.5 text-left text-[13px] text-ink transition-colors hover:bg-fill disabled:opacity-50"
              >
                {s}
              </button>
            ))}
          </div>
        )}
        <form
          onSubmit={e => {
            e.preventDefault()
            ask(input)
          }}
          className="flex gap-2"
        >
          <input
            value={input}
            onChange={e => setInput(e.target.value)}
            maxLength={800}
            placeholder="Ask about a second, a region, or the hook…"
            aria-label="Your question about this clip"
            className="min-h-11 min-w-0 flex-1 rounded-full bg-fill px-4 py-2 text-[16px] text-ink outline-none placeholder:text-muted focus:shadow-[var(--shadow-hairline)] md:text-[14px]"
          />
          <button
            type="submit"
            disabled={busy || !input.trim()}
            className="btn-primary btn-sm min-h-11 disabled:opacity-50"
          >
            {busy ? '…' : 'Ask'}
          </button>
        </form>
        <p className="mt-2 text-[11px] leading-4 text-muted">
          Predicted cortical response of an average viewer, not a measurement. Not validated against engagement.
        </p>
      </div>
    </section>
  )
}
