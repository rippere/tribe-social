"""
Mock inference service — Phase 2 (no RunPod, deterministic fake scores).
Phase 3 will swap _mock_process for real RunPod submission.
"""
import asyncio
import base64
import hashlib
import os
from datetime import datetime
from uuid import uuid4

import httpx
import numpy as np

from app.models.job import Job, JobStatus, ScoreResult
from tribe_scoring.composite import scale_to_100, compute_verdict
from app.services.scoring import get_revision_tips, generate_temporal_data
from app.store import jobs as job_store

_REAL_MODE = bool(os.getenv("RUNPOD_API_KEY") and os.getenv("RUNPOD_ENDPOINT_ID"))

# Persistent warm-pod inference server (preferred over serverless when set).
# e.g. https://<podId>-8000.proxy.runpod.net
_POD_URL = os.getenv("POD_URL", "").rstrip("/")

# Shared secret for the warm-pod endpoint (must match POD_KEY on the pod server).
# When set, sent as the X-Pod-Key header on /score and /result calls.
_POD_KEY = os.getenv("POD_KEY", "")

# Real inference is available via either the warm pod or the serverless endpoint.
# The router uses this to decide whether to download/read the video.
_INFER_ENABLED = bool(_POD_URL) or _REAL_MODE

# Reference count of active RunPod jobs. enable_endpoint fires on 0→1 transition;
# disable_endpoint fires on 1→0 transition, so concurrent jobs share one active endpoint.
_active_runpod_jobs: int = 0
_active_runpod_lock: asyncio.Lock = asyncio.Lock()

# Hold strong references to background scoring tasks. asyncio.create_task keeps
# only a weak reference, so without this a task can be garbage-collected mid-run.
# Each task discards itself from the set once done.
_background_tasks: set[asyncio.Task] = set()


def _spawn(coro) -> asyncio.Task:
    task = asyncio.create_task(coro)
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
    return task

MOCK_STAGES = [
    (10, "uploading",   "Uploading video..."),
    (30, "scoring",     "Running TRIBE v2 inference..."),
    (60, "scoring",     "Encoding brain activations..."),
    (85, "downloading", "Extracting ROI signals..."),
    (95, "analyzing",   "Computing composite score..."),
]


def _seed_from_name(name: str) -> int:
    return int(hashlib.md5(name.encode()).hexdigest()[:8], 16)


def _composite_from_raw(output: dict) -> float:
    """The ONE composite: scale the pod's composite_raw (tribe_scoring) onto the
    corpus's 0-100 scale. Fails LOUD if the corpus range is unavailable rather
    than emitting a plausible-looking wrong score — with a 0-1 fallback a missing
    corpus.json would silently grade every clip ~2/100 (RETHINK)."""
    raw = output.get("composite_raw")
    if raw is None:
        raise RuntimeError("scorer output missing 'composite_raw'")
    from app import state
    stats = (state.corpus_data or {}).get("stats", {})
    lo, hi = stats.get("composite_raw_min"), stats.get("composite_raw_max")
    if lo is None or hi is None:
        raise RuntimeError(
            "corpus composite_raw range unavailable (corpus.json not loaded) — "
            "refusing to emit an unscaled/garbage composite score"
        )
    return scale_to_100(float(raw), float(lo), float(hi))


async def submit_job(filename: str, video_bytes: bytes | None = None) -> str:
    job_id = str(uuid4())
    job = Job(
        job_id=job_id,
        status=JobStatus.queued,
        progress_pct=0,
        message="Queued",
        created_at=datetime.utcnow(),
    )
    job_store.set(job)

    if _POD_URL and video_bytes is not None:
        _spawn(pod_process_job(job_id, filename, video_bytes))
    elif _REAL_MODE and video_bytes is not None:
        _spawn(real_process_job(job_id, filename, video_bytes))
    else:
        _spawn(_mock_process(job_id, filename))

    return job_id


