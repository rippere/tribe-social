"""
Follow-up hardening of the video-URL -> yt-dlp path and the admin token check.

  * URL allow-list pins each accepted shape to an ID form that only the YouTube
    / Instagram yt-dlp extractors handle (never the Generic extractor, which
    follows redirects), rejects "%" and "list=" params, and normalizes
    scheme/host case and schemeless input before validating.
  * yt-dlp runs with --ignore-config and single-download / filesize caps, and
    the whole per-job download dir is removed afterwards.
  * yt-dlp stderr is logged, never returned to the client.
  * The admin token is compared in constant time.
"""
import logging
import types

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers import admin as admin_router
from app.routers import jobs as jobs_router
from app.services import downloader

MP4_BYTES = b"\x00" * 2048
VID = "abcdefghijk"  # YouTube IDs are exactly 11 chars


@pytest.fixture
def api(monkeypatch):
    submitted: list[tuple[str, bytes | None]] = []
    outbound: list[object] = []

    async def fake_submit(filename, video_bytes=None):
        submitted.append((filename, video_bytes))
        return "job-1"

    def fake_fetch(url):
        outbound.append(url)
        raise AssertionError(f"fetch_video must not be reached for {url!r}")

    def fake_run(cmd, *a, **kw):
        outbound.append(cmd)
        raise AssertionError(f"subprocess must not be reached: {cmd!r}")

    monkeypatch.setattr(jobs_router, "submit_job", fake_submit)
    monkeypatch.setattr(downloader, "fetch_video", fake_fetch)
    monkeypatch.setattr(downloader, "yt_dlp_available", lambda: True)
    monkeypatch.setattr(downloader.subprocess, "run", fake_run)

    app = FastAPI()
    app.include_router(jobs_router.router)
    client = TestClient(app)
    client.submitted = submitted
    client.outbound = outbound
    return client


# ---------------------------------------------------------------------------
# URL allow-list
# ---------------------------------------------------------------------------

REJECTED_URLS = [
    # Percent-encoded path traversal: YouTube resolves the decoded path, so
    # this reached an arbitrary youtube.com path (incl. its open redirect).
    "https://youtube.com/shorts/%2e%2e/redirect?q=x",
    f"https://youtube.com/shorts/{VID}%2f..",
    f"https://www.youtube.com/watch?v={VID}&x=%2e",
    # Shapes that fall through to yt-dlp's Generic extractor.
    "https://youtube.com/shorts/abcdefg",  # 7-char id
    "https://youtu.be/abcdefg",
    f"https://youtube.com/shorts/{VID}x",  # 12-char id
    f"https://youtube.com/shorts/{VID}/extra",
    f"https://youtu.be/{VID}/extra",
    f"https://youtube.com/shorts/{VID}//",
    # Instagram audio pages are not posts; yt-dlp sends them to Generic.
    "https://www.instagram.com/reel/audio/",
    "https://www.instagram.com/reels/audio/123456789/",
    "https://www.instagram.com/reels/audio?x=1",
    "https://www.instagram.com/someuser/extra/reel/Cabcdefg/",
    "https://www.instagram.com/some/user/reel/Cabcdefg/",
    f"https://youtube.com/watch?v={VID}?x=1",
    "https://youtube.com/watch?v=",
    # Non-ASCII "word" chars must not satisfy the id charset.
    "https://youtu.be/abcdefghij١",
    # Ports, extra hosts.
    f"https://youtube.com:443/shorts/{VID}",
    f"https://youtube.com.evil.example/shorts/{VID}",
    f"https://music.youtube.com.evil.example/watch?v={VID}",
    f"https://evil.example/https://youtu.be/{VID}",
    # Embedded newline / second URL.
    f"https://youtu.be/{VID}\nhttps://evil.example/",
    # Still https only.
    f"http://youtube.com/shorts/{VID}",
    f"HTTP://YOUTU.BE/{VID}",
    # Schemeless input gets https:// prepended and must still pass in full.
    f"evil.example/shorts/{VID}",
    f"--exec=id youtu.be/{VID}",
    f"//youtu.be/{VID}",
    "",
    "   ",
]

