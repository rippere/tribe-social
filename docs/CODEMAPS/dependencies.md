# Dependencies — tribe-social
<!-- Generated: 2026-09-17 | Scope: monorepo | Token estimate: ~650 -->

## External services
- **RunPod** — GPU inference (A100 80GB), runs TRIBE v2. Two modes: serverless (`apps/runpod_handler`) and warm/persistent pod (`apps/pod_server`).
- **Railway** — hosting. `apps/api` (Docker, healthcheck `/health`) and `apps/web` (Nixpacks, `npm run start`, healthcheck `/`).
- **Hugging Face** — TRIBE v2 weights (`facebook/tribev2`); HF token via env.
- **TRIBE v2 (Meta FAIR)** — the brain-encoding model. Licensed **CC-BY-NC-4.0 (non-commercial)**. This repo's Apache-2.0 grant does not extend to it; see `NOTICE` at the repo root before building anything commercial on this pipeline.

## Python — uv workspace (requires-python >=3.12, shared `uv.lock`)
Workspace members: `packages/tribe_scoring`, `research`, `apps/api`.
- **packages/tribe_scoring** — `numpy` only. Canonical scoring (`load_model`, `quick_scores` in `run_and_save.py`). Imported by `research/`, `apps/pod_server`, `apps/runpod_handler` — never re-duplicated.
- **apps/api** — fastapi, uvicorn[standard], pandas, scipy, numpy, httpx, pydantic, python-dotenv, python-multipart. dev: pytest.
- **research** — TRIBE scoring pipeline (tribev2 + nilearn/neuromaps + pandas/scipy); see `research/pyproject.toml` + `research/Makefile`.

## Web — apps/web (Next.js)
- next 16.2.6, react 19, typescript 5
- UI: shadcn, @base-ui/react, tailwindcss 4, lucide-react, class-variance-authority, clsx, tailwind-merge, tw-animate-css
- Data + charts: **swr** (fetch from API), **recharts** (ROI dashboard), **react-dropzone** (video upload)

## Internal wiring
```
apps/web ──SWR──▶ apps/api (FastAPI) ──reads──▶ research/scores.csv + research/engagement.csv
                        │                         (via apps/api/scripts/build_corpus_json.py)
apps/pod_server ─┐
apps/runpod_handler ─┴─import──▶ packages/tribe_scoring (run_and_save) ──▶ TRIBE v2 on RunPod GPU
```
Docker builds for pod_server / runpod_handler use the **monorepo root** as build context so the shared package resolves.

## Secrets / guards
- `.deploy.env` (git-ignored) — RunPod / HF / Railway credentials, must stay untracked.
- Git hooks are not version-controlled by git. Install them after cloning: `bash scripts/install-hooks.sh` (pre-commit credential scan; source in `scripts/pre-commit-credential-scan.sh`).
