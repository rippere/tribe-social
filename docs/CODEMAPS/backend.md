# Backend — tribe-social
<!-- Generated: 2026-09-15 | Scope: apps/api + pod_server + runpod_handler + packages/tribe_scoring | Token estimate: ~950 -->

## apps/api — FastAPI ("tribe-api"), the product API
Entry `app/main.py`: `FastAPI(...)`; lifespan loads `data/corpus.json` → `state.corpus_data`, `reconcile_interrupted_jobs()`, spawns `cleanup_loop()`; CORS `*`; mounts 4 routers.

### Routes
```
GET    /health             → health()        [routers/health.py]  reports mode pod|real|mock (env)
GET    /corpus             → get_corpus()     [routers/corpus.py]  reads state.corpus_data
GET    /corpus/stats       → get_stats()      [routers/corpus.py]
POST   /jobs        (202)  → create_job()     [routers/jobs.py]    validate file(.mp4 ≤50MB ≤60s, ffprobe)
                                                                   OR video_url(YT/IG regex)→downloader.fetch_video()(yt-dlp)
                                                                   → inference.submit_job()
GET    /jobs/{id}          → get_job()        [routers/jobs.py]    store/jobs.py
DELETE /jobs/{id}          → cancel_job()      [routers/jobs.py]
POST   /admin/flush-corpus → flush_corpus()   [routers/admin.py]   X-Admin-Token vs ADMIN_TOKEN → corpus_writer.flush_to_disk()
```

### The backend-routing brain — `services/inference.py::submit_job()` (env precedence)
```
POD_URL set                       → pod_process_job()   POST {POD_URL}/score, poll /result/{id}   (warm pod)
RUNPOD_API_KEY + RUNPOD_ENDPOINT_ID → real_process_job() refcount enable/disable_endpoint, submit, poll (serverless)
neither                            → _mock_process()    deterministic np.random by filename hash
```
All three converge → `_map_runpod_output_to_roi()` → `scoring.{compute_composite, compute_verdict, get_revision_tips, generate_temporal_data}` → `ScoreResult` → `corpus_writer.add_video_to_corpus()`.

### Services
- `runpod_client.py` — `submit/check_status/poll` (REST `api.runpod.ai/v2`) + `enable/disable_endpoint` (GraphQL `saveEndpoint`, workersMax 3↔0 for **cost control**).
- `scoring.py` — ports `research/demo.py`: `COMPOSITE_WEIGHTS`, verdict thresholds POST≥65 / REVISE≥40, `REVISION_TIPS`, `HOOK_TEMPLATES`, `generate_temporal_data()`.
- `corpus_writer.py` — in-memory append + `_recompute_stats()`; `flush_to_disk()` → `data/corpus.json` (24 videos).
- `downloader.py` — yt-dlp subprocess fetch.
- Models: `models/job.py` (`Job`, `JobStatus`, `ScoreResult`, `TemporalPoint`, `RevisionTip`), `models/scores.py`. `state.py` module-global `corpus_data`; `store/jobs.py` process-local dict.
- Config: `railway.toml` (`/health`), `Dockerfile` (py3.12-slim + ffmpeg + pinned `YTDLP_VERSION`, `uv sync`, uvicorn `$PORT`), `tests/` (2 mapping tests, pytest `pythonpath=.`).

## apps/pod_server — warm A100 inference (preferred real backend, `POD_URL`)
`server.py` FastAPI. `@startup _warm_load()` → `tribe_scoring.run_and_save.load_model()` (kept in VRAM). Async: `POST /score` (daemon thread `_run_inference` → `job_id`) → `GET /result/{job_id}`; `GET /health`. Auth `X-Pod-Key`/`POD_KEY` (`require_pod_key`, hmac). Inference: `model.get_events_dataframe(video)` → `model.predict()` → `quick_scores(preds)`. **~530 s/score.**
Dockerfile: `runpod/pytorch…torch260`, installs `tribev2@${TRIBEV2_REF}`, build context = **monorepo root**, COPY `packages/tribe_scoring`. No railway.toml.

## apps/runpod_handler — RunPod Serverless (real backend when `RUNPOD_ENDPOINT_ID`, no `POD_URL`)
`handler.py` → `runpod.serverless.start({"handler": handler})`. Serverless equivalent of pod_server: `load_model` + `quick_scores`. Dockerfile builds from monorepo root.

## packages/tribe_scoring — canonical scoring (single home)
`__init__` exports `load_model(cache_folder)`, `quick_scores(preds)->dict`, `_BATCH_MASKS`.
`run_and_save.py` (278 ln): `_bilateral(*ranges)`, `quick_scores` (per-ROI mean/hook/offset/peak_s/ts_ratio ×7 + `composite_raw`, `gfp_*`, `vmPFC_TPJ_coupling` [Scholz 2017], `pleasantness_index`), `run_single(model,path,text,label)->np.ndarray`, `main()` (CLI `--batch-dir --results-csv`, runs on the pod).
Imported by `research/visualize.py`, `apps/pod_server/server.py`, `apps/runpod_handler/handler.py`.

> ⚠ **Dual composite-weights (drift risk):** the ROI composite is defined **twice** — `packages/tribe_scoring._BATCH_MASKS` (the scoring pod) and `apps/api/services/scoring.py::COMPOSITE_WEIGHTS` (ported from `demo.py`, the API mapping). Two homes for one fact; they can silently diverge. Candidate for consolidation into the shared package.