PLAYLIST_URLS = [
    # Empty v= plus list= made yt-dlp enumerate the whole playlist.
    "https://youtube.com/watch?v=&list=PLxxxxxxxxxxxxxxxx",
    f"https://www.youtube.com/watch?v={VID}&list=PLxxxxxxxxxxxxxxxx",
    f"https://www.youtube.com/watch?v={VID}&index=2&list=PLxxxxxxxxxxxxxxxx",
    f"https://youtu.be/{VID}?list=PLxxxxxxxxxxxxxxxx",
    f"https://youtube.com/shorts/{VID}?feature=share&list=PLxxxxxxxxxxxxxxxx",
    "https://www.youtube.com/playlist?list=PLxxxxxxxxxxxxxxxx",
]

# (input, normalized URL handed to yt-dlp, expected video id)
ACCEPTED_URLS = [
    (f"https://youtube.com/shorts/{VID}", f"https://youtube.com/shorts/{VID}", VID),
    (f"https://m.youtube.com/shorts/{VID}?feature=share", f"https://m.youtube.com/shorts/{VID}?feature=share", VID),
    (f"https://www.youtube.com/watch?v={VID}&t=10", f"https://www.youtube.com/watch?v={VID}&t=10", VID),
    # Newly accepted: dots in query values.
    (f"https://www.youtube.com/watch?v={VID}&t=1.5", f"https://www.youtube.com/watch?v={VID}&t=1.5", VID),
    (f"https://youtu.be/{VID}?t=1.5&feature=youtu.be", f"https://youtu.be/{VID}?t=1.5&feature=youtu.be", VID),
    (f"https://youtu.be/{VID}?si=xYz-_9AbC", f"https://youtu.be/{VID}?si=xYz-_9AbC", VID),
    # Newly accepted: music.youtube.com.
    (f"https://music.youtube.com/watch?v={VID}", f"https://music.youtube.com/watch?v={VID}", VID),
    # Newly accepted: case-insensitive scheme/host; id case preserved.
    ("HTTPS://WWW.YouTube.COM/shorts/AbCdEfGhIjK", "https://www.youtube.com/shorts/AbCdEfGhIjK", "AbCdEfGhIjK"),
    ("Https://YOUTU.BE/AbCdEfGhIjK", "https://youtu.be/AbCdEfGhIjK", "AbCdEfGhIjK"),
    # Newly accepted: schemeless input.
    (f"youtu.be/{VID}", f"https://youtu.be/{VID}", VID),
    (f"www.youtube.com/shorts/{VID}", f"https://www.youtube.com/shorts/{VID}", VID),
    ("instagram.com/reel/Cabcdefg/", "https://instagram.com/reel/Cabcdefg/", "Cabcdefg"),
    # Instagram, incl. base64 share tokens with "=" padding.
    ("https://www.instagram.com/reel/Cabcdefg/", "https://www.instagram.com/reel/Cabcdefg/", "Cabcdefg"),
    ("https://www.instagram.com/reel/Cabcdefg", "https://www.instagram.com/reel/Cabcdefg", "Cabcdefg"),
    ("https://www.instagram.com/reels/Cabcdefg/", "https://www.instagram.com/reels/Cabcdefg/", "Cabcdefg"),
    ("https://instagram.com/p/Cabcdefg/?igsh=xyz", "https://instagram.com/p/Cabcdefg/?igsh=xyz", "Cabcdefg"),
    (
        "https://www.instagram.com/p/C-abc_123/?igsh=MTc4MmM1YmI2Ng==",
        "https://www.instagram.com/p/C-abc_123/?igsh=MTc4MmM1YmI2Ng==",
        "C-abc_123",
    ),
    (
        "https://www.instagram.com/reel/Cabcdefg/?utm_source=ig_web_copy_link&igsh=bXk=",
        "https://www.instagram.com/reel/Cabcdefg/?utm_source=ig_web_copy_link&igsh=bXk=",
        "Cabcdefg",
    ),
    (f"  https://youtu.be/{VID}  ", f"https://youtu.be/{VID}", VID),
    # Trailing slash on Shorts, Instagram username prefix, dropped fragment.
    (f"https://youtube.com/shorts/{VID}/", f"https://youtube.com/shorts/{VID}/", VID),
    (f"https://youtube.com/shorts/{VID}/?feature=share", f"https://youtube.com/shorts/{VID}/?feature=share", VID),
    ("https://www.instagram.com/some.user_1/reel/Cabcdefg/", "https://www.instagram.com/some.user_1/reel/Cabcdefg/", "Cabcdefg"),
    ("https://www.instagram.com/someuser/p/Cabcdefg/?igsh=bXk=", "https://www.instagram.com/someuser/p/Cabcdefg/?igsh=bXk=", "Cabcdefg"),
    ("https://www.instagram.com/reel/audiobook1/", "https://www.instagram.com/reel/audiobook1/", "audiobook1"),
    (f"https://youtu.be/{VID}?t=10#x", f"https://youtu.be/{VID}?t=10", VID),
    (f"https://youtube.com/shorts/{VID}#frag", f"https://youtube.com/shorts/{VID}", VID),
]


