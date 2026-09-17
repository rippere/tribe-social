# tribe-social

**Does a brain-encoding model tell you anything useful about short-form video that the video itself doesn't?**

This monorepo scores short-form video with Meta's [TRIBE v2](https://github.com/facebookresearch/TRIBE) brain-encoding model, maps the predicted cortical response onto seven regions of interest, and exposes the result as a composite score, a web dashboard, and a research pipeline for testing whether that score actually predicts engagement.

> [!IMPORTANT]
> **The honest headline: the core hypothesis has not been validated, and the current evidence is against it.**
> On the 24-video pilot corpus the composite score correlates with engagement at **r = 0.25 (p = 0.24, n = 24)** — not significant, and short of the pre-registered r > 0.4 gate. An independent 2026 paper (arXiv:2607.01400) separately found TRIBE's global predicted signal does **not** predict YouTube replay behavior.
> Treat every score in this repository as **exploratory**. The scoring product is real and runs; the claim that the score *means* something is the open question, and [`docs/VALIDATION-PROTOCOL-AND-ROADMAP.md`](docs/VALIDATION-PROTOCOL-AND-ROADMAP.md) is the study designed to settle it either way.

---

## Why this repo is public

Two reasons, and neither is "look at our product."

1. **The methodology is worth more than the result.** Two designs are published here in full:
   - [`docs/VALIDATION-PROTOCOL-AND-ROADMAP.md`](docs/VALIDATION-PROTOCOL-AND-ROADMAP.md) — an incremental-validity design with negative controls, creator-grouped nested CV, conditional permutation testing and pre-committed kill criteria.
   - [`research/PREREGISTRATION.md`](research/PREREGISTRATION.md) — a cheaper, sharper prospective hook test: 18 base videos × 4 opening variants, analyzed within-base so each base is its own control. Its power analysis is reproducible — [`research/power_sim2.py`](research/power_sim2.py) regenerates the §8 table verbatim.

   Both are built so a null result is as publishable as a positive one. The approach is reusable by anyone testing whether a neural or embedding-derived feature adds real predictive value over a strong content baseline.
2. **Nulls should be visible.** The pilot did not clear its gate. Publishing the pipeline, the corpus scores, and the analysis that produced the null is more useful than quietly not mentioning it.

---

## Layout

| Path | What |
|---|---|
| [`research/`](research/) | The science: corpus → TRIBE score → correlation → go/no-go figures. CLI `tribe-score`. |
| [`packages/tribe_scoring/`](packages/tribe_scoring/) | Canonical scoring (`load_model`, `quick_scores`). Single home — never duplicated. |
| [`apps/api/`](apps/api/) | FastAPI — corpus + score-a-clip jobs, RunPod → ROI mapping. |
| [`apps/web/`](apps/web/) | Next.js dashboard — upload a clip, view ROI scores. |
| [`apps/pod_server/`](apps/pod_server/) · [`apps/runpod_handler/`](apps/runpod_handler/) | Warm + serverless RunPod GPU inference. |
| [`docs/`](docs/) | Validation protocol + [codemaps](docs/CODEMAPS/) (architecture · backend · frontend · data · dependencies). |

Contributor routing lives in [`CLAUDE.md`](CLAUDE.md); the system map is [`docs/CODEMAPS/`](docs/CODEMAPS/).

---

## Quickstart — no GPU, no credentials

The research dashboard ships with a pre-scored 24-video corpus, so you can see the whole output surface without a RunPod account or an API key.

