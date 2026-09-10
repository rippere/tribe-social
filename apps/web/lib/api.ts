import type { JobResponse, InferenceMode } from './types'

function resolveApiBase(): string {
  const url = process.env.NEXT_PUBLIC_API_URL
  if (url) return url
  if (process.env.NODE_ENV === 'production') {
    throw new Error(
      'NEXT_PUBLIC_API_URL is not set. Refusing to fall back to http://localhost:8000 in production.',
    )
  }
  return 'http://localhost:8000'
}

// Single source of truth for the API base URL. Import this everywhere instead
// of re-reading process.env.NEXT_PUBLIC_API_URL.
export const API_BASE = resolveApiBase()

export const fetchCorpus = () => fetch(`${API_BASE}/corpus`).then(r => r.json())
export const fetchStats  = () => fetch(`${API_BASE}/corpus/stats`).then(r => r.json())
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
