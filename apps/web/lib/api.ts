import type { JobResponse, InferenceMode } from './types'

function resolveApiBase(): string | null {
  const url = process.env.NEXT_PUBLIC_API_URL
  if (url) return url
  // Never fall back to localhost in production: a build without the variable (e.g.
  // the static Cloudflare site) ships with scoring switched off instead.
  return process.env.NODE_ENV === 'production' ? null : 'http://localhost:8000'
}

const RESOLVED = resolveApiBase()

/** False when this build has no scoring API; the scorer then says so instead of failing. */
export const API_CONFIGURED = RESOLVED !== null

// Single source of truth for the API base URL. Import this everywhere instead
// of re-reading process.env.NEXT_PUBLIC_API_URL.
export const API_BASE = RESOLVED ?? ''

function requireApi(): void {
  if (!API_CONFIGURED) throw new Error('The scoring API is offline on this site.')
}

export const fetchCorpus = async () => (requireApi(), fetch(`${API_BASE}/corpus`).then(r => r.json()))
export const fetchStats = async () => (requireApi(), fetch(`${API_BASE}/corpus/stats`).then(r => r.json()))
export const fetchHealth = (): Promise<{ status: string; mode: InferenceMode; runpod_endpoint_configured: boolean }> =>
  fetch(`${API_BASE}/health`).then(r => r.json())

export async function submitJob(
  file?: File,
  youtubeUrl?: string,
): Promise<{ job_id: string }> {
  const form = new FormData()
  if (file) {
    form.append('file', file)
  } else if (youtubeUrl) {
    form.append('video_url', youtubeUrl)
  } else {
    throw new Error('Provide either a file or youtubeUrl')
  }
  const res = await fetch(`${API_BASE}/jobs`, { method: 'POST', body: form })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail ?? 'Failed to create job')
  }
  return res.json()
}

export async function getJob(jobId: string): Promise<JobResponse> {
  const res = await fetch(`${API_BASE}/jobs/${jobId}`)
  if (!res.ok) throw new Error(`Job ${jobId} not found`)
  return res.json()
}