async def pod_process_job(job_id: str, filename: str, video_bytes: bytes):
    """Real inference via the persistent warm-pod server (POD_URL).

    Submits to POST /score, polls GET /result/{id}. The pod keeps the model warm,
    so there's no cold-start download; a score takes ~9 min currently.
    """
    POLL_S = 5
    TIMEOUT_S = 1200   # warm-pod score observed ~530s; headroom for longer clips
    try:
        job_store.update(job_id, status="uploading", progress_pct=8, message="Uploading to GPU pod...")
        video_b64 = base64.b64encode(video_bytes).decode()
        pod_headers = {"X-Pod-Key": _POD_KEY} if _POD_KEY else {}

        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(f"{_POD_URL}/score", json={"video_b64": video_b64, "filename": filename},
                                  headers=pod_headers)
            r.raise_for_status()
            pod_job_id = r.json().get("job_id")
            if not pod_job_id:
                raise RuntimeError(f"Pod /score returned no job_id: {r.text}")
            job_store.update(job_id, runpod_job_id=pod_job_id)

            loop = asyncio.get_running_loop()
            start = loop.time()
            result = None
            while True:
                elapsed = loop.time() - start
                if elapsed > TIMEOUT_S:
                    raise TimeoutError(f"Pod job timed out after {TIMEOUT_S}s")
                pct = min(95, 15 + int((elapsed / 540) * 80))
                job_store.update(job_id, status="scoring", progress_pct=pct,
                                 message="Running TRIBE v2 inference on GPU pod...")
                rr = await client.get(f"{_POD_URL}/result/{pod_job_id}", headers=pod_headers)
                rr.raise_for_status()
                data = rr.json()
                st = data.get("status")
                if st == "complete":
                    result = data.get("output", {})
                    break
                if st == "failed":
                    raise RuntimeError(data.get("error", "Pod inference failed"))
                await asyncio.sleep(POLL_S)

        roi_raw   = _map_runpod_output_to_roi(result)
        composite = _composite_from_raw(result)
        verdict   = compute_verdict(composite)
        tips      = get_revision_tips(roi_raw)
        seed      = _seed_from_name(filename)
        temporal  = generate_temporal_data(
            vmPFC=roi_raw["vmPFC"], TPJ=roi_raw["TPJ"], IFJa=roi_raw["IFJa"],
            hook_attn=min(roi_raw["IFJa"] + 0.1, 1.0), seed=seed,
        )
        from app import state
        corpus_roi_means: dict[str, float] = {}
        if state.corpus_data:
            corpus_roi_means = state.corpus_data["stats"]["roi_means"]

        score_result = ScoreResult(
            video_id=f"upload_{job_id[:8]}",
            composite_score=round(composite, 1),
            verdict=verdict,
            roi=roi_raw,
            corpus_roi_means=corpus_roi_means,
            weak_rois=[r for r, v in roi_raw.items() if v < 0.45 and r != "IFJp"],
            revision_tips=tips,
            temporal=temporal,
        )
        job_store.update(job_id, status=JobStatus.complete, progress_pct=100,
                         message="Complete", result=score_result)

        from app.services.corpus_writer import add_video_to_corpus
        add_video_to_corpus(job_id, filename, roi_raw, round(composite, 1))

    except Exception as exc:
        job_store.update(job_id, status=JobStatus.failed, progress_pct=0,
                         message="Failed", error=str(exc))


async def _mock_process(job_id: str, filename: str):
    seed = _seed_from_name(filename)
    rng = np.random.default_rng(seed)

    for pct, status, msg in MOCK_STAGES:
        await asyncio.sleep(1.2)
        job_store.update(job_id, status=status, progress_pct=pct, message=msg)

    # Generate deterministic ROI scores (short-name keys)
    roi_raw = {
        "vmPFC":   float(rng.uniform(0.25, 0.90)),
        "TPJ":     float(rng.uniform(0.25, 0.90)),
        "IFJa":    float(rng.uniform(0.20, 0.85)),
        "IFJp":    float(rng.uniform(0.20, 0.85)),
        "area_45": float(rng.uniform(0.15, 0.80)),
        "MT_V5":   float(rng.uniform(0.15, 0.75)),
    }

    composite = round(float(rng.uniform(20, 90)), 1)  # mock: deterministic fake score
    verdict = compute_verdict(composite)
    tips = get_revision_tips(roi_raw)
    temporal = generate_temporal_data(
        vmPFC=roi_raw["vmPFC"],
        TPJ=roi_raw["TPJ"],
        IFJa=roi_raw["IFJa"],
        hook_attn=min(roi_raw["IFJa"] + 0.1, 1.0),
        seed=seed,
    )

    # Load corpus roi_means from state (loaded at startup)
    from app import state
    corpus_roi_means: dict[str, float] = {}
    if state.corpus_data:
        corpus_roi_means = state.corpus_data["stats"]["roi_means"]

    result = ScoreResult(
        video_id=f"upload_{job_id[:8]}",
        composite_score=round(composite, 1),
        verdict=verdict,
        roi=roi_raw,
        corpus_roi_means=corpus_roi_means,
        weak_rois=[r for r, v in roi_raw.items() if v < 0.45 and r != "IFJp"],
        revision_tips=tips,
        temporal=temporal,
    )

    job_store.update(
        job_id,
        status=JobStatus.complete,
        progress_pct=100,
        message="Complete",
        result=result,
    )