@pytest.mark.parametrize("url", REJECTED_URLS)
def test_rejected_urls_never_reach_yt_dlp(api, monkeypatch, url):
    monkeypatch.setattr(jobs_router, "_INFER_ENABLED", True)
    r = api.post("/jobs", data={"video_url": url})
    assert r.status_code == 422, (url, r.status_code, r.text)
    assert api.outbound == []
    assert api.submitted == []


@pytest.mark.parametrize("url", PLAYLIST_URLS)
def test_playlist_urls_rejected(api, monkeypatch, url):
    monkeypatch.setattr(jobs_router, "_INFER_ENABLED", True)
    r = api.post("/jobs", data={"video_url": url})
    assert r.status_code == 422, (url, r.status_code, r.text)
    assert api.outbound == []
    assert api.submitted == []


@pytest.mark.parametrize("url", PLAYLIST_URLS)
def test_playlist_urls_get_playlist_message(url):
    with pytest.raises(jobs_router.InvalidVideoURL) as exc:
        jobs_router.normalize_video_url(url)
    assert exc.value.detail == jobs_router.PLAYLIST_URL_DETAIL


@pytest.mark.parametrize("raw, normalized, video_id", ACCEPTED_URLS)
def test_accepted_urls_normalize(raw, normalized, video_id):
    assert jobs_router.normalize_video_url(raw) == (normalized, video_id)


@pytest.mark.parametrize("raw, normalized, video_id", ACCEPTED_URLS)
def test_accepted_urls_queue_and_pass_normalized_url(api, monkeypatch, tmp_path, raw, normalized, video_id):
    monkeypatch.setattr(jobs_router, "_INFER_ENABLED", True)
    seen = []
    dl_dir = tmp_path / "tribe_dl_x"
    dl_dir.mkdir()

    def ok_fetch(url):
        seen.append(url)
        out = dl_dir / f"{video_id}.mp4"
        out.write_bytes(MP4_BYTES)
        return out

    monkeypatch.setattr(downloader, "fetch_video", ok_fetch)
    r = api.post("/jobs", data={"video_url": raw})
    assert r.status_code == 202, (raw, r.text)
    # yt-dlp gets exactly the string that was validated.
    assert seen == [normalized]
    assert api.submitted[0][0] == f"{video_id}.mp4"


@pytest.mark.parametrize("raw, normalized, video_id", ACCEPTED_URLS)
def test_accepted_urls_use_a_specific_extractor(raw, normalized, video_id):
    """Every accepted shape is claimed by a site extractor, never Generic."""
    extractor = pytest.importorskip("yt_dlp.extractor")
    claimed = [
        ie.ie_key()
        for ie in extractor.gen_extractor_classes()
        if ie.ie_key() != "Generic" and ie.suitable(normalized)
    ]
    assert claimed and claimed[0] in ("Youtube", "Instagram"), (normalized, claimed)


# ---------------------------------------------------------------------------
# Download error handling: no stderr to the client
# ---------------------------------------------------------------------------

SECRET = "SECRET-STDERR /tmp/tribe_dl_abc yt-dlp 2025.08.11 traceback"


