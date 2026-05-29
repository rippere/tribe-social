"""
Warm TRIBE v2 inference server — runs on a PERSISTENT RunPod GPU pod (A100 80GB).

Loads the model ONCE at startup and keeps it warm in VRAM. Scoring is ASYNC:
POST /score returns a job_id immediately (inference runs in a background thread),
and GET /result/{job_id} is polled for the outcome. This keeps every HTTP request
well under RunPod's ~100s proxy (Cloudflare 524) timeout, even though a full
score takes a couple of minutes.
"""
import base64
import os
import tempfile
import threading
import time
import uuid
from pathlib import Path

os.environ.setdefault("HF_HUB_DOWNLOAD_TIMEOUT", "300")
os.environ["HF_HUB_ENABLE_HF_TRANSFER"] = "0"

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from tribe_scoring.run_and_save import load_model, quick_scores

CACHE_FOLDER = os.environ.get("TRIBE_CACHE", "/workspace/cache")

app = FastAPI(title="TRIBE v2 Warm Inference")
_model = None
_jobs: dict[str, dict] = {}        # job_id -> {status, output|error, started}
_jobs_lock = threading.Lock()


@app.on_event("startup")
def _warm_load():
    global _model
    t0 = time.time()
    print(f"[pod_server] Loading TRIBE v2 from cache={CACHE_FOLDER} ...", flush=True)
    _model = load_model(cache_folder=CACHE_FOLDER)
    print(f"[pod_server] Model warm in {time.time() - t0:.1f}s", flush=True)


class ScoreRequest(BaseModel):
    video_b64: str
    filename: str = "video.mp4"


@app.get("/health")
def health():
    return {"status": "ok", "model_loaded": _model is not None}


def _run_inference(job_id: str, video_bytes: bytes, filename: str):
    tmp_dir = tempfile.mkdtemp()
    video_path = Path(tmp_dir) / filename
    try:
        video_path.write_bytes(video_bytes)
        t0 = time.time()
        # Stage 1: transcription + multimodal feature extraction (WhisperX etc.)
        events_df = _model.get_events_dataframe(video_path=str(video_path))
        t_features = time.time() - t0
        # Stage 2: the fMRI prediction itself
        t1 = time.time()
        preds, _ = _model.predict(events=events_df)
        t_predict = time.time() - t1
        row = quick_scores(preds)
        row["filename"] = filename
        row["label"] = Path(filename).stem
        row["n_seconds"] = int(preds.shape[0])
        dur = time.time() - t0
        timing = {"features_s": round(t_features, 1), "predict_s": round(t_predict, 1),
                  "total_s": round(dur, 1)}
        print(f"[pod_server] scored {filename}: features={t_features:.1f}s "
              f"predict={t_predict:.1f}s total={dur:.1f}s ({preds.shape[0]}s clip)", flush=True)
        with _jobs_lock:
            _jobs[job_id] = {"status": "complete", "output": row,
                             "elapsed_s": round(dur, 1), "timing": timing}
    except Exception as exc:
        print(f"[pod_server] scoring FAILED for {filename}: {exc}", flush=True)
        with _jobs_lock:
            _jobs[job_id] = {"status": "failed", "error": str(exc)}
    finally:
        video_path.unlink(missing_ok=True)
        try:
            Path(tmp_dir).rmdir()
        except OSError:
            pass


@app.post("/score")
def score(req: ScoreRequest):
    if _model is None:
        raise HTTPException(503, "Model not loaded yet")
    video_bytes = base64.b64decode(req.video_b64)
    if len(video_bytes) < 1024:
        raise HTTPException(422, "Invalid video data — payload too small or corrupted")

    job_id = str(uuid.uuid4())
    with _jobs_lock:
        _jobs[job_id] = {"status": "processing", "started": time.time()}
    threading.Thread(
        target=_run_inference, args=(job_id, video_bytes, req.filename), daemon=True
    ).start()
    return {"job_id": job_id, "status": "processing"}


@app.get("/result/{job_id}")
def result(job_id: str):
    with _jobs_lock:
        j = _jobs.get(job_id)
    if j is None:
        raise HTTPException(404, "Unknown job_id")
    return j
