// "Ask about this clip": answers questions about one scored clip (lib/clips.ts) from
// TRIBE v2's real per-second prediction (built by research/clip_chat_context.py),
// via any OpenAI-compatible chat endpoint or Cloudflare Workers AI.
//
// Served by app/api/clip-chat/route.node.ts under `next dev` / `next start`, and by
// functions/api/clip-chat.ts on Cloudflare Pages (static export). Server-only env,
// never committed (apps/web/.env.local locally, Pages project settings in prod):
//   CHAT_LLM_BASE_URL  e.g. https://host:8000/v1 (an OpenAI-compatible server)
//   CHAT_LLM_API_KEY
//   CHAT_LLM_MODEL     optional; defaults to the first model the server lists
// With no CHAT_LLM_BASE_URL, an `AI` (Workers AI) binding is used instead.

import { CLIPS, getClip, REGION_KEYS as KEYS, type ClipContext } from './clips'

export type ChatEnv = {
  CHAT_LLM_BASE_URL?: string
  CHAT_LLM_API_KEY?: string
  CHAT_LLM_MODEL?: string
  AI?: { run(model: string, input: Record<string, unknown>): Promise<unknown> }
}

/** Workers AI model used when the AI binding serves the chat. */
const WORKERS_AI_MODEL = '@cf/meta/llama-3.3-70b-instruct-fp8-fast'

const MAX_TURNS = 12
const MAX_CHARS = 800
const MAX_ANSWER_CHARS = 3000

type Turn = { role: 'user' | 'assistant'; content: string }

// One row per second: what's on screen, then each region's value relative to the
// whole cortex at that second (z). Compact so the prompt prefills fast.
function contextTable(clip: ClipContext): string {
  const header = ['sec', 'shot', 'cortexGFP', ...KEYS].join(' | ')
  const rows = Array.from({ length: clip.seconds }, (_, s) => {
    const shot = clip.timeline.findIndex(t => s >= t.from && s < t.to) + 1
    return [
      s,
      shot,
      clip.whole_cortex.global_field_power_per_second[s].toFixed(2),
      ...KEYS.map(k => clip.regions[k].vs_cortex_z[s].toFixed(2)),
    ].join(' | ')
  })
  return [header, ...rows].join('\n')
}

function systemPrompt(clip: ClipContext): string {
  return `You are fMRIght's clip analyst. You answer questions about ONE video using ONLY the data below: Meta TRIBE v2's predicted cortical response to it. Be concrete: cite seconds and values from the table.

CLIP: ${clip.clip}
SHOTS:
${clip.timeline.map((t, i) => `${i + 1}. ${t.from}-${t.to}s: ${t.shot}`).join('\n')}

REGIONS (what each column is):
${KEYS.map(k => `- ${k}: ${clip.regions[k].area}`).join('\n')}

TABLE: per second, cortexGFP = global field power (spread of the predicted response across the cortex; higher = stronger overall drive). Region columns = that region's predicted response minus the whole-cortex mean at the same second, in cortex SDs (positive = above the cortex average).
${contextTable(clip)}

RULES (non-negotiable; this is shown to scientists):
- Say "predicted response" or "the model predicts", never "the viewer's brain did" or "brain activity". It is a group-average encoding model, not a measurement of anyone.
- The released TRIBE v2 checkpoint predicts the cortical surface only (the paper's subcortical head was not released). It cannot see the nucleus accumbens / ventral striatum, the main reward signal in neuroforecasting work. If asked about reward, wanting or "dopamine", say this.
- Do not claim the clip will get views, retention or engagement. If asked, say it is unvalidated: our pilot found r = 0.25, p = 0.24, n = 24, and Sahu & Pandey (arXiv:2607.01400, 2026) found TRIBE's signal did not predict YouTube re-watch. Our pre-registered test targets early retention (3-5 s).
- Timing is approximate: the prediction is BOLD-like, so it is smooth and seconds-scale.
- Regions are Destrieux-atlas approximations of HCP MMP1.0 areas.
- If the table can't answer the question, say so plainly. Never invent numbers.
- Report what the numbers show; don't explain them as feelings or intent ("reduces affective valuation"). If you offer an interpretation, label it a hypothesis.
- Plain text only: no markdown, no backticks, no bold. Call regions by plain name (attention, social...) and cortexGFP "overall predicted drive"; never write column names.
- Under 120 words unless asked for detail. Plain English; go technical if the user does.`
}

const SYSTEM = new Map(CLIPS.map(c => [c.slug, systemPrompt(c.context)]))

function badRequest(msg: string) {
  return Response.json({ error: msg }, { status: 400 })
}

function parseTurns(body: unknown): Turn[] | string {
  const msgs = (body as { messages?: unknown })?.messages
  if (!Array.isArray(msgs) || msgs.length === 0) return 'messages must be a non-empty array'
  if (msgs.length > MAX_TURNS) return `at most ${MAX_TURNS} messages`
  const turns: Turn[] = []
  for (const m of msgs) {
    const { role, content } = (m ?? {}) as Partial<Turn>
    if ((role !== 'user' && role !== 'assistant') || typeof content !== 'string') return 'bad message'
    if (role === 'user' && content.length > MAX_CHARS) return `messages are limited to ${MAX_CHARS} characters`
    // Earlier answers can run long when the user asks for detail; keep them, trimmed.
    turns.push({ role, content: role === 'assistant' ? content.slice(0, MAX_ANSWER_CHARS) : content })
  }
  if (turns[turns.length - 1].role !== 'user') return 'last message must be from the user'
  return turns
}