**Prerequisites:** Python 3.12+ and [`uv`](https://docs.astral.sh/uv/getting-started/installation/).

```bash
git clone https://github.com/rippere/tribe-social.git
cd tribe-social/research

make setup   # creates .venv, installs dependencies
make demo    # Streamlit dashboard at http://localhost:8501
```

In the sidebar, pick **"Real corpus (scores.csv)"** to load the pre-scored dataset instead of the synthetic fallback.

### The web product (API + dashboard)

```bash
# terminal 1 — API (runs in mock mode with no credentials)
cd apps/api && uv run uvicorn app.main:app --reload

# terminal 2 — web
cd apps/web && npm install && npm run dev
```

The API picks its scoring backend from the environment: `POD_URL` → warm pod, `RUNPOD_API_KEY` + `RUNPOD_ENDPOINT_ID` → serverless, neither → deterministic mock. Mock mode needs no credentials and is the default for local work. The web app needs `NEXT_PUBLIC_API_URL` (defaults to `localhost:8000` in dev).

### Scoring your own video on a GPU

Requires a RunPod account and a Hugging Face token with TRIBE v2 access. Copy `research/.env.example` to `research/.env` and fill it in, then:

```bash
cd research
make fetch              # download source videos listed in urls_demo.txt (yt-dlp)
make score-corpus-dry   # validate inputs without spending GPU time
make score-corpus       # provision pod → upload → score → download → terminate
tribe-score score path/to/video.mp4   # or a single clip
```

A full corpus scoring run provisions an A100 80GB and terminates it on completion. Inference is roughly **530 s per clip** on a warm pod.

---

## How the score is built

```
video ──▶ TRIBE v2 (A100)  ──▶ 69 timepoints × 20,484 vertices (fsaverage5)
                                        │
                     ROI extraction (HCP MMP1.0 / Glasser 2016)
                                        │
        attention · social/TPJ · language · valuation/vmPFC · auditory · motion · narrative
                                        │
              per-ROI mean · hook (0–3s) · offset · peak second · temporal slope
                                        │
                           composite score ──▶ POST / REVISE / RETHINK
```

Composite weights and verdict thresholds have **one home**: `packages/tribe_scoring/composite.py`. The pod computes the raw composite, the API scales it to the corpus range and serves the verdict, and the web app renders what the API returns.

Full detail: [`docs/CODEMAPS/data.md`](docs/CODEMAPS/data.md) and [`docs/CODEMAPS/backend.md`](docs/CODEMAPS/backend.md).

---

## Scientific grounding, and its limits

| Finding | Source |
|---|---|
| fMRI during video exposure predicts YouTube views and watch time | Berns & Skipper, *PNAS* 2020 |
| vmPFC + TPJ activity predicts article virality at scale | Scholz et al., *PNAS* 2017 |
| TRIBE v2 encodes attention, language, social cognition, motion | d'Ascoli et al., 2026 (arXiv:2605.04326) |
| vmPFC is a structural node in the cortico-striatal reward loop | Haber & Knutson, *Neuropsychopharmacology* 2010 |
| **TRIBE's global predicted signal does NOT predict YouTube replay** | **arXiv:2607.01400 (2026)** |

**Scope limits, stated plainly:**

- TRIBE v2 covers **cortical** ROIs only. Nucleus accumbens and ventral striatum — the core Berns 2020 and Scholz 2017 predictors — are subcortical and are not directly measured. The composite is a cortical approximation of a cortico-striatal value state, not a measurement of it.
- The model predicts a **population-average** response. It says nothing about any specific audience, and it is not an audience-targeting instrument.
- The pilot corpus is **24 videos from 3 creators** — underpowered, with restriction-of-range, and one ROI (MT/V5) correlates *negatively* with engagement.
- Nothing here is a virality predictor. The defensible framing is a population-average salience read on the first seconds of a clip, and even that is pending validation.

---

## Project status

| Stage | State |
|---|---|
| Phase 0 — TRIBE v2 inference on RunPod | Complete |
| Phase 1a — 24-video pilot corpus collected + scored | Complete |
| Phase 1b — correlation vs. engagement | Complete — **go/no-go gate NOT cleared** (r = 0.25, p = 0.24) |
| Phase 2 — hardened incremental-validity study | Designed, not run — see [the protocol](docs/VALIDATION-PROTOCOL-AND-ROADMAP.md) |

---

## Licensing — read before you build on this

The code here is **Apache-2.0** (see [`LICENSE`](LICENSE)).

**TRIBE v2 is not.** The model this pipeline invokes is **CC-BY-NC-4.0** — non-commercial only. Apache-2.0 on this repository grants you nothing with respect to those weights and cannot relicense them. Running this code against TRIBE v2 as part of any paid product or client deliverable is very likely a license violation, and "sell the service, not the model" does not fix it.

[`NOTICE`](NOTICE) has the full breakdown, including the dataset-taint issue and what a commercially clean path would actually require.

---

## Contributing & security

- [`CONTRIBUTING.md`](CONTRIBUTING.md) — setup, tests, the single-home rule, PR expectations.
- [`SECURITY.md`](SECURITY.md) — how to report a vulnerability; never commit credentials.

No credentials belong in this repository. `.env`, `.env.*`, and `.deploy.env` are git-ignored, and `scripts/pre-commit-credential-scan.sh` is available as a local hook — see CONTRIBUTING.
