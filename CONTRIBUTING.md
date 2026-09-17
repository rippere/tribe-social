# Contributing to tribe-social

Thanks for looking. This is a research repository first and a product second — the most valuable contributions are usually the ones that make the science harder to fool, not the ones that add features.

## Before you start

Read the honest-status box in [`README.md`](README.md). The core hypothesis has not been validated and the pilot's evidence runs against it. Contributions that quietly strengthen the marketing claim without strengthening the evidence will be declined.

Also read [`NOTICE`](NOTICE). This code is Apache-2.0, but TRIBE v2 is CC-BY-NC-4.0. Do not contribute anything whose purpose is commercial use of the non-commercial model.

## Setup

**Prerequisites:** Python 3.12+, [`uv`](https://docs.astral.sh/uv/getting-started/installation/), Node 20+ (for `apps/web`).

```bash
git clone https://github.com/rippere/tribe-social.git
cd tribe-social

bash scripts/install-hooks.sh   # REQUIRED — installs the credential pre-commit scan

cd research && make setup       # research pipeline + Streamlit demo
```

`scripts/install-hooks.sh` is not optional. Git does not version-control `.git/hooks/`, so a fresh clone has no credential scan until you install it. Everything else in this repo assumes it is running.

## Running things

| What | Command |
|---|---|
| Research demo (no GPU, no credentials) | `cd research && make demo` |
| Research targets | `cd research && make help` |
| API (mock mode, no credentials) | `cd apps/api && uv run uvicorn app.main:app --reload` |
| API tests | `cd apps/api && pytest` |
| Web | `cd apps/web && npm run dev` |

The API selects its backend from the environment — `POD_URL` → warm pod, `RUNPOD_API_KEY` + `RUNPOD_ENDPOINT_ID` → serverless, neither → deterministic mock. Develop against mock unless you are specifically changing inference.

## The rules that actually matter

**1. One home per fact.** This repo has been bitten by the same constant living in three places. The composite weights and verdict thresholds live in `packages/tribe_scoring/composite.py` and nowhere else. The pod computes, the API scales and serves, the web renders. If you find yourself re-implementing scoring logic in TypeScript or in the API, stop — import or fetch it instead.

**2. Never duplicate `run_and_save.py`.** `packages/tribe_scoring` is the canonical scorer, imported by `research/`, `apps/pod_server/`, and `apps/runpod_handler/`. Docker builds for the pod and handler use the **monorepo root** as build context precisely so the shared package resolves. Do not copy it back into an app.

**3. No credentials, ever.** `.env`, `.env.*`, and `.deploy.env` are git-ignored and must stay that way. If you add a new configuration key, add it to `research/.env.example` with a placeholder value and document what it does.

**4. Claims carry their uncertainty.** Any statement about what a score predicts must travel with its effect size, confidence interval, and sample limits. This is the project's actual differentiator; treat it as a hard requirement, not a style preference.

**5. Update the codemap with the code.** [`docs/CODEMAPS/`](docs/CODEMAPS/) is the system map. A card is stale the moment code moves under it. If your change moves a route, a service, or a schema, update the matching card in the same PR, and check the change-impact index in [`docs/CODEMAPS/CONTEXT.md`](docs/CODEMAPS/CONTEXT.md) for anything else that must move with it.

## Pull requests

- Branch from `master`. Keep one concern per PR.
- Run `pytest` in `apps/api` if you touched the API; run the research demo if you touched scoring.
- Describe what you changed **and what you verified** — "tests pass" is weaker than "ran the corpus scoring end-to-end and the composite matched the previous run to 4dp."
- If your change affects the science (scoring, ROI extraction, correlation analysis, the protocol), say explicitly how it changes what can be claimed.

## Reporting problems

Bugs and questions: open an issue. Security or credential exposure: see [`SECURITY.md`](SECURITY.md) — do not open a public issue for those.