@pytest.mark.parametrize(
    "exc, expected",
    [
        (
            downloader.DownloadError("Download failed", f"yt-dlp exit 1: {SECRET}"),
            "Download failed",
        ),
        (RuntimeError(SECRET), jobs_router.DOWNLOAD_FAILED_DETAIL),
    ],
)
def test_download_failure_hides_stderr_but_logs_it(api, monkeypatch, caplog, exc, expected):
    monkeypatch.setattr(jobs_router, "_INFER_ENABLED", True)

    def failing_fetch(url):
        raise exc

    monkeypatch.setattr(downloader, "fetch_video", failing_fetch)
    with caplog.at_level(logging.WARNING, logger=jobs_router.logger.name):
        r = api.post("/jobs", data={"video_url": f"https://youtu.be/{VID}"})
    assert r.status_code == 502
    assert r.json()["detail"] == expected
    assert "SECRET" not in r.text and "/tmp" not in r.text
    assert SECRET in caplog.text


def test_job_cleanup_removes_whole_download_dir(api, monkeypatch, tmp_path):
    """Extra files yt-dlp leaves behind (e.g. playlist entries) are removed too."""
    monkeypatch.setattr(jobs_router, "_INFER_ENABLED", True)
    dl_dir = tmp_path / "tribe_dl_job"
    dl_dir.mkdir()

    def fetch(url):
        for i in range(3):
            (dl_dir / f"extra{i}.mp4").write_bytes(MP4_BYTES)
        (dl_dir / "frag.part").write_bytes(b"x")
        out = dl_dir / f"{VID}.mp4"
        out.write_bytes(MP4_BYTES)
        return out

    monkeypatch.setattr(downloader, "fetch_video", fetch)
    r = api.post("/jobs", data={"video_url": f"https://youtu.be/{VID}"})
    assert r.status_code == 202, r.text
    assert not dl_dir.exists()


def test_job_cleanup_runs_on_too_small_download(api, monkeypatch, tmp_path):
    monkeypatch.setattr(jobs_router, "_INFER_ENABLED", True)
    dl_dir = tmp_path / "tribe_dl_small"
    dl_dir.mkdir()

    def fetch(url):
        out = dl_dir / f"{VID}.mp4"
        out.write_bytes(b"tiny")
        (dl_dir / "other.mp4").write_bytes(b"x")
        return out

    monkeypatch.setattr(downloader, "fetch_video", fetch)
    r = api.post("/jobs", data={"video_url": f"https://youtu.be/{VID}"})
    assert r.status_code == 502
    assert not dl_dir.exists()


def test_cleanup_download_refuses_unprefixed_dir(tmp_path):
    """The guard: never rmtree a directory fetch_video didn't create."""
    keep = tmp_path / "not_ours"
    keep.mkdir()
    sibling = keep / "keep.txt"
    sibling.write_text("x")
    target = keep / "v.mp4"
    target.write_bytes(MP4_BYTES)
    downloader.cleanup_download(target)
    assert not target.exists()
    assert sibling.exists()


# ---------------------------------------------------------------------------
# Downloader: yt-dlp argv and result handling
# ---------------------------------------------------------------------------


@pytest.fixture
def fake_ytdlp(monkeypatch, tmp_path):
    """Run fetch_video against a fake yt-dlp. Configure via the returned ns."""
    dl_dir = tmp_path / "tribe_dl_fake"
    dl_dir.mkdir()
    ns = types.SimpleNamespace(dir=dl_dir, cmd=None, files=["abc.mp4"], returncode=0, stderr="")

    def fake_run(cmd, *a, **kw):
        ns.cmd = list(cmd)
        for name in ns.files:
            (dl_dir / name).write_bytes(MP4_BYTES)
        return types.SimpleNamespace(returncode=ns.returncode, stdout="", stderr=ns.stderr)

    monkeypatch.setattr(downloader, "yt_dlp_available", lambda: True)
    monkeypatch.setattr(downloader.tempfile, "mkdtemp", lambda prefix="": str(dl_dir))
    monkeypatch.setattr(downloader.subprocess, "run", fake_run)
    monkeypatch.delenv("YTDLP_COOKIES_FILE", raising=False)
    return ns


