'use client'

import { useCallback, useEffect, useState } from 'react'
import { useDropzone, type FileRejection } from 'react-dropzone'
import { ClaimBanner, TrialFooter } from './TrialNotice'

const MAX_BYTES = 50 * 1024 * 1024
const MAX_SECONDS = 60
export const CONSENT_TEXT =
  'I own this video or have the right to upload it. It is deleted once scored, or after 72 hours at most. The predicted response is kept for 30 days at a private link.'

type InviteState =
  | { kind: 'checking' }
  | { kind: 'missing' }
  | { kind: 'invalid'; error: string }
  | { kind: 'ok'; remaining: number; maxUses: number; active: number; expires: string }

/** Duration from the browser's own decoder; null when it can't tell (the server checks too). */
function readDuration(file: File): Promise<number | null> {
  return new Promise((resolve) => {
    const v = document.createElement('video')
    const url = URL.createObjectURL(file)
    const done = (d: number | null) => {
      URL.revokeObjectURL(url)
      resolve(d)
    }
    v.preload = 'metadata'
    v.onloadedmetadata = () => done(Number.isFinite(v.duration) ? v.duration : null)
    v.onerror = () => done(null)
    v.src = url
  })
}

function upload(file: File, code: string, onProgress: (p: number) => void): Promise<{ token: string }> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    xhr.open('POST', '/api/trial/upload')
    xhr.setRequestHeader('X-Invite', code)
    xhr.setRequestHeader('X-Consent', 'v1')
    xhr.setRequestHeader('Content-Type', file.type || 'application/octet-stream')
    xhr.upload.onprogress = (e) => e.lengthComputable && onProgress(Math.round((e.loaded / e.total) * 100))
    xhr.onload = () => {
      let body: { token?: string; error?: string } = {}
      try {
        body = JSON.parse(xhr.responseText)
      } catch {
        /* non-JSON error page */
      }
      if (xhr.status >= 200 && xhr.status < 300 && body.token) resolve({ token: body.token })
      else reject(new Error(body.error ?? `Upload failed (${xhr.status}).`))
    }
    xhr.onerror = () => reject(new Error('The upload was interrupted. Check your connection and try again.'))
    xhr.send(file)
  })
}

