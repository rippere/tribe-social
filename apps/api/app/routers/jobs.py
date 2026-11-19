import logging
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

logger = logging.getLogger(__name__)

# Video URL allow-list.
#
# Each accepted shape pins the video ID to the exact form the matching yt-dlp
# extractor expects, so a URL that passes can only be handled by the YouTube or
# Instagram extractor, never by yt-dlp's Generic extractor (which follows
# redirects to arbitrary hosts). Rules:
#   * matched with fullmatch() under re.ASCII, so \w is [A-Za-z0-9_] only;
#   * YouTube IDs are exactly 11 chars -- shorter/longer "shorts/<id>" values
#     fall through to the Generic extractor;
#   * no "%" anywhere (percent-encoded "../" let YouTube resolve the path to an
#     arbitrary redirect), no extra path segments; a "#fragment" is dropped
#     during normalization (it is never sent to the server anyway);
#   * query params are "key=value" pairs with a conservative value charset
#     (letters, digits, "_", "-", "."), plus up to two trailing "=" so
#     base64 share tokens like Instagram's igsh=...== still work;
#   * any "list=" param is rejected outright (playlist enumeration).
_PARAM = r"[\w-]+=[\w.-]*={0,2}"
_QUERY = rf"(?:\?{_PARAM}(?:&{_PARAM})*)?"
_YT_HOST = r"(?:www\.|m\.|music\.)?youtube\.com"
_IG_HOST = r"(?:www\.)?instagram\.com"
VIDEO_URL_PATTERN = re.compile(
    r"https://(?:"
    rf"{_YT_HOST}/shorts/(?P<shorts>[\w-]{{11}})/?{_QUERY}"
    rf"|{_YT_HOST}/watch\?v=(?P<watch>[\w-]{{11}})(?:&{_PARAM})*"
    rf"|youtu\.be/(?P<short_link>[\w-]{{11}}){_QUERY}"
    # Optional "<username>/" prefix (yt-dlp supports it). "audio" is not a
    # post id: yt-dlp hands reel(s)/audio/ to the Generic extractor.
    rf"|{_IG_HOST}/(?:[\w.]{{1,30}}/)?(?:reels?|p)/(?!audio(?![\w-]))(?P<ig>[\w-]{{5,40}})/?{_QUERY}"
    r")",
    re.ASCII,
)
_PLAYLIST_PARAM = re.compile(r"[?&]list=", re.ASCII)
_SCHEME_HOST = re.compile(r"([A-Za-z][A-Za-z0-9+.-]*)://([^/?#]*)(.*)", re.DOTALL)

INVALID_URL_DETAIL = "Invalid URL — paste a YouTube Shorts or Instagram Reel link"
PLAYLIST_URL_DETAIL = "Playlist links aren't supported — paste a link to a single video"
DOWNLOAD_FAILED_DETAIL = (
    "Download failed — the video may be private, region-blocked, or unavailable"
)


class InvalidVideoURL(ValueError):
    def __init__(self, detail: str = INVALID_URL_DETAIL):
        super().__init__(detail)
        self.detail = detail


def normalize_video_url(raw: str) -> tuple[str, str]:
    """Validate a user-supplied video URL; return (normalized_url, video_id).

    Normalization happens BEFORE validation, and the normalized string is what
    gets passed to yt-dlp, so the checked value and the used value are the same:
      * surrounding whitespace is stripped;
      * schemeless input ("youtu.be/<id>") gets "https://" prepended -- the
        result must still pass the full allow-list, so this only helps
        legitimate copy/paste and cannot introduce a new host;
      * scheme and host are lower-cased (both are case-insensitive); the
        path/query are left alone because video IDs are case-sensitive;
      * a trailing "#fragment" is dropped (browsers never send it either).
    "http://" is NOT upgraded: only https input is accepted.
    Raises InvalidVideoURL.
    """
    url = (raw or "").strip()
    m = _SCHEME_HOST.fullmatch(url)
    if m is None:
        url = "https://" + url
        m = _SCHEME_HOST.fullmatch(url)
        if m is None:
            raise InvalidVideoURL()
    scheme, host, rest = m.groups()
    rest = rest.split("#", 1)[0]
    url = f"{scheme.lower()}://{host.lower()}{rest}"

    # Checked first so playlist links get a specific message; a list= URL is
    # rejected whatever else it contains.
    if _PLAYLIST_PARAM.search(url):
        raise InvalidVideoURL(PLAYLIST_URL_DETAIL)
    match = VIDEO_URL_PATTERN.fullmatch(url)
    if match is None:
        raise InvalidVideoURL()
    video_id = next(v for v in match.groupdict().values() if v)
    return url, video_id


def _safe_upload_name(raw: str | None) -> str:
    """Basename of a client-supplied filename; never a path component."""
    name = Path((raw or "").replace("\x00", "")).name
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
        try:
            video_url, video_id = normalize_video_url(video_url)
        except InvalidVideoURL as exc:
            raise HTTPException(422, exc.detail) from exc
        filename = f"{video_id}.mp4"

        if _INFER_ENABLED:
            from app.services.downloader import cleanup_download, fetch_video, yt_dlp_available
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
                # The exception text carries yt-dlp stderr (paths, versions,
                # upstream errors): log it, never return it to the client.
                logger.warning("video download failed for %s: %s", video_url, exc)
                detail = getattr(exc, "user_message", None) or DOWNLOAD_FAILED_DETAIL
                raise HTTPException(502, detail) from exc
            finally:
                # Remove the whole per-job download dir, not just the file we
                # read: anything else yt-dlp left there must not leak.
                if tmp_path is not None:
                    cleanup_download(tmp_path)

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
