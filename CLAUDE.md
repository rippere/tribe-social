# tribe-social — Monorepo Routing Guide

This is a consolidated monorepo. Work in the subtree that matches your task; do not
scatter changes across roots.

## Layout / routing

| Area | Path | What lives here |
|------|------|-----------------|
| Research pipeline | `research/` | TRIBE v2 scoring research: corpus collection, scoring orchestration (`tribe_score/`), correlation analysis, visualization, demo. The `tribe-score` CLI. |
| Web frontend | `apps/web/` | Next.js app. See `apps/web/CLAUDE.md` for app-specific guidance. |
| API backend | `apps/api/` | FastAPI service (`app.main:app`). Maps RunPod scores to ROI dashboard data. |
| Pod server | `apps/pod_server/` | Warm/persistent RunPod GPU inference server (`server.py`). |
| RunPod handler | `apps/runpod_handler/` | RunPod serverless handler (`handler.py`). |
| Shared scoring | `packages/tribe_scoring/` | The single canonical `run_and_save.py` (`load_model`, `quick_scores`). Imported by research/, pod_server and runpod_handler — do NOT re-duplicate it. |
| Docs | `docs/` | Cross-cutting docs, incl. `VALIDATION-PROTOCOL-AND-ROADMAP.md`. |

- Research → `research/`
- Web / API / Pod → `apps/<name>/`
- Shared scoring logic → `packages/tribe_scoring/` (never copy `run_and_save.py` back into an app)

## Build / test / run

Python is a uv workspace (root `pyproject.toml`); `tribe_scoring` is a shared member.

- Research: `cd research && make help` (targets: `setup`, `demo`, `fetch`, `analyze`,
  `score-corpus`). CLI entry point: `tribe-score`.
- API: `cd apps/api && uv run uvicorn app.main:app --reload`
  - Tests: `cd apps/api && pytest` (includes `tests/test_scoring_mapping.py`).
  - Corpus build: `python apps/api/scripts/build_corpus_json.py` (run from repo root;
    reads `research/scores.csv` + `research/engagement.csv`).
- Web: `cd apps/web && npm run dev` (also `build`, `start`).
- Pod server / handler Docker builds use the **monorepo root** as build context so the
  shared package is available, e.g.:
  `docker build -f apps/pod_server/Dockerfile -t tribe-pod .`
  `docker build -f apps/runpod_handler/Dockerfile -t tribe-handler .`

## Secrets

`.deploy.env` files are git-ignored (root `.gitignore`) and must stay untracked.
A pre-commit hook scans for real-looking credentials; a pre-push hook refuses
unrelated-history pushes. Hooks live in `.git/hooks/` (not version-controlled).
