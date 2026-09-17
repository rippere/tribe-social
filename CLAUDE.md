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
| Docs | `docs/` | Cross-cutting docs: `VALIDATION-PROTOCOL-AND-ROADMAP.md` + `docs/CODEMAPS/` (architecture · backend · frontend · data · dependencies). |
| Scripts | `scripts/` | Repo tooling: `install-hooks.sh`, `pre-commit-credential-scan.sh`. |

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

`.env`, `.env.*` and `.deploy.env` are git-ignored (root `.gitignore`) and must stay
untracked. New config keys go in `research/.env.example` with a placeholder value.

Git does not version-control `.git/hooks/`, so a fresh clone has no protection until
you run `bash scripts/install-hooks.sh`. That installs the pre-commit credential scan
(source: `scripts/pre-commit-credential-scan.sh`), which blocks a commit whose staged
diff contains a real-looking key. Bypass with `SECRETS_OK=1` only when certain.

## Public-repo contract

This repository is public. Two standing rules:

- **No credentials, ever** — see above.
- **Claims carry their uncertainty.** The core hypothesis is unvalidated and the pilot
  evidence runs against it (r = 0.25, p = 0.24, n = 24; plus arXiv:2607.01400). Any
  statement about what a score predicts travels with its effect size, CI, and sample
  limits. Do not let docs drift back toward marketing language.
- **Licensing:** this code is Apache-2.0; TRIBE v2 is CC-BY-NC-4.0 and the Apache grant
  does not extend to it. See `NOTICE` before adding anything commercial-facing.