let cachedModel: string | undefined

async function modelId(base: string, key: string, configured?: string): Promise<string> {
  if (configured) return configured
  if (cachedModel) return cachedModel
  const res = await fetch(`${base}/models`, { headers: { Authorization: `Bearer ${key}` } })
  if (!res.ok) throw new Error(`model list failed: ${res.status}`)
  const id = (await res.json())?.data?.[0]?.id
  if (!id) throw new Error('chat server lists no models')
  cachedModel = id as string
  return cachedModel
}

/** Drops any <think>…</think> span from a stream of text chunks. Call flush() at the end. */
function thinkFilter() {
  let inThink = false
  let buf = ''
  const push = (chunk: string): string => {
    buf += chunk
    let out = ''
    for (;;) {
      if (inThink) {
        const end = buf.indexOf('</think>')
        if (end < 0) {
          buf = buf.slice(-8)
          return out
        }
        buf = buf.slice(end + 8)
        inThink = false
      } else {
        const start = buf.indexOf('<think>')
        if (start < 0) {
          // Hold back a possible partial "<think" tag at the end.
          const keep = buf.lastIndexOf('<')
          const safe = keep >= 0 && buf.length - keep < 7 ? keep : buf.length
          out += buf.slice(0, safe)
          buf = buf.slice(safe)
          return out
        }
        out += buf.slice(0, start)
        buf = buf.slice(start + 7)
        inThink = true
      }
    }
  }
  // Text held back as a possible "<think" (e.g. "z <1") is real text once the stream ends.
  const flush = (): string => {
    const rest = inThink ? '' : buf
    buf = ''
    return rest
  }
  return { push, flush }
}

/** OpenAI-style SSE (choices[0].delta.content) or Workers AI SSE ({"response": ...}) to plain text. */
function sseToText(body: ReadableStream<Uint8Array>): ReadableStream<Uint8Array> {
  const decoder = new TextDecoder()
  const encoder = new TextEncoder()
  const strip = thinkFilter()
  const reader = body.getReader()
  let pending = ''

  return new ReadableStream<Uint8Array>({
    async start(controller) {
      const emit = (text: string) => {
        if (text) controller.enqueue(encoder.encode(text))
      }
      const handle = (line: string) => {
        const data = line.trim()
        if (!data.startsWith('data:')) return
        const payload = data.slice(5).trim()
        if (payload === '[DONE]') return
        try {
          const event = JSON.parse(payload)
          const text = event?.choices?.[0]?.delta?.content ?? event?.response
          if (typeof text === 'string') emit(strip.push(text))
        } catch {
          // ignore keep-alives and partial events
        }
      }
      try {
        for (;;) {
          const { done, value } = await reader.read()
          if (done) break
          pending += decoder.decode(value, { stream: true })
          const lines = pending.split('\n')
          pending = lines.pop() ?? ''
          lines.forEach(handle)
        }
        handle(pending)
        emit(strip.flush())
      } catch {
        // Upstream dropped mid-answer: say so rather than pass off a partial answer.
        try {
          emit(strip.flush() + ' [answer cut off]')
        } catch {
          // the client already went away
        }
      } finally {
        try {
          controller.close()
        } catch {
          // already cancelled by the client
        }
      }
    },
    cancel(reason) {
      return reader.cancel(reason)
    },
  })
}

export async function handleClipChat(req: Request, env: ChatEnv): Promise<Response> {
  const base = env.CHAT_LLM_BASE_URL?.replace(/\/$/, '')
  const key = env.CHAT_LLM_API_KEY
  if (!(base && key) && !env.AI) {
    return Response.json({ error: 'Chat is not configured on this server.' }, { status: 503 })
  }

  const body = await req.json().catch(() => null)
  const slug = (body as { clip?: unknown })?.clip ?? CLIPS[0].slug
  const system = typeof slug === 'string' && getClip(slug) ? SYSTEM.get(slug) : undefined
  if (!system) return badRequest('unknown clip')
  const turns = parseTurns(body)
  if (typeof turns === 'string') return badRequest(turns)
  const messages = [{ role: 'system', content: system }, ...turns]

  let upstream: ReadableStream<Uint8Array>
  try {
    if (base && key) {
      const res = await fetch(`${base}/chat/completions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${key}` },
        body: JSON.stringify({
          model: await modelId(base, key, env.CHAT_LLM_MODEL),
          messages,
          stream: true,
          max_tokens: 500,
          temperature: 0.3,
          // Thinking off: vLLM/TabbyAPI read chat_template_kwargs, Ollama reads reasoning_effort.
          chat_template_kwargs: { enable_thinking: false },
          reasoning_effort: 'none',
        }),
        signal: req.signal,
      })
      if (!res.ok || !res.body) {
        return Response.json({ error: `The analysis model returned ${res.status}.` }, { status: 502 })
      }
      upstream = res.body
    } else {
      const out = await env.AI!.run(env.CHAT_LLM_MODEL || WORKERS_AI_MODEL, {
        messages,
        stream: true,
        max_tokens: 500,
        temperature: 0.3,
      })
      if (!(out instanceof ReadableStream)) throw new Error('Workers AI did not stream')
      upstream = out as ReadableStream<Uint8Array>
    }
  } catch {
    return Response.json({ error: 'The analysis model is unreachable right now.' }, { status: 502 })
  }

  return new Response(sseToText(upstream), {
    headers: { 'Content-Type': 'text/plain; charset=utf-8', 'Cache-Control': 'no-store' },
  })
}
