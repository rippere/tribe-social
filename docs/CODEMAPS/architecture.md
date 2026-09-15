# Architecture — tribe-social
<!-- Generated: 2026-09-15 | Scope: monorepo | Token estimate: ~850 -->

## What it is
Consolidated monorepo for the **TRIBE v2 neural-content-intelligence** project: a research pipeline that scores short-form video with Meta's TRIBE v2 brain-encoding model, a web/api/GPU **product** that exposes scoring + an ROI dashboard. Canonical branch: `master`.

## Service boundaries (one job each)
| Area | Job | Detail codemap |
|---|---|---|
| `research/` | The science: corpus → score → correlate → figures. CLI `tribe-score`. | `data.md` |
| `packages/tribe_scoring/` | Canonical scoring (`load_model`, `quick_scores`). Single home — never duplicated. | `backend.md` |
| `apps/api/` | FastAPI: maps RunPod scores → ROI dashboard data; builds corpus JSON. | `backend.md` |
| `apps/web/` | Next.js dashboard: upload a clip, view ROI scores (recharts). | `frontend.md` |
| `apps/pod_server/` | Warm/persistent A100 inference server. | `backend.md` |
| `apps/runpod_handler/` | RunPod serverless inference handler. | `backend.md` |
| `docs/` | Local-only working material (not tracked). | `CONTRIBUTING.md` |
| `docs/` | Cross-cutting docs: validation protocol + these codemaps. | — |

## Scoring lifecycle (core data flow)
```
[web] upload clip ─▶ [apps/api] ─▶ RunPod ──(serverless: runpod_handler)──┐
                          ▲          (warm: pod_server) ───────────────────┤
                          │                                                ▼
                          │                       packages/tribe_scoring.run_and_save
                          │                         load_model → quick_scores
                          │                       TRIBE v2 on GPU → 20,484-vertex BOLD
                          │                                                │
                          │                          ROI extraction (attention/TPJ/vmPFC/…)
                          └──── maps scores → ROI dashboard JSON ◀──────────┘
                                       │
                          [web] SWR fetch → recharts render
```
Offline corpus path: `apps/api/scripts/build_corpus_json.py` reads `research/scores.csv` + `research/engagement.csv` → dashboard corpus.

## Deploy
- **Railway:** `apps/api` (Docker, `/health`), `apps/web` (Nixpacks, `npm start`, `/`).
- **RunPod:** `pod_server` (warm) + `runpod_handler` (serverless), Docker built from **monorepo root** so `tribe_scoring` resolves.
- Full list: `dependencies.md`.

## Two tracks (why both exist)
- **Product** (`apps/` + `packages/`) — the scorer + dashboard, deployable today.
- **Research** (`research/`) — the validation that decides whether the score *means* anything. The pilot (`docs/VALIDATION-PROTOCOL-AND-ROADMAP.md` §7) GO/NO-GO gates the product's core claim; a paper (`arXiv:2607.01400`) already found TRIBE's global signal null vs. re-watch, so the honest-diagnostic framing is load-bearing.
