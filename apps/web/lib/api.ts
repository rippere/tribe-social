import type { JobResponse } from './types'

const API = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

export const fetchCorpus = () => fetch(`${API}/corpus`).then(r => r.json())
export const fetchStats  = () => fetch(`${API}/corpus/stats`).then(r => r.json())
export const fetchHealth = (): Promise<{ status: string; mode: 'mock' | 'real'; runpod_endpoint_configured: boolean }> =>
  fetch(`${API}/health`).then(r => r.json())

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
  const res = await fetch(`${API}/jobs`, { method: 'POST', body: form })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail ?? 'Failed to create job')
  }
  return res.json()
}

export async function getJob(jobId: string): Promise<JobResponse> {
  const res = await fetch(`${API}/jobs/${jobId}`)
  if (!res.ok) throw new Error(`Job ${jobId} not found`)
  return res.json()
}
