"""
Video downloader using yt-dlp subprocess. Supports YouTube and Instagram Reels.
Returns Path to a temp .mp4 file inside a per-job temp dir. Caller is
responsible for cleanup via cleanup_download(path).
"""
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

TMP_DIR_PREFIX = "tribe_dl_"
MAX_FILESIZE = "50M"  # matches the API's 50 MB upload limit

# yt-dlp exits 101 when --max-downloads is reached. With --max-downloads 1 that
# happens on every successful single-video download (the check runs after the
# file is downloaded and merged), so 101 is a success code here.
_OK_EXIT_CODES = (0, 101)


class DownloadError(RuntimeError):
    """RuntimeError whose str() carries yt-dlp detail for logs, plus a
    user_message that is safe to show to the client (no stderr, no paths)."""

    def __init__(self, user_message: str, detail: str = ""):
        super().__init__(f"{user_message} | {detail}" if detail else user_message)
        self.user_message = user_message


def yt_dlp_available() -> bool:
    return shutil.which("yt-dlp") is not None


def cleanup_download(path: Path) -> None:
    """Remove the whole per-job download dir that fetch_video() created.

    Removes the directory, not just the returned file, so any extra files yt-dlp
    left behind (playlist entries, partial fragments) are deleted too. Guarded
    on the mkdtemp prefix so a bad path can never rmtree an unrelated dir.
    """
    parent = Path(path).parent
    if parent.name.startswith(TMP_DIR_PREFIX):
        shutil.rmtree(parent, ignore_errors=True)
    else:
        Path(path).unlink(missing_ok=True)


def fetch_video(url: str) -> Path:
    """
    Downloads a YouTube or Instagram Reel URL to a temp .mp4 file.
    Returns the Path. Caller must call cleanup_download(path) after use
    (try/finally). Raises DownloadError (a RuntimeError) on failure; its
    user_message is client-safe, its str() is for logs only.
    """
    if not yt_dlp_available():
        raise RuntimeError("yt-dlp is not installed or not on PATH")

    tmp_dir = tempfile.mkdtemp(prefix=TMP_DIR_PREFIX)
    output_template = str(Path(tmp_dir) / "%(id)s.%(ext)s")

    cmd = [
        "yt-dlp",
        # Never read yt-dlp.conf / ~/.config/yt-dlp: a config file on the host
        # must not be able to add options (--exec, proxies, output paths).
        "--ignore-config",
        "--format", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "--merge-output-format", "mp4",
        # Belt and braces against playlist enumeration: the URL allow-list
        # already rejects list= params, and these cap what yt-dlp will fetch
        # even if a URL still resolves to a playlist.
        "--no-playlist",
        "--playlist-items", "1",
        "--max-downloads", "1",
        "--max-filesize", MAX_FILESIZE,
        "--output", output_template,
    ]

    # Optional cookie support for sites that require login (e.g. Instagram).
    # If YTDLP_COOKIES_FILE points at an existing file, pass it through.
    # Unset/missing env var keeps current behavior (works for public YouTube).
    cookies_file = os.environ.get("YTDLP_COOKIES_FILE")
    if cookies_file and Path(cookies_file).is_file():
        cmd += ["--cookies", cookies_file]

    # "--" ends option parsing so a URL can never be read as a yt-dlp flag.
    cmd += ["--", url]

    # On every failure path below (and on timeout) we must remove tmp_dir before
    # re-raising, otherwise each failed download leaks a temp directory. Only the
    # success path hands tmp_dir ownership to the caller (who cleans it up).
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    except subprocess.TimeoutExpired as exc:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        # Docstring promises RuntimeError; the caller catches only RuntimeError.
        raise DownloadError("Download timed out", "yt-dlp timed out after 300s") from exc

    stderr = (result.stderr or "").strip()

    # Inspect yt-dlp output for known failure signals BEFORE trusting file
    # existence. Instagram reels in particular fail with auth/login/private
    # messages that would otherwise surface as an opaque "no .mp4 found" error.
    combined_output = f"{result.stdout or ''}\n{stderr}"
    lowered = combined_output.lower()
    stderr_tail = stderr[-1500:]

    auth_signals = ("login required", "login", "private", "rate-limit", "rate limit")
    if any(signal in lowered for signal in auth_signals):
        shutil.rmtree(tmp_dir, ignore_errors=True)
        # Operator hint (YTDLP_COOKIES_FILE) goes to the log via str(), not
        # to the client.
        raise DownloadError(
            "Download failed — the video may be private, region-blocked, or require login",
            "set YTDLP_COOKIES_FILE to a cookies.txt path if login is needed; "
            f"yt-dlp stderr: {stderr_tail}",
        )

    if result.returncode not in _OK_EXIT_CODES or "ERROR" in combined_output:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise DownloadError(
            "Download failed",
            f"yt-dlp exit {result.returncode}: {stderr_tail}",
        )

    mp4_files = list(Path(tmp_dir).glob("*.mp4"))
    if len(mp4_files) != 1:
        # 0: nothing usable (e.g. skipped by --max-filesize). >1: yt-dlp
        # fetched more than the single video we asked for -- refuse it.
        shutil.rmtree(tmp_dir, ignore_errors=True)
        user_message = (
            f"Download failed — no usable video (it may exceed the {MAX_FILESIZE}B limit)"
            if not mp4_files
            else "Download failed"
        )
        raise DownloadError(
            user_message,
            f"expected exactly 1 .mp4, got {len(mp4_files)}; yt-dlp stderr: {stderr_tail}",
        )

    return mp4_files[0]
