"""
RunPod Serverless handler for TRIBE v2 inference.
Deployed as a Docker container to RunPod — NOT part of Railway.

Input (one of video_url / video_b64):
  {"input": {
      "video_url":  "<https URL the worker GETs the clip from>",   # trial path (no size cap)
      "video_b64":  "<base64 mp4>",                                # legacy path (/run caps ~10 MB)
      "filename":   "video.mp4",
      "activity_put_url": "<optional https URL; the uint8 cortex activity is PUT here>",
      "max_seconds": 75                                            # optional duration guard
  }}

Output: the quick_scores() flat dict, plus
  series      {roi: [per-second mean], ..., "gfp": [...]}  (raw TRIBE units)
  activity    {frames, vertices, hz, scale, uploaded}     (when activity_put_url is set)
  timings     {download_s, events_s, predict_s, model_load_s, cold_start}
RunPod wraps the return value in "output" itself, so the handler must NOT add its
own "output" key. Failures return {"error": "..."}; a "[fatal]" prefix marks an
input problem (bad or overlong video) that a retry would not fix.

Weights: on Serverless a network volume mounts at /runpod-volume. When it is
present every model cache (Hugging Face, torch hub, the uv cache behind
`uvx whisperx`) points there, so only the first worker ever downloads weights.
The per-video feature cache stays on the container disk and is wiped after each
job, so no uploaded content is kept on the shared volume.
"""
import base64
import os
import shutil
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

# RunPod's PyTorch base image sets HF_HUB_ENABLE_HF_TRANSFER=1, but hf_transfer
# isn't installed — whisperx (spawned by TRIBE v2 to transcribe the video's audio)
# inherits the flag and dies fetching the faster-whisper model. Force it off so the
# subprocess falls back to the standard HF downloader. Hard set (not setdefault):
# the base image already exports =1, so we must override it.
os.environ["HF_HUB_ENABLE_HF_TRANSFER"] = "0"

VOLUME = Path("/runpod-volume")
if VOLUME.is_dir():
    _c = VOLUME / "cache"
    os.environ["HF_HOME"] = str(_c / "huggingface")
    os.environ["TORCH_HOME"] = str(_c / "torch")
    os.environ["UV_CACHE_DIR"] = str(_c / "uv")
    os.environ["XDG_CACHE_HOME"] = str(_c / "xdg")
    # The volume is a different filesystem from the container disk; uv's default
    # hardlink mode would warn and fall back on every run.
    os.environ["UV_LINK_MODE"] = "copy"
    for _d in ("huggingface", "torch", "uv", "xdg"):
        (_c / _d).mkdir(parents=True, exist_ok=True)

# Per-video feature cache (TRIBE's exca cache). Local disk, cleared per job.
FEATURE_CACHE = Path("/tmp/tribe-feature-cache")

sys.path.insert(0, "/workspace")

import numpy as np  # noqa: E402
import runpod  # noqa: E402

N_VERTS = 20484
MAX_DOWNLOAD_BYTES = 60 * 1024 * 1024

_model = None
_model_load_s: float | None = None
_jobs_done = 0


def _get_model():
    global _model, _model_load_s
    if _model is None:
        from tribe_scoring.run_and_save import load_model
        t0 = time.time()
        print(f"[handler] Loading TRIBE v2 (HF_HOME={os.environ.get('HF_HOME', 'default')})", flush=True)
        _model = load_model(cache_folder=str(FEATURE_CACHE))
        _model_load_s = round(time.time() - t0, 1)
        print(f"[handler] TRIBE v2 model loaded in {_model_load_s}s", flush=True)
    return _model


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Signed URLs never redirect; following one could leave the signed origin."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        raise urllib.error.HTTPError(req.full_url, code, "redirect refused", headers, fp)


_opener = urllib.request.build_opener(_NoRedirect)
DOWNLOAD_DEADLINE_S = 180


def _require_https(url: str) -> None:
    if urllib.parse.urlsplit(url).scheme != "https":
        raise ValueError("[fatal] only https URLs are accepted")


def _download(url: str, dest: Path) -> None:
    _require_https(url)
    req = urllib.request.Request(url, headers={"User-Agent": "tribe-runpod-handler"})
    deadline = time.monotonic() + DOWNLOAD_DEADLINE_S
    with _opener.open(req, timeout=60) as resp, open(dest, "wb") as out:
        total = 0
        while True:
            if time.monotonic() > deadline:
                raise TimeoutError(f"video download exceeded {DOWNLOAD_DEADLINE_S} s")
            chunk = resp.read(1 << 20)
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_DOWNLOAD_BYTES:
                raise ValueError("[fatal] video is larger than 60 MB")
            out.write(chunk)


def _put(url: str, data: bytes) -> None:
    _require_https(url)
    req = urllib.request.Request(
        url, data=data, method="PUT",
        headers={"Content-Type": "application/octet-stream", "User-Agent": "tribe-runpod-handler"},
    )
    with _opener.open(req, timeout=120) as resp:
        if resp.status >= 300:
            raise RuntimeError(f"activity upload failed: HTTP {resp.status}")


def quantize(act: np.ndarray) -> tuple[np.ndarray, float]:
    """Signed -> uint8 around 128, scaled by the robust max |value|.
    Same encoding as research/export_cortex.py (the web CortexBrain reads it)."""
    scale = float(np.percentile(np.abs(act), 99.5)) or 1.0
    q = np.clip(np.round(128 + 127 * act / scale), 0, 255).astype(np.uint8)
    return q, scale


