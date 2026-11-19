// POST /api/trial/upload — one clip for an invited uploader.
//
// Headers: X-Invite: <22-char code>, X-Consent: v1, X-Filename (optional).
// Body: the raw video bytes (mp4 or mov, ≤ 50 MB, ≤ 60 s).
// Order matters: every check that can refuse the upload runs before anything is
// written, and the D1 insert that claims a use (and enforces the per-invite and
// global caps atomically) runs before the R2 write.
import { randomToken, sha256Hex } from '../../../lib/trial/crypto'
import type { PagesEnv } from '../../../lib/trial/env'
import { checkInvite, json, trialSite } from '../../../lib/trial/http'
import { LIMITS, uploadKey } from '../../../lib/trial/jobs'
import { sniffVideo, videoDurationSeconds } from '../../../lib/trial/video'

export const CONSENT_VERSION = 'v1'

export const onRequestPost = async ({ request, env }: { request: Request; env: PagesEnv }) => {
  // Result links and the GPU worker's signed URLs are built from this origin, so it
  // must be one we configured, not whatever host the request arrived on.
  const site = trialSite(env, request)
  if (!site) return json({ error: 'Use the link from your invite email.' }, 403)
  const check = await checkInvite(env.WAITLIST, request.headers.get('x-invite'))
  if (!check.ok) return json({ error: check.error }, check.status)
  if (request.headers.get('x-consent') !== CONSENT_VERSION) {
    return json({ error: 'Tick the consent box before uploading.' }, 400)
  }
  const declared = Number(request.headers.get('content-length') ?? '0')
  if (declared > LIMITS.maxBytes) return json({ error: 'The video is larger than 50 MB.' }, 413)

  const bytes = new Uint8Array(await request.arrayBuffer())
  if (bytes.byteLength > LIMITS.maxBytes) return json({ error: 'The video is larger than 50 MB.' }, 413)
  if (bytes.byteLength < 1024) return json({ error: 'That file is empty or too small to be a video.' }, 400)
  const ext = sniffVideo(bytes)
  if (!ext) return json({ error: 'Upload an MP4 or MOV video.' }, 415)
  const duration = videoDurationSeconds(bytes)
  if (duration !== null && duration > LIMITS.maxSeconds + 0.5) {
    return json({ error: `The clip is ${Math.round(duration)} seconds; the limit is 60.` }, 400)
  }

  const id = randomToken(16)
  const token = randomToken(32)
  const inviteHash = await sha256Hex(check.code)
  const now = Date.now()
  const maxUses = Math.min(check.invite.max_uses, LIMITS.usesPerInvite)

  // One statement, so the three caps hold under concurrent uploads.
  const claim = await env.TRIAL_DB.prepare(
    `INSERT INTO jobs (id, token_hash, token, invite_hash, email, site, ext, size_bytes, duration_s, status, created_at)
     SELECT ?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, 'uploading', ?10
     WHERE (SELECT COUNT(*) FROM jobs WHERE invite_hash = ?4) < ?11
       AND (SELECT COUNT(*) FROM jobs WHERE invite_hash = ?4
              AND status IN ('uploading', 'queued', 'submitted', 'running')) < ?12
       AND (SELECT COUNT(*) FROM jobs WHERE status IN ('uploading', 'queued', 'submitted', 'running')) < ?13`,
  )
    .bind(id, await sha256Hex(token), token, inviteHash, check.invite.email, site, ext, bytes.byteLength, duration, now,
      maxUses, LIMITS.activePerInvite, LIMITS.queueCap)
    .run()

  if (claim.meta.changes !== 1) {
    const r = await env.TRIAL_DB.prepare(
      `SELECT COUNT(*) AS used, SUM(status IN ('uploading', 'queued', 'submitted', 'running')) AS active
       FROM jobs WHERE invite_hash = ?`,
    )
      .bind(inviteHash)
      .first<{ used: number; active: number | null }>()
    if ((r?.used ?? 0) >= maxUses) return json({ error: 'This invite has used all of its uploads.' }, 403)
    if ((r?.active ?? 0) >= LIMITS.activePerInvite) {
      return json({ error: 'Your previous clip is still being scored. Upload the next one when it is done.' }, 429)
    }
    return json({ error: 'The trial queue is full right now. Try again in a little while.' }, 503, { 'retry-after': '600' })
  }

  try {
    await env.TRIAL_BUCKET.put(uploadKey({ id, ext }), bytes, {
      httpMetadata: { contentType: ext === 'mov' ? 'video/quicktime' : 'video/mp4' },
    })
  } catch (err) {
    await env.TRIAL_DB.prepare('DELETE FROM jobs WHERE id = ?').bind(id).run()
    console.error('trial upload: R2 put failed', err instanceof Error ? err.message : String(err))
    return json({ error: 'The upload could not be stored. Try again.' }, 502)
  }
  await env.TRIAL_DB.prepare(`UPDATE jobs SET status = 'queued' WHERE id = ? AND status = 'uploading'`).bind(id).run()

  // D1 is the only use counter. (No KV write-back: it could overwrite a concurrent revoke.)
  const usedNow = await env.TRIAL_DB.prepare('SELECT COUNT(*) AS n FROM jobs WHERE invite_hash = ?')
    .bind(inviteHash)
    .first<{ n: number }>()

  return json({ ok: true, token, remaining: Math.max(0, maxUses - (usedNow?.n ?? 0)) }, 201)
}