async def real_process_job(job_id: str, filename: str, video_bytes: bytes):
    """Real inference path via RunPod Serverless."""
    global _active_runpod_jobs
    from app.services.runpod_client import submit, check_status, enable_endpoint, disable_endpoint

    try:
        job_store.update(job_id, status="uploading", progress_pct=5, message="Activating GPU endpoint...")
        async with _active_runpod_lock:
            _active_runpod_jobs += 1
            if _active_runpod_jobs == 1:
                await enable_endpoint()

        job_store.update(job_id, status="uploading", progress_pct=10, message="Uploading to RunPod...")
        runpod_job_id = await submit(video_bytes, filename)
        job_store.update(job_id, runpod_job_id=runpod_job_id)

        loop = asyncio.get_running_loop()
        submit_time = loop.time()
        EXPECTED_S = 900   # cold start re-downloads ~30GB (observed ~560s delayTime) + inference
        TIMEOUT_S  = 1800  # 30 min: a fresh worker must download ~30GB before inference can run.
                           # Once a model-cache network volume is attached this can drop back to ~600s.

        result_data = None
        try:
            while True:
                elapsed = loop.time() - submit_time
                if elapsed > TIMEOUT_S:
                    raise TimeoutError(f"RunPod job timed out after {TIMEOUT_S}s")

                pct = min(95, 20 + int((elapsed / EXPECTED_S) * 75))
                data = await check_status(runpod_job_id)
                runpod_status = data.get("status", "")

                if runpod_status == "IN_QUEUE":
                    msg = "Waiting for GPU worker..."
                elif runpod_status == "IN_PROGRESS":
                    if pct < 40:
                        msg = "GPU pod warming up..."
                    elif pct < 60:
                        msg = "Running TRIBE v2 inference..."
                    elif pct < 75:
                        msg = "Encoding brain activations..."
                    else:
                        msg = "Extracting ROI signals..."
                else:
                    msg = "Processing..."

                job_store.update(job_id, status="scoring", progress_pct=pct, message=msg)

                if runpod_status == "COMPLETED":
                    result_data = {"status": "COMPLETED", "output": data.get("output", {})}
                    break
                if runpod_status in ("FAILED", "CANCELLED"):
                    result_data = {"status": runpod_status, "error": data.get("error", "RunPod job failed")}
                    break

                await asyncio.sleep(5)
        finally:
            async with _active_runpod_lock:
                _active_runpod_jobs -= 1
                if _active_runpod_jobs == 0:
                    # Teardown must never mask the real job error propagating out of the
                    # try block — a failed disable_endpoint() in finally would replace the
                    # actual failure reason the user sees. Log it and move on.
                    try:
                        await disable_endpoint()
                    except Exception as disable_exc:
                        print(f"[inference] disable_endpoint failed for job {job_id}: {disable_exc}")

        if result_data is None:
            raise RuntimeError("RunPod polling exited without a terminal status")
        if result_data["status"] != "COMPLETED":
            raise RuntimeError(result_data.get("error", "RunPod job failed"))

        output    = result_data["output"]
        roi_raw   = _map_runpod_output_to_roi(output)
        composite = _composite_from_raw(output)
        verdict   = compute_verdict(composite)
        tips      = get_revision_tips(roi_raw)
        seed      = _seed_from_name(filename)
        temporal  = generate_temporal_data(
            vmPFC=roi_raw["vmPFC"],
            TPJ=roi_raw["TPJ"],
            IFJa=roi_raw["IFJa"],
            hook_attn=min(roi_raw["IFJa"] + 0.1, 1.0),
            seed=seed,
        )

        from app import state
        corpus_roi_means: dict[str, float] = {}
        if state.corpus_data:
            corpus_roi_means = state.corpus_data["stats"]["roi_means"]

        score_result = ScoreResult(
            video_id=f"upload_{job_id[:8]}",
            composite_score=round(composite, 1),
            verdict=verdict,
            roi=roi_raw,
            corpus_roi_means=corpus_roi_means,
            weak_rois=[r for r, v in roi_raw.items() if v < 0.45 and r != "IFJp"],
            revision_tips=tips,
            temporal=temporal,
        )

        job_store.update(
            job_id,
            status=JobStatus.complete,
            progress_pct=100,
            message="Complete",
            result=score_result,
        )

        from app.services.corpus_writer import add_video_to_corpus
        add_video_to_corpus(job_id, filename, roi_raw, round(composite, 1))

    except Exception as exc:
        job_store.update(
            job_id,
            status=JobStatus.failed,
            progress_pct=0,
            message="Failed",
            error=str(exc),
        )



def _map_runpod_output_to_roi(output: dict) -> dict[str, float]:
    """
    Map RunPod handler output (run_and_save.py quick_scores() keys) to app ROI dict.
    Raw values are signed floats near 0; normalize to 0-1 using (val + 0.5) / 2.0.
    Calibrate this formula once real outputs are available.
    """
    expected_keys = {
        "valuation_mean", "social_mean", "attention_mean", "language_mean", "motion_mean",
    }
    missing = expected_keys - output.keys()
    if missing:
        raise RuntimeError(f"RunPod output missing expected keys: {sorted(missing)}")

    def _get(key: str) -> float:
        val = output.get(key, 0.5)
        return float(max(0.0, min(1.0, (val + 0.5) / 2.0)))

    return {
        "vmPFC":   _get("valuation_mean"),
        "TPJ":     _get("social_mean"),
        "IFJa":    _get("attention_mean"),
        "IFJp":    _get("attention_mean"),  # proxy — no dedicated mask
        "area_45": _get("language_mean"),
        "MT_V5":   _get("motion_mean"),
    }