def per_second_series(preds: np.ndarray) -> dict[str, list[float]]:
    from tribe_scoring.run_and_save import _BATCH_MASKS
    out = {dim: [round(float(v), 6) for v in preds[:, idx].mean(axis=1)] for dim, idx in _BATCH_MASKS.items()}
    out["gfp"] = [round(float(v), 6) for v in np.sqrt((preds ** 2).mean(axis=1))]
    return out

# Linux NAME_MAX is 255 bytes; stay well under it so a long client filename
# can't make write_bytes()/unlink() raise.
_MAX_NAME_BYTES = 200


def _safe_filename(raw) -> str:
    """Client-supplied filename reduced to something safe to create in tmp_dir.

    Basename only (writes/unlinks stay in tmp_dir), NULs stripped, lone
    surrogates replaced, and truncated to _MAX_NAME_BYTES of UTF-8 while keeping
    a short extension -- otherwise open()/unlink() raise ValueError/OSError.
    """
    text = str(raw or "").replace("\x00", "")
    # Lone surrogates (valid in JSON "\ud800") can't be encoded to a path.
    text = text.encode("utf-8", "replace").decode("utf-8")
    name = Path(text).name
    if len(name.encode("utf-8")) > _MAX_NAME_BYTES:
        suffix = Path(name).suffix
        if len(suffix.encode("utf-8")) > 16:
            suffix = ""
        stem = name[: len(name) - len(suffix)] if suffix else name
        budget = _MAX_NAME_BYTES - len(suffix.encode("utf-8"))
        stem = stem.encode("utf-8")[:budget].decode("utf-8", "ignore")
        name = stem + suffix
    if name in ("", ".", ".."):
        return "video.mp4"
    return name


def handler(event: dict) -> dict:
    global _jobs_done
    inp = event.get("input", {}) or {}
    video_url = inp.get("video_url")
    video_b64 = inp.get("video_b64")
    filename = _safe_filename(inp.get("filename") or "video.mp4")
    put_url = inp.get("activity_put_url")
    max_seconds = int(inp.get("max_seconds") or 0)

    if not video_url and not video_b64:
        return {"error": "[fatal] Missing video_url or video_b64 in input"}
    if Path(filename).suffix.lower() not in (".mp4", ".mov"):
        filename = Path(filename).stem + ".mp4"

    cold = _jobs_done == 0
    timings: dict = {"cold_start": cold}
    tmp_dir = Path(tempfile.mkdtemp())
    video_path = tmp_dir / filename
    try:
        t0 = time.time()
        if video_url:
            _download(video_url, video_path)
        else:
            try:
                video_bytes = base64.b64decode(video_b64)
            except (ValueError, TypeError):
                return {"error": "[fatal] Invalid video data: video_b64 is not valid base64"}
            video_path.write_bytes(video_bytes)
        if video_path.stat().st_size < 1024:
            return {"error": "[fatal] Invalid video data: payload too small or corrupted"}
        timings["download_s"] = round(time.time() - t0, 2)

        model = _get_model()
        timings["model_load_s"] = _model_load_s
        from tribe_scoring.run_and_save import quick_scores

        t0 = time.time()
        events_df = model.get_events_dataframe(video_path=str(video_path))
        timings["events_s"] = round(time.time() - t0, 1)
        t0 = time.time()
        preds, _ = model.predict(events=events_df)
        timings["predict_s"] = round(time.time() - t0, 1)
        preds = np.asarray(preds, dtype=np.float32)
        if preds.ndim != 2 or preds.shape[1] != N_VERTS:
            return {"error": f"unexpected prediction shape {preds.shape}"}
        if max_seconds and preds.shape[0] > max_seconds:
            return {"error": f"[fatal] clip is {preds.shape[0]} s; the limit is {max_seconds} s"}

        row = quick_scores(preds)
        row["filename"] = filename
        row["label"] = Path(filename).stem
        row["n_seconds"] = int(preds.shape[0])
        row["series"] = per_second_series(preds)

        if put_url:
            q, scale = quantize(preds)
            _put(put_url, q.tobytes())
            row["activity"] = {"frames": int(q.shape[0]), "vertices": N_VERTS, "hz": 1,
                               "scale": round(scale, 6), "uploaded": True}
        row["timings"] = timings
        return row
    except Exception as exc:  # noqa: BLE001 — surfaced to the dispatcher as the job error
        return {"error": str(exc)[:2000]}
    finally:
        _jobs_done += 1
        shutil.rmtree(tmp_dir, ignore_errors=True)
        # Drop this clip's cached features (anything derived from the upload), but
        # keep the folder itself: the loaded model was configured with its path.
        if FEATURE_CACHE.is_dir():
            for child in FEATURE_CACHE.iterdir():
                if child.is_dir():
                    shutil.rmtree(child, ignore_errors=True)
                else:
                    child.unlink(missing_ok=True)


if __name__ == "__main__":
    # Load the weights before taking jobs: a warm worker then serves every queued
    # clip without reloading, and the load shows up in the job's delayTime.
    if os.environ.get("TRIBE_EAGER_LOAD", "1") == "1":
        try:
            _get_model()
        except Exception as exc:  # noqa: BLE001 — retried lazily on the first job
            print(f"[handler] eager model load failed: {exc}", flush=True)
    runpod.serverless.start({"handler": handler})