export default function TrialUpload() {
  const [code, setCode] = useState<string | null>(null)
  const [invite, setInvite] = useState<InviteState>({ kind: 'checking' })
  const [file, setFile] = useState<File | null>(null)
  const [duration, setDuration] = useState<number | null>(null)
  const [consent, setConsent] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [progress, setProgress] = useState<number | null>(null)

  // A different link pasted into the same tab only changes the fragment: start over.
  useEffect(() => {
    const onHash = () => window.location.reload()
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
  }, [])

  useEffect(() => {
    const c = window.location.hash.slice(1)
    if (!c) {
      setInvite({ kind: 'missing' })
      return
    }
    setCode(c)
    fetch('/api/trial/invite', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ code: c }),
    })
      .then(async (r) => {
        const b = await r.json()
        if (!r.ok) setInvite({ kind: 'invalid', error: b.error ?? 'This invite link does not work.' })
        else setInvite({ kind: 'ok', remaining: b.remaining, maxUses: b.max_uses, active: b.active, expires: b.expires })
      })
      .catch(() => setInvite({ kind: 'invalid', error: 'Could not check the invite. Reload to try again.' }))
  }, [])

  const onDrop = useCallback(async (accepted: File[], rejected: FileRejection[]) => {
    setError(null)
    setFile(null)
    setDuration(null)
    if (rejected.length > 0) {
      setError(
        rejected[0].errors.some((e) => e.code === 'file-too-large')
          ? 'The video is larger than 50 MB.'
          : 'Upload an MP4 or MOV video.',
      )
      return
    }
    const f = accepted[0]
    if (!f) return
    const d = await readDuration(f)
    if (d !== null && d > MAX_SECONDS + 0.5) {
      setError(`The clip is ${Math.round(d)} seconds; the limit is ${MAX_SECONDS}. Trim it and try again.`)
      return
    }
    setFile(f)
    setDuration(d)
  }, [])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { 'video/mp4': ['.mp4'], 'video/quicktime': ['.mov'] },
    maxSize: MAX_BYTES,
    maxFiles: 1,
    disabled: progress !== null,
  })

  const submit = async () => {
    if (!file || !code || !consent) return
    setError(null)
    setProgress(0)
    try {
      const { token } = await upload(file, code, setProgress)
      window.location.assign(`/trial/result#${token}`)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Upload failed.')
      setProgress(null)
    }
  }

  const ok = invite.kind === 'ok'
  const canUpload = ok && invite.remaining > 0 && invite.active === 0

  return (
    <div className="mx-auto max-w-[720px] px-4 pt-12 pb-16 md:px-6 md:pt-16">
      <p className="mb-3 text-[13px] font-medium text-muted">Free research trial · invite only</p>
      <h1 className="type-h2 text-ink">Score a clip with TRIBE v2</h1>
      <p className="type-lead mt-3">
        Upload a video of up to 60 seconds. TRIBE v2 predicts how an average brain responds to it, second by second.
        You get a private result link straight away and an email when the result is ready.
      </p>

      <div className="mt-6">
        <ClaimBanner />
      </div>

      <div className="mt-6 rounded-[22px] bg-elevated p-5 shadow-[var(--shadow-window),var(--shadow-hairline)] md:p-6">
        {invite.kind === 'checking' && <p className="text-[14px] text-muted">Checking your invite…</p>}
        {invite.kind === 'missing' && (
          <p className="text-[14px] text-muted">
            This page needs the private link from your invite email. Not invited yet? Join the waitlist on the{' '}
            <a href="/" className="underline underline-offset-2">
              home page
            </a>
            .
          </p>
        )}
        {invite.kind === 'invalid' && <p className="text-[14px] text-[#F87171]">{invite.error}</p>}

        {ok && (
          <>
            <p className="text-[13px] text-muted">
              {invite.remaining} of {invite.maxUses} uploads left · invite valid until {invite.expires.slice(0, 10)}
            </p>
            {invite.active > 0 && (
              <p className="mt-2 text-[13px] text-[#FBBF24]">
                Your previous clip is still being scored. Open its result link; you can upload the next one once it
                is done.
              </p>
            )}

            {canUpload && (
              <>
                <div
                  {...getRootProps()}
                  className={`mt-4 flex min-h-[180px] cursor-pointer flex-col items-center justify-center rounded-[16px] border border-dashed px-6 text-center transition-colors ${
                    isDragActive ? 'border-accent bg-accent-bg' : 'border-line bg-fill hover:border-ink/40'
                  }`}
                >
                  <input {...getInputProps()} aria-label="Choose a video" />
                  {file ? (
                    <>
                      <p className="text-[15px] font-medium text-ink">{file.name}</p>
                      <p className="mt-1 text-[13px] text-muted">
                        {(file.size / 1024 / 1024).toFixed(1)} MB{duration !== null ? ` · ${duration.toFixed(1)} s` : ''} ·
                        click to choose another
                      </p>
                    </>
                  ) : (
                    <>
                      <p className="text-[15px] font-medium text-ink">Drop a video here, or click to choose</p>
                      <p className="mt-1 text-[13px] text-muted">MP4 or MOV · up to 60 seconds · 50 MB max</p>
                    </>
                  )}
                </div>

                <label className="mt-4 flex cursor-pointer items-start gap-3 text-[14px] leading-6 text-ink">
                  <input
                    type="checkbox"
                    checked={consent}
                    onChange={(e) => setConsent(e.target.checked)}
                    className="mt-1 h-4 w-4 shrink-0 accent-[#5CE1F0]"
                  />
                  <span>{CONSENT_TEXT}</span>
                </label>

                {progress !== null ? (
                  <div className="mt-5">
                    <div className="h-1.5 w-full overflow-hidden rounded-full bg-fill">
                      <div className="h-full rounded-full bg-accent transition-all" style={{ width: `${progress}%` }} />
                    </div>
                    <p className="mt-2 text-center text-[13px] text-muted">Uploading… {progress}%</p>
                  </div>
                ) : (
                  <button
                    type="button"
                    onClick={submit}
                    disabled={!file || !consent}
                    className="btn-primary mt-5 w-full disabled:cursor-not-allowed disabled:opacity-40"
                  >
                    Upload and score
                  </button>
                )}
              </>
            )}
            {invite.remaining === 0 && invite.active === 0 && (
              <p className="mt-3 text-[14px] text-muted">This invite has used all of its uploads.</p>
            )}
          </>
        )}
        {error && (
          <p role="alert" className="mt-4 text-[14px] text-[#F87171]">
            {error}
          </p>
        )}
      </div>

      <TrialFooter />
    </div>
  )
}
