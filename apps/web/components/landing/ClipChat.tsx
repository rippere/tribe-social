'use client'

import { useEffect, useRef, useState } from 'react'

type Turn = { role: 'user' | 'assistant'; content: string }

const SUGGESTIONS = [
  'What happens in the first 3 seconds?',
  'Where is the predicted response strongest?',
  'Does the flat instructions shot lose anything?',
  "What can't this model tell me?",
]

// Chat about the sample clip playing in the hero. Answers come from TRIBE v2's real
// per-second prediction for that clip (app/api/clip-chat/route.ts).
export default function ClipChat() {
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
        body: JSON.stringify({ messages: history.slice(-12) }),
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
    <div className="mx-auto w-full max-w-[976px] overflow-hidden rounded-[22px] bg-elevated text-left shadow-[var(--shadow-window),var(--shadow-hairline)]">
      <div className="flex h-11 items-center gap-2 border-b border-line px-4">
        <span className="truncate text-[13px] text-ink">Ask about this clip</span>
        <span className="shrink-0 whitespace-nowrap rounded-full bg-accent-bg px-2 py-0.5 text-[11px] font-medium text-accent">
          Real TRIBE v2 prediction
        </span>
      </div>

      <div ref={listRef} className="max-h-[420px] min-h-[180px] space-y-4 overflow-y-auto px-4 py-5 md:px-6" aria-live="polite">
        {turns.length === 0 && (
          <p className="text-[14px] leading-relaxed text-muted">
            Ask anything about the clip playing above: which second the model predicts the strongest response, what
            the hook does, where it goes flat. Answers come from TRIBE v2&apos;s per-second prediction for this clip,
            not from a guess.
          </p>
        )}
        {turns.map((t, i) => (
          <div key={i} className={t.role === 'user' ? 'flex justify-end' : 'flex justify-start'}>
            <div
              className={
                t.role === 'user'
                  ? 'max-w-[85%] rounded-[16px] bg-ink px-3.5 py-2 text-[14px] text-on-ink'
                  : 'max-w-[85%] whitespace-pre-wrap rounded-[16px] bg-fill px-3.5 py-2 text-[14px] leading-relaxed text-ink'
              }
            >
              {t.content || <span className="text-muted">Reading the prediction…</span>}
            </div>
          </div>
        ))}
        {error && <p className="text-[13px] text-[#FF8A80]">{error}</p>}
      </div>

      <div className="border-t border-line px-4 py-3 md:px-6">
        {turns.length === 0 && (
          <div className="mb-3 flex flex-wrap gap-2">
            {SUGGESTIONS.map(s => (
              <button
                key={s}
                type="button"
                onClick={() => ask(s)}
                disabled={busy}
                className="rounded-full bg-btn-2 px-3 py-1.5 text-[13px] text-ink transition-colors hover:bg-fill disabled:opacity-50"
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
            aria-label="Ask about this clip"
            className="min-w-0 flex-1 rounded-full bg-fill px-4 py-2 text-[14px] text-ink outline-none placeholder:text-muted focus:shadow-[var(--shadow-hairline)]"
          />
          <button type="submit" disabled={busy || !input.trim()} className="btn-primary btn-sm disabled:opacity-50">
            {busy ? '…' : 'Ask'}
          </button>
        </form>
        <p className="mt-2 text-[11px] text-muted">
          Predicted cortical response of an average viewer, not a measurement. Not validated against engagement.
        </p>
      </div>
    </div>
  )
}
