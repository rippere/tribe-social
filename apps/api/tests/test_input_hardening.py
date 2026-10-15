"""
Security regression tests for client-controlled input on the scoring path.

Covers three findings fixed together:
  F3  client filename path traversal (API upload, pod_server, runpod_handler):
      a filename like "../x.mp4" must be reduced to its basename so the video is
      written to, and unlinked from, the per-job tmp_dir only.
  F4  unanchored VIDEO_URL_PATTERN.search() let non-https / loopback URLs and
      leading-dash values ("--opt=...youtube.com/shorts/x") through to yt-dlp
      (SSRF + option injection). The pattern is now an anchored https allow-list
      matched with fullmatch(), and yt-dlp gets "--" before the URL.
  F5  CORS allow_origins=["*"] combined with allow_credentials=True.
"""
import importlib.util
import sys
import types
from pathlib import Path

import numpy as np
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers import jobs as jobs_router
from app.services import downloader

REPO_ROOT = Path(__file__).resolve().parents[3]

MP4_BYTES = b"\x00" * 2048


# ---------------------------------------------------------------------------
# API: /jobs
# ---------------------------------------------------------------------------


@pytest.fixture
def api(monkeypatch):
    """A client over the jobs router with submit_job and all outbound I/O stubbed."""
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


@pytest.mark.parametrize(
    "raw",
    ["../x.mp4", "../../etc/x.mp4", "/tmp/evil/x.mp4", "a/b/../../x.mp4"],
)
def test_upload_filename_is_reduced_to_basename(api, raw):
    r = api.post("/jobs", files={"file": (raw, MP4_BYTES, "video/mp4")})
    assert r.status_code == 202, r.text
    (filename, _), = api.submitted
    assert filename == "x.mp4"
    assert "/" not in filename and ".." not in filename


def test_upload_non_mp4_still_rejected(api):
    r = api.post("/jobs", files={"file": ("x.mp4/../evil.sh", MP4_BYTES, "video/mp4")})
    assert r.status_code == 422
    assert api.submitted == []


@pytest.mark.parametrize(
    "url",
    [
        # yt-dlp option injection: leading dash, pattern text further on.
        "--opt=https://youtube.com/shorts/abcdefg",
        "--exec=touch /tmp/pwned;youtube.com/shorts/abcdefg",
        "-o/tmp/x youtube.com/shorts/abcdefg",
        # SSRF: loopback / internal hosts with the pattern in path or query.
        "http://127.0.0.1/youtube.com/shorts/abcdefg",
        "https://127.0.0.1/?youtube.com/shorts/abcdefg",
        "http://localhost:8000/youtube.com/shorts/abcdefg",
        "https://169.254.169.254/latest/meta-data/?x=youtube.com/shorts/abc",
        "https://[::1]/youtube.com/shorts/abcdefg",
        # Host confusion.
        "https://youtube.com.evil.example/shorts/abcdefg",
        "https://youtube.com@127.0.0.1/shorts/abcdefg",
        "https://evil.example/#youtube.com/shorts/abcdefg",
        # Non-https schemes.
        "http://youtube.com/shorts/abcdefg",
        "file:///etc/passwd#youtube.com/shorts/abcdefg",
        # Trailing junk after a valid URL.
        "https://youtube.com/shorts/abcdefg --exec=id",
    ],
)
def test_bad_urls_rejected_with_no_outbound_hit(api, monkeypatch, url):
    # Inference enabled, so a URL that passed validation WOULD reach yt-dlp.
    monkeypatch.setattr(jobs_router, "_INFER_ENABLED", True)
    r = api.post("/jobs", data={"video_url": url})
    assert r.status_code == 422, (url, r.status_code, r.text)
    assert api.outbound == []
    assert api.submitted == []


@pytest.mark.parametrize(
    "url",
    [
        "https://youtube.com/shorts/abcdefg",
        "https://www.youtube.com/shorts/abcdefg",
        "https://m.youtube.com/watch?v=abcdefghijk",
        "https://www.youtube.com/watch?v=abcdefghijk&t=10",
        "https://youtu.be/abcdefghijk",
        "https://www.instagram.com/reel/Cabcdefg/",
        "https://instagram.com/p/Cabcdefg/?igsh=xyz",
        "  https://youtu.be/abcdefghijk  ",
    ],
)
def test_valid_urls_still_accepted(api, url):
    # _INFER_ENABLED is False in the test env: no download, just queued.
    r = api.post("/jobs", data={"video_url": url})
    assert r.status_code == 202, (url, r.text)
    assert api.outbound == []
    assert len(api.submitted) == 1


def test_valid_url_reaches_downloader_when_inference_enabled(api, monkeypatch, tmp_path):
    monkeypatch.setattr(jobs_router, "_INFER_ENABLED", True)
    seen = []
    out = tmp_path / "dl" / "abcdefg.mp4"
    out.parent.mkdir()
    out.write_bytes(MP4_BYTES)

    def ok_fetch(url):
        seen.append(url)
        return out

    monkeypatch.setattr(downloader, "fetch_video", ok_fetch)
    r = api.post("/jobs", data={"video_url": "https://youtube.com/shorts/abcdefg"})
    assert r.status_code == 202, r.text
    assert seen == ["https://youtube.com/shorts/abcdefg"]


