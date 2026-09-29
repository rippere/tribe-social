'use client'

import { useState, useCallback } from 'react'
import { useDropzone } from 'react-dropzone'
import { submitJob } from '@/lib/api'

interface Props {
  onJobCreated: (jobId: string) => void
}

const MAX_SIZE_BYTES = 50 * 1024 * 1024 // 50 MB

export default function VideoDropzone({ onJobCreated }: Props) {
  const [tab, setTab] = useState<'upload' | 'url'>('upload')
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [youtubeUrl, setYoutubeUrl] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const onDrop = useCallback((accepted: File[], rejected: import('react-dropzone').FileRejection[]) => {
    setError(null)
    if (rejected.length > 0) {
      const r = rejected[0]
      if (r.errors.some((e) => e.code === 'file-too-large')) {
        setError('File exceeds the 50 MB limit. For longer content, use a YouTube URL.')
      } else {
        setError('Only .mp4 files are supported.')
      }
      return
    }
    if (accepted.length > 0) {
      const f = accepted[0]
      if (!f.name.endsWith('.mp4')) {
        setError('Only .mp4 files are supported.')
        return
      }
      setSelectedFile(f)
    }
  }, [])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { 'video/mp4': ['.mp4'] },
    maxSize: MAX_SIZE_BYTES,
    maxFiles: 1,
    noClick: false,
  })

  const handleSubmitFile = async () => {
    if (!selectedFile) return
    setError(null)
    setLoading(true)
    try {
      const { job_id } = await submitJob(selectedFile)
      onJobCreated(job_id)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Unknown error')
    } finally {
      setLoading(false)
    }
  }

  const handleSubmitUrl = async () => {
    if (!youtubeUrl.trim()) return
    setError(null)
    setLoading(true)
    try {
      const { job_id } = await submitJob(undefined, youtubeUrl.trim())
      onJobCreated(job_id)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Unknown error')
    } finally {
      setLoading(false)
    }
  }

  const consent = (
    <p className="text-[12px] leading-5 text-muted">
      By scoring a clip you confirm you have the rights to it. The video is sent to a rented cloud GPU and isn&apos;t
      kept; the scores are saved to our research dataset.
    </p>
  )

  const errorBox = error && (
    <p className="rounded-xl bg-[#F87171]/10 px-4 py-2 text-[13px] text-[#F87171]">{error}</p>
  )

  return (
    <div>
      {/* Tabs */}
      <div className="mb-5 flex w-fit gap-1 rounded-full bg-fill p-1" role="tablist" aria-label="Input type">
        {(['upload', 'url'] as const).map((t) => (
          <button
            key={t}
            type="button"
            role="tab"
            aria-selected={tab === t}
            onClick={() => { setTab(t); setError(null); setSelectedFile(null) }}
            className={`rounded-full px-4 py-1.5 text-[13px] font-medium transition-colors ${
              tab === t ? 'bg-ink text-on-ink' : 'text-muted hover:text-ink'
            }`}
          >
            {t === 'upload' ? 'Upload file' : 'Paste URL'}
          </button>
        ))}
      </div>

      {tab === 'upload' && (
        <div className="space-y-4">
          <div
            {...getRootProps()}
            className={`cursor-pointer rounded-2xl border border-dashed p-12 text-center transition-colors ${
              isDragActive ? 'border-accent bg-accent-bg' : 'border-line bg-fill hover:border-ink/30'
            }`}
          >
            <input {...getInputProps()} />
            {selectedFile ? (
              <div className="space-y-1">
                <p className="font-medium text-ink">{selectedFile.name}</p>
                <p className="text-[13px] text-muted">{(selectedFile.size / (1024 * 1024)).toFixed(1)} MB</p>
                <p className="mt-2 text-[12px] text-accent">Click or drop to replace</p>
              </div>
            ) : (
              <div className="space-y-2">
                <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-fill">
                  <svg className="h-6 w-6 text-muted" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden>
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                      d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                  </svg>
                </div>
                <p className="font-medium text-ink">
                  {isDragActive ? 'Drop your .mp4 here' : 'Drag and drop an .mp4, or click to browse'}
                </p>
                <p className="text-[12px] text-muted">MP4 only · 50 MB · 60 seconds max</p>
              </div>
            )}
          </div>

          {errorBox}
          {consent}

          <button
            type="button"
            onClick={handleSubmitFile}
            disabled={!selectedFile || loading}
            className="btn-primary btn-lg w-full disabled:cursor-not-allowed disabled:opacity-40"
          >
            {loading ? 'Submitting…' : 'Score this clip'}
          </button>
        </div>
      )}

      {tab === 'url' && (
        <div className="space-y-4">
          <div>
            <label htmlFor="clip-url" className="mb-2 block text-[13px] text-muted">
              YouTube Shorts or Instagram Reel URL
            </label>
            <input
              id="clip-url"
              type="text"
              value={youtubeUrl}
              onChange={(e) => setYoutubeUrl(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSubmitUrl()}
              placeholder="https://www.instagram.com/reel/... or https://youtu.be/..."
              className="w-full rounded-full border border-line bg-fill px-4 py-2.5 text-[14px] text-ink placeholder:text-muted/70 focus:border-accent focus:outline-none"
            />
          </div>

          {errorBox}
          {consent}

          <button
            type="button"
            onClick={handleSubmitUrl}
            disabled={!youtubeUrl.trim() || loading}
            className="btn-primary btn-lg w-full disabled:cursor-not-allowed disabled:opacity-40"
          >
            {loading ? 'Submitting…' : 'Score this URL'}
          </button>
        </div>
      )}
    </div>
  )
}
