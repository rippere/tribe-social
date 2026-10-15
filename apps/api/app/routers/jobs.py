import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.services.inference import _INFER_ENABLED, _POD_URL, _REAL_MODE, submit_job
from app.store import jobs as job_store

router = APIRouter(prefix="/jobs", tags=["jobs"])

# Anchored allow-list, matched with fullmatch(): the whole string must be an
# https URL on one of these hosts. An unanchored search() let values like
# "http://127.0.0.1/?youtube.com/shorts/x" (SSRF) or
# "--exec=...youtube.com/shorts/x" (yt-dlp option injection) through.
# The path charset excludes ".", ":", "@" and "#", so the host cannot be
# extended ("youtube.com.evil.example") or swapped via userinfo.
VIDEO_URL_PATTERN = re.compile(
    r"https://(?:"
    r"(?:www\.|m\.)?youtube\.com/(?:shorts/|watch\?v=)"
    r"|youtu\.be/"
    r"|(?:www\.)?instagram\.com/(?:reel|p)/"
    r")[A-Za-z0-9_\-/?=&%]+"
)


def _safe_upload_name(raw: str | None) -> str:
    """Basename of a client-supplied filename; never a path component."""
    name = Path(raw or "").name
    if name in ("", ".", ".."):
        return "video_upload.mp4"
    return name

_MODE = "pod" if _POD_URL else ("real" if _REAL_MODE else "mock")

MAX_UPLOAD_BYTES = 50 * 1024 * 1024  # 50 MB
MAX_DURATION_SECONDS = 60


def _probe_duration(video_bytes: bytes) -> float | None:
    try:
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
            f.write(video_bytes)
            tmp = f.name
        result = subprocess.run(
            [
                "ffprobe", "-v", "quiet",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                tmp,
            ],
            capture_output=True, text=True, timeout=15,
        )
        os.unlink(tmp)
        val = result.stdout.strip()
        return float(val) if val else None
    except Exception:
        return None


@router.post("", status_code=202)
async def create_job(
    file: Optional[UploadFile] = File(None),
    video_url: Optional[str] = Form(None),
    youtube_url: Optional[str] = Form(None),  # backwards compat
):
    video_url = video_url or youtube_url
    if file is None and video_url is None:
        raise HTTPException(422, "Provide either a file or video_url")

    video_bytes: bytes | None = None
    filename: str

    if file is not None:
        filename = _safe_upload_name(file.filename)
        if not filename.endswith(".mp4"):
            raise HTTPException(422, "Only .mp4 files are supported")
        if _INFER_ENABLED:
            video_bytes = await file.read()
            if len(video_bytes) > MAX_UPLOAD_BYTES:
                raise HTTPException(
                    413,
                    "File exceeds 50 MB limit. For longer content, paste a YouTube URL instead.",
                )
            duration = _probe_duration(video_bytes)
            if duration is not None and duration > MAX_DURATION_SECONDS:
                raise HTTPException(
                    422,
                    f"Video is {duration:.0f}s — limit is {MAX_DURATION_SECONDS}s. "
                    "Upload a shorter clip or paste a YouTube URL.",
                )
    else:
        video_url = video_url.strip()
        if not VIDEO_URL_PATTERN.fullmatch(video_url):
            raise HTTPException(422, "Invalid URL — paste a YouTube Shorts or Instagram Reel link")

        tail = video_url.split("?v=")[-1].split("/")[-1].split("?")[0]
        match = re.search(r"[A-Za-z0-9_-]{7,}", tail)
        filename = f"{match.group(0)}.mp4" if match else "video_upload.mp4"

        if _INFER_ENABLED:
            from app.services.downloader import fetch_video, yt_dlp_available
            if not yt_dlp_available():
                raise HTTPException(503, "yt-dlp not available on this instance")
            tmp_path: Path | None = None
            try:
                tmp_path = fetch_video(video_url)
                filename = tmp_path.name
                video_bytes = tmp_path.read_bytes()
                if len(video_bytes) < 1024:
                    raise HTTPException(
                        status_code=502,
                        detail="Downloaded file invalid (too small) — the source URL may be private, blocked, or not a video",
                    )
            except RuntimeError as exc:
                raise HTTPException(502, f"Download failed: {exc}") from exc
            finally:
                if tmp_path and tmp_path.exists():
                    tmp_path.unlink(missing_ok=True)
                    try:
                        tmp_path.parent.rmdir()
                    except OSError:
                        pass

    job_id = await submit_job(filename, video_bytes)
    return {"job_id": job_id, "status": "queued", "mode": _MODE}


@router.get("/{job_id}")
async def get_job(job_id: str):
    job = job_store.get(job_id)
    if job is None:
        raise HTTPException(404, "Job not found")
    return job


@router.delete("/{job_id}")
async def cancel_job(job_id: str):
    job = job_store.get(job_id)
    if job is None:
        raise HTTPException(404, "Job not found")
    job_store.update(job_id, status="failed", error="Cancelled by user")
    return {"cancelled": True}
