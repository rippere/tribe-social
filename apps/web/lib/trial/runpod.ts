// RunPod control for the trial dispatcher: scale the endpoint, submit, poll, cancel.
// GraphQL (api.runpod.io) for endpoint settings, the v2 job API (api.runpod.ai) for jobs.

import type { DispatcherEnv } from './env'
import type { RunpodJob } from './jobs'

const GQL = 'https://api.runpod.io/graphql'
const JOBS = 'https://api.runpod.ai/v2'

function auth(env: DispatcherEnv): Record<string, string> {
  if (!env.RUNPOD_API_KEY) throw new Error('RUNPOD_API_KEY is not set')
  return { Authorization: `Bearer ${env.RUNPOD_API_KEY}`, 'Content-Type': 'application/json' }
}

const gqlString = (s: string) => JSON.stringify(s)

/**
 * Set workersMax (0 = off). saveEndpoint replaces the endpoint config, so every field
 * we rely on is sent each time: name + gpuIds are required, and leaving out the
 * template or network volume would detach them. gpuIds is always AMPERE_80.
 */
export async function setWorkersMax(env: DispatcherEnv, workersMax: number): Promise<void> {
  if (env.RUNPOD_GPU_IDS !== 'AMPERE_80') throw new Error('refusing to scale: gpuIds must be AMPERE_80')
  const fields = [
    `id: ${gqlString(env.RUNPOD_ENDPOINT_ID)}`,
    `name: ${gqlString(env.RUNPOD_ENDPOINT_NAME)}`,
    `gpuIds: ${gqlString(env.RUNPOD_GPU_IDS)}`,
    `templateId: ${gqlString(env.RUNPOD_TEMPLATE_ID)}`,
    env.RUNPOD_NETWORK_VOLUME_ID ? `networkVolumeId: ${gqlString(env.RUNPOD_NETWORK_VOLUME_ID)}` : '',
    `idleTimeout: ${Number(env.RUNPOD_IDLE_TIMEOUT_S ?? '120')}`,
    `scalerType: "QUEUE_DELAY"`,
    `scalerValue: 4`,
    `workersMin: 0`,
    `workersMax: ${Math.max(0, Math.min(1, workersMax))}`,
  ].filter(Boolean)
  const query = `mutation { saveEndpoint(input: { ${fields.join(', ')} }) { id workersMax gpuIds networkVolumeId } }`
  let last: unknown
  for (let attempt = 0; attempt < 3; attempt++) {
    try {
      const res = await fetch(GQL, { method: 'POST', headers: auth(env), body: JSON.stringify({ query }) })
      const body = (await res.json()) as { errors?: unknown; data?: { saveEndpoint?: { workersMax: number } } }
      if (!res.ok || body.errors || body.data?.saveEndpoint?.workersMax !== Math.min(1, workersMax)) {
        throw new Error(`saveEndpoint failed (${res.status}): ${JSON.stringify(body.errors ?? body).slice(0, 300)}`)
      }
      return
    } catch (err) {
      last = err
      await new Promise((r) => setTimeout(r, 1000 * 2 ** attempt))
    }
  }
  throw last instanceof Error ? last : new Error(String(last))
}

export interface SubmitInput {
  video_url: string
  filename: string
  activity_put_url: string
  max_seconds: number
}

export async function submitJob(env: DispatcherEnv, input: SubmitInput, webhook: string): Promise<string> {
  const res = await fetch(`${JOBS}/${env.RUNPOD_ENDPOINT_ID}/run`, {
    method: 'POST',
    headers: auth(env),
    body: JSON.stringify({
      input,
      webhook,
      // 20 min of execution per clip; 3 h total so a long cold start can't strand a job.
      policy: { executionTimeout: 20 * 60_000, ttl: 3 * 3600_000 },
    }),
  })
  const body = (await res.json().catch(() => ({}))) as { id?: string; error?: string }
  if (!res.ok || !body.id) throw new Error(`RunPod /run failed (${res.status}): ${JSON.stringify(body).slice(0, 300)}`)
  return body.id
}

/** Job status, or null when RunPod no longer knows the job (404 after TTL). */
export async function jobStatus(env: DispatcherEnv, runpodId: string): Promise<RunpodJob | null> {
  const res = await fetch(`${JOBS}/${env.RUNPOD_ENDPOINT_ID}/status/${runpodId}`, { headers: auth(env) })
  if (res.status === 404) return null
  if (!res.ok) throw new Error(`RunPod /status failed (${res.status})`)
  return (await res.json()) as RunpodJob
}

export async function cancelJob(env: DispatcherEnv, runpodId: string): Promise<void> {
  await fetch(`${JOBS}/${env.RUNPOD_ENDPOINT_ID}/cancel/${runpodId}`, { method: 'POST', headers: auth(env) }).catch(() => {})
}