def test_downloader_puts_double_dash_before_url(monkeypatch, tmp_path):
    captured = {}
    dl_dir = tmp_path / "dl"
    dl_dir.mkdir()

    def fake_run(cmd, *a, **kw):
        captured["cmd"] = list(cmd)
        (dl_dir / "abc.mp4").write_bytes(MP4_BYTES)
        return types.SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(downloader, "yt_dlp_available", lambda: True)
    monkeypatch.setattr(downloader.tempfile, "mkdtemp", lambda prefix="": str(dl_dir))
    monkeypatch.setattr(downloader.subprocess, "run", fake_run)
    monkeypatch.delenv("YTDLP_COOKIES_FILE", raising=False)

    downloader.fetch_video("https://youtu.be/abcdefghijk")
    cmd = captured["cmd"]
    assert cmd[-2:] == ["--", "https://youtu.be/abcdefghijk"]
    assert cmd.count("--") == 1


# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------


def test_cors_wildcard_does_not_allow_credentials():
    from app.main import app

    client = TestClient(app)
    r = client.options(
        "/health",
        headers={
            "Origin": "https://evil.example",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert r.headers.get("access-control-allow-credentials") is None
    r = client.get("/health", headers={"Origin": "https://evil.example"})
    assert r.headers.get("access-control-allow-credentials") is None


# ---------------------------------------------------------------------------
# GPU side: pod_server + runpod_handler (loaded with heavy deps stubbed)
# ---------------------------------------------------------------------------


class _FakeModel:
    def __init__(self):
        self.video_paths: list[Path] = []

    def get_events_dataframe(self, video_path):
        p = Path(video_path)
        assert p.is_file(), f"video not written at {p}"
        self.video_paths.append(p)
        return object()

    def predict(self, events):
        return np.zeros((3, 4)), None


def _stub_scoring(monkeypatch):
    pkg = types.ModuleType("tribe_scoring")
    mod = types.ModuleType("tribe_scoring.run_and_save")
    mod.load_model = lambda cache_folder=None: _FakeModel()
    mod.quick_scores = lambda preds: {}
    pkg.run_and_save = mod
    monkeypatch.setitem(sys.modules, "tribe_scoring", pkg)
    monkeypatch.setitem(sys.modules, "tribe_scoring.run_and_save", mod)
    runpod = types.ModuleType("runpod")
    runpod.serverless = types.SimpleNamespace(start=lambda *_a, **_k: None)
    monkeypatch.setitem(sys.modules, "runpod", runpod)


def _load(monkeypatch, rel: str, name: str):
    _stub_scoring(monkeypatch)
    spec = importlib.util.spec_from_file_location(name, REPO_ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    """tmp_dir handed out by mkdtemp, nested so '..' has somewhere to escape to."""
    job_dir = tmp_path / "outer" / "job"
    job_dir.mkdir(parents=True)
    monkeypatch.setattr("tempfile.mkdtemp", lambda *a, **k: str(job_dir))
    return job_dir


TRAVERSAL_NAMES = ["../x.mp4", "../../x.mp4", "/tmp/x.mp4", "..", ""]


@pytest.mark.parametrize("raw", TRAVERSAL_NAMES)
def test_pod_server_write_stays_in_tmp_dir(monkeypatch, sandbox, raw):
    server = _load(monkeypatch, "apps/pod_server/server.py", "_pod_server_under_test")
    model = _FakeModel()
    monkeypatch.setattr(server, "_model", model)

    server._run_inference("j1", MP4_BYTES, raw)

    job = server._jobs["j1"]
    assert job["status"] == "complete", job
    (written,) = model.video_paths
    assert written.parent == sandbox
    assert job["output"]["filename"] == written.name
    # Nothing landed outside the job dir, and the job dir was cleaned up.
    assert not (sandbox.parent / "x.mp4").exists()
    assert not (sandbox.parent.parent / "x.mp4").exists()
    assert not sandbox.exists()


@pytest.mark.parametrize("raw", TRAVERSAL_NAMES)
def test_runpod_handler_write_stays_in_tmp_dir(monkeypatch, sandbox, raw):
    import base64

    handler = _load(monkeypatch, "apps/runpod_handler/handler.py", "_rp_handler_under_test")
    model = _FakeModel()
    monkeypatch.setattr(handler, "_model", model)

    out = handler.handler(
        {"input": {"video_b64": base64.b64encode(MP4_BYTES).decode(), "filename": raw}}
    )

    assert "error" not in out, out
    (written,) = model.video_paths
    assert written.parent == sandbox
    assert out["filename"] == written.name
    assert not (sandbox.parent / "x.mp4").exists()
    assert not (sandbox.parent.parent / "x.mp4").exists()
    assert not sandbox.exists()
