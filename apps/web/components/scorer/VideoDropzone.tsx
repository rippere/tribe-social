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

  return (
    <div className="mt-8 rounded-xl border border-[#1F2937] bg-[#111827] p-6">
      {/* Tabs */}
      <div className="flex gap-1 mb-6 p-1 rounded-lg bg-[#0D0D0D] w-fit">
        {(['upload', 'url'] as const).map((t) => (
          <button
            key={t}
            onClick={() => { setTab(t); setError(null); setSelectedFile(null) }}
            className={`px-4 py-1.5 rounded-md text-sm font-medium transition-colors ${
              tab === t
                ? 'bg-[#6366F1] text-white'
                : 'text-[#9CA3AF] hover:text-[#F9FAFB]'
            }`}
          >
            {t === 'upload' ? 'Upload File' : 'Paste URL'}
          </button>
        ))}
      </div>

      {tab === 'upload' && (
        <div className="space-y-4">
          <div
            {...getRootProps()}
            className={`border-2 border-dashed rounded-xl p-12 text-center cursor-pointer transition-colors ${
              isDragActive
                ? 'border-[#6366F1] bg-[#6366F1]/5'
                : 'border-[#374151] hover:border-[#6366F1]/60 hover:bg-[#6366F1]/5'
            }`}
          >
            <input {...getInputProps()} />
            {selectedFile ? (
              <div className="space-y-1">
                <p className="text-[#F9FAFB] font-medium">{selectedFile.name}</p>
                <p className="text-[#9CA3AF] text-sm">
                  {(selectedFile.size / (1024 * 1024)).toFixed(1)} MB
                </p>
                <p className="text-[#6366F1] text-xs mt-2">Click or drop to replace</p>
              </div>
            ) : (
              <div className="space-y-2">
                <div className="mx-auto w-12 h-12 rounded-full bg-[#1F2937] flex items-center justify-center mb-3">
                  <svg className="w-6 h-6 text-[#9CA3AF]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                      d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                  </svg>
                </div>
                <p className="text-[#F9FAFB] font-medium">
                  {isDragActive ? 'Drop your .mp4 here' : 'Drag & drop your .mp4 here, or click to browse'}
                </p>
                <p className="text-[#9CA3AF] text-xs">MP4 only · 50 MB · 60s max</p>
              </div>
            )}
          </div>

          {error && (
            <p className="text-[#DC2626] text-sm bg-[#DC2626]/10 rounded-lg px-4 py-2">{error}</p>
          )}

          <button
            onClick={handleSubmitFile}
            disabled={!selectedFile || loading}
            className="w-full py-2.5 rounded-lg bg-[#6366F1] text-white font-medium text-sm disabled:opacity-40 disabled:cursor-not-allowed hover:bg-[#4F46E5] transition-colors"
          >
            {loading ? 'Submitting…' : 'Analyze Video'}
          </button>
        </div>
      )}

      {tab === 'url' && (
        <div className="space-y-4">
          <div>
            <label className="block text-sm text-[#9CA3AF] mb-2">YouTube Shorts or Instagram Reel URL</label>
            <input
              type="text"
              value={youtubeUrl}
              onChange={(e) => setYoutubeUrl(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSubmitUrl()}
              placeholder="https://www.instagram.com/reel/... or https://youtu.be/..."
              className="w-full px-4 py-2.5 rounded-lg bg-[#0D0D0D] border border-[#374151] text-[#F9FAFB] placeholder-[#4B5563] focus:outline-none focus:border-[#6366F1] text-sm"
            />
          </div>

          {error && (
            <p className="text-[#DC2626] text-sm bg-[#DC2626]/10 rounded-lg px-4 py-2">{error}</p>
          )}

          <button
            onClick={handleSubmitUrl}
            disabled={!youtubeUrl.trim() || loading}
            className="w-full py-2.5 rounded-lg bg-[#6366F1] text-white font-medium text-sm disabled:opacity-40 disabled:cursor-not-allowed hover:bg-[#4F46E5] transition-colors"
          >
            {loading ? 'Submitting…' : 'Analyze URL'}
          </button>
        </div>
      )}
    </div>
  )
}
