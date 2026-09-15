# tribe-social

TRIBE v2 **neural content intelligence** — a consolidated monorepo that scores short-form video with Meta's TRIBE v2 brain-encoding model, exposes scoring + an ROI dashboard as a web/api/GPU product.

> **Routing for contributors:** [`CLAUDE.md`](CLAUDE.md) · **Architecture:** [`docs/CODEMAPS/`](docs/CODEMAPS/)

## Layout
| Path | What |
|---|---|
| `research/` | The science: corpus → TRIBE score → correlation → Go/No-Go figures. CLI `tribe-score`. |
| `packages/tribe_scoring/` | Canonical scoring (`load_model`, `quick_scores`) — the single home, never duplicated. |
| `apps/api/` | FastAPI — corpus + score-a-clip jobs, RunPod → ROI mapping. |
| `apps/web/` | Next.js dashboard — upload a clip, view ROI scores (recharts). |
| `apps/pod_server/` · `apps/runpod_handler/` | Warm + serverless RunPod GPU inference. |
| `docs/` | Local-only working material (not tracked). Start at [`CONTRIBUTING.md`](CONTRIBUTING.md). |
| `docs/` | Validation protocol + [codemaps](docs/CODEMAPS/). |

## Quickstart
- **Research:** `cd research && make help` (`setup`, `demo`, `fetch`, `score-corpus`, `analyze`)
- **API:** `cd apps/api && uv run uvicorn app.main:app --reload` · tests: `pytest`
- **Web:** `cd apps/web && npm run dev` (needs `NEXT_PUBLIC_API_URL`)
- **Deploy:** Railway (api, web) + RunPod (pod_server, runpod_handler) — see [`docs/CODEMAPS/dependencies.md`](docs/CODEMAPS/dependencies.md)

## The one thing to know
Two tracks: a **product** (scorer + dashboard) and the **research** that decides whether the score means anything. The pilot (`docs/VALIDATION-PROTOCOL-AND-ROADMAP.md` §7) gates the core claim — a 2026 paper already found TRIBE's global signal null vs. YouTube re-watch, so the honest-diagnostic framing is deliberate, not marketing.