def test_ytdlp_argv_is_hardened(fake_ytdlp):
    url = f"https://youtu.be/{VID}"
    downloader.fetch_video(url)
    cmd = fake_ytdlp.cmd

    def opt(flag):
        return cmd[cmd.index(flag) + 1]

    assert "--ignore-config" in cmd
    assert "--no-playlist" in cmd
    assert opt("--max-downloads") == "1"
    assert opt("--playlist-items") == "1"
    assert opt("--max-filesize") == "50M"
    # "--" is last-but-one and only appears once.
    assert cmd[-2:] == ["--", url]
    assert cmd.count("--") == 1


def test_exit_101_from_max_downloads_is_success(fake_ytdlp):
    # yt-dlp exits 101 once --max-downloads is reached, i.e. after every
    # successful single download.
    fake_ytdlp.returncode = 101
    out = downloader.fetch_video(f"https://youtu.be/{VID}")
    assert out == fake_ytdlp.dir / "abc.mp4"


def test_multiple_files_refused_and_dir_removed(fake_ytdlp):
    # Simulates a URL that still enumerated a playlist.
    fake_ytdlp.files = [f"v{i}.mp4" for i in range(13)]
    with pytest.raises(downloader.DownloadError):
        downloader.fetch_video(f"https://youtu.be/{VID}")
    assert not fake_ytdlp.dir.exists()


def test_no_file_from_filesize_cap_is_error(fake_ytdlp):
    fake_ytdlp.files = []
    with pytest.raises(downloader.DownloadError) as exc:
        downloader.fetch_video(f"https://youtu.be/{VID}")
    assert "50M" in exc.value.user_message
    assert not fake_ytdlp.dir.exists()


@pytest.mark.parametrize("stderr", ["ERROR: Private video. Sign in", "ERROR: something /tmp/x"])
def test_failure_user_message_has_no_stderr(fake_ytdlp, stderr):
    fake_ytdlp.files = []
    fake_ytdlp.returncode = 1
    fake_ytdlp.stderr = stderr
    with pytest.raises(downloader.DownloadError) as exc:
        downloader.fetch_video(f"https://youtu.be/{VID}")
    assert stderr not in exc.value.user_message
    assert "YTDLP_COOKIES_FILE" not in exc.value.user_message
    assert stderr in str(exc.value)  # still available for the server log
    assert not fake_ytdlp.dir.exists()


# ---------------------------------------------------------------------------
# Admin token
# ---------------------------------------------------------------------------


@pytest.fixture
def admin(monkeypatch):
    flushed = []
    monkeypatch.setattr(admin_router, "_ADMIN_TOKEN", "s3cret-token")
    monkeypatch.setattr(admin_router, "flush_to_disk", lambda: flushed.append(True))
    app = FastAPI()
    app.include_router(admin_router.router)
    client = TestClient(app)
    client.flushed = flushed
    return client


def test_admin_token_uses_constant_time_compare(admin, monkeypatch):
    calls = []
    real = admin_router.hmac.compare_digest

    def spy(a, b):
        calls.append((a, b))
        return real(a, b)

    monkeypatch.setattr(admin_router.hmac, "compare_digest", spy)
    r = admin.post("/admin/flush-corpus", headers={"X-Admin-Token": "s3cret-token"})
    assert r.status_code == 200, r.text
    assert admin.flushed == [True]
    assert calls == [(b"s3cret-token", b"s3cret-token")]


@pytest.mark.parametrize(
    "token",
    ["wrong", "s3cret-toke", "s3cret-token-", "", b"s3cret-token\xe9"],
)
def test_admin_wrong_token_401(admin, token):
    r = admin.post("/admin/flush-corpus", headers={"X-Admin-Token": token})
    assert r.status_code == 401, r.text
    assert admin.flushed == []


def test_admin_unset_token_always_401(admin, monkeypatch):
    monkeypatch.setattr(admin_router, "_ADMIN_TOKEN", "")
    r = admin.post("/admin/flush-corpus", headers={"X-Admin-Token": ""})
    assert r.status_code == 401
    assert admin.flushed == []
