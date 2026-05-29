"""
Video downloader using yt-dlp subprocess. Supports YouTube and Instagram Reels.
Returns Path to a temp .mp4 file. Caller is responsible for cleanup.
"""
import os
import shutil
import subprocess
import tempfile
from pathlib import Path


def yt_dlp_available() -> bool:
    return shutil.which("yt-dlp") is not None


def fetch_video(url: str) -> Path:
    """
    Downloads a YouTube or Instagram Reel URL to a temp .mp4 file.
    Returns the Path. Caller must delete after use (try/finally).
    Raises RuntimeError on failure.
    """
    if not yt_dlp_available():
        raise RuntimeError("yt-dlp is not installed or not on PATH")

    tmp_dir = tempfile.mkdtemp(prefix="tribe_dl_")
    output_template = str(Path(tmp_dir) / "%(id)s.%(ext)s")

    cmd = [
        "yt-dlp",
        "--format", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "--merge-output-format", "mp4",
        "--no-playlist",
        "--output", output_template,
    ]

    # Optional cookie support for sites that require login (e.g. Instagram).
    # If YTDLP_COOKIES_FILE points at an existing file, pass it through.
    # Unset/missing env var keeps current behavior (works for public YouTube).
    cookies_file = os.environ.get("YTDLP_COOKIES_FILE")
    if cookies_file and Path(cookies_file).is_file():
        cmd += ["--cookies", cookies_file]

    cmd.append(url)

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

    stderr = (result.stderr or "").strip()

    # Inspect yt-dlp output for known failure signals BEFORE trusting file
    # existence. Instagram reels in particular fail with auth/login/private
    # messages that would otherwise surface as an opaque "no .mp4 found" error.
    combined_output = f"{result.stdout or ''}\n{stderr}"
    lowered = combined_output.lower()
    stderr_tail = stderr[-1500:]

    auth_signals = ("login required", "login", "private", "rate-limit", "rate limit")
    if any(signal in lowered for signal in auth_signals):
        raise RuntimeError(
            "Instagram download failed — the reel may be private, region-blocked, "
            "or require login cookies (set YTDLP_COOKIES_FILE to a cookies.txt path). "
            f"yt-dlp stderr: {stderr_tail}"
        )

    if result.returncode != 0 or "ERROR" in combined_output:
        raise RuntimeError(f"yt-dlp failed (exit {result.returncode}): {stderr_tail}")

    mp4_files = list(Path(tmp_dir).glob("*.mp4"))
    if not mp4_files:
        raise RuntimeError(
            f"yt-dlp reported success but produced no .mp4 in {tmp_dir}. "
            f"yt-dlp stderr: {stderr_tail}"
        )

    return mp4_files[0]
