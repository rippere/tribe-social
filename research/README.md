# research — TRIBE v2 scoring & validation pipeline

**Does a brain-encoding model predict short-form video engagement?**

This is the research half of [`tribe-social`](../README.md). It applies Meta's TRIBE v2 whole-brain encoding model to short-form video, extracts predicted activation across seven cortical ROIs, and reduces those signals to an interpretable composite score — then tests whether that score has any relationship to real engagement.

> [!IMPORTANT]
> **It did not clear its gate.** On the 24-video pilot corpus the composite correlates with engagement at **r = 0.25 (p = 0.24, n = 24)** — not significant, and below the pre-registered r > 0.4 threshold. An independent 2026 paper (arXiv:2607.01400) separately found TRIBE's global predicted signal does not predict YouTube replay behavior.
> The pipeline works. Whether the number it produces means anything is unresolved, and current evidence leans negative. Every score here is **exploratory**.

---

## The Problem

Engagement metrics arrive after publication, conflate algorithmic reach with audience response, and offer no per-second diagnosis of *where* a clip loses people. A brain-encoding model is one candidate for a pre-publication signal that decomposes a clip temporally and by cortical region.

Whether that candidate actually carries engagement-relevant information is the question this repository exists to answer — not an assumption it starts from. See [`../docs/VALIDATION-PROTOCOL-AND-ROADMAP.md`](../docs/VALIDATION-PROTOCOL-AND-ROADMAP.md) for the study designed to settle it.

---

## Architecture

```
Videos (MP4)
    │
    ▼
[make fetch] ── yt-dlp → reels_new/
    │
    ▼
TRIBE v2 Encoding Model (RunPod A100 80GB)
    │  facebook/tribev2 via HuggingFace
    │  Input: raw video frames + audio
    │  Output: per-second cortical activation (69 timepoints × 20,484 vertices)
    │
    ▼
ROI Extraction (HCP MMP1.0 Atlas)
    ├── vmPFC       → Valuation / reward signal
    ├── TPJ         → Social cognition / virality proxy
    ├── IFJa / IFJp → Executive attention
    ├── Area 45     → Language processing (Broca)
    └── MT/V5       → Visual motion
    │
    ▼
scores.csv  (mean, hook [0–3s], offset [final 3s], peak second per ROI)
    │
    ├── Composite Neural Score (0–100)
    │   POST ≥ 65  |  REVISE 40–65  |  RETHINK < 40
    │
    ├── Phase 1b Correlation Analysis
    │   Pearson r vs. likes/1K views (primary available proxy)
    │   Go/No-Go verdict: ≥ 2 ROIs r > 0.3 OR composite r > 0.4
    │
    └── Streamlit Dashboard  (demo.py)
        Corpus Overview · Engagement Correlations · Score New Video
```

---

## Quick Start — Zero Credentials Required

The dashboard ships with a pre-scored 24-video corpus (3 creators × 8 videos: Ali Abdaal, Andrew Huberman, Sahil Bloom). No RunPod account, no API keys, no GPU needed.

**Prerequisites:** Python 3.12+, [`uv`](https://docs.astral.sh/uv/getting-started/installation/)

```bash
git clone <this-repo>
cd tribe-social

make setup   # creates .venv and installs dependencies
make demo    # launches http://localhost:8501
```

In the Streamlit sidebar, select **"Real corpus (scores.csv)"** to load the pre-scored dataset.

> If you don't have `uv`, install it with:
> `curl -Lsf https://astral.sh/uv/install.sh | sh`

---

## Full Pipeline — RunPod Scoring

To score your own videos:

1. Copy `.env.example` → `.env` and fill in your credentials:
   ```
   RUNPOD_API_KEY=...
   HF_TOKEN=...
   ```

2. Add video URLs to `urls_demo.txt`, then fetch:
   ```bash
   make fetch           # downloads to reels_new/ via yt-dlp
   ```

3. Score with TRIBE v2 on a RunPod A100 (~$1.64/hr):
   ```bash
   make score-corpus         # full pipeline: provisions pod → uploads → scores → downloads
   make score-corpus-dry     # validate inputs without spending GPU time
   ```

4. View ranked results in the dashboard:
   ```bash
   make demo
   ```

The `tribe-score` CLI also supports single-video scoring:
```bash
tribe-score score path/to/video.mp4
```

---

## Tech Stack

| Layer | Tool |
|---|---|
| Brain encoding model | [TRIBE v2](https://github.com/facebookresearch/TRIBE) (Meta Research) |
| Atlas / ROI extraction | HCP MMP1.0 via [neuromaps](https://netneurolab.github.io/neuromaps/) |
| GPU compute | [RunPod](https://runpod.io) A100 80GB PCIe |
| Video download | [yt-dlp](https://github.com/yt-dlp/yt-dlp) |
| Dashboard | [Streamlit](https://streamlit.io) + Plotly |
| Data / analysis | pandas, scipy, statsmodels, seaborn |
| Python env | [uv](https://docs.astral.sh/uv/) + Python 3.12 |
| Remote orchestration | paramiko (SSH), RunPod REST API |

---

## Scientific Grounding

The core hypothesis: cortical activation patterns during video consumption predict downstream sharing behavior.

| Finding | Source |
|---|---|
| fMRI during video exposure predicts YouTube views and watch time | Berns & Skipper, *PNAS* 2020 |
| vmPFC + TPJ activity predicts article virality at scale | Scholz et al., *PNAS* 2017 |
| TRIBE v2 reliably encodes attention, language, social cognition, motion | Wubble et al., *arXiv* 2604.04025 |
| vmPFC is a structural node in the cortico-striatal reward loop (upstream of dopamine) | Haber & Knutson, *Neuropsychopharmacology* 2010 |

**Honest scope:** TRIBE v2 covers cortical ROIs only — nucleus accumbens and ventral striatum (core Berns 2020 predictors) are subcortical and not directly measured. The composite vmPFC + TPJ + IFJ neuro-signature approximates the cortico-striatal value state and is the approach used in applied neuromarketing research.

---

## Pre-Scored Corpus Results

24 videos from three adjacent creators, scored via TRIBE v2 on a RunPod A100, correlating neural predictions against public YouTube engagement (likes/1K views as the primary proxy).

| Rank | Video | Creator | Score | vmPFC | TPJ | Attn | Lang | Motion | Views | Likes/1K |
|------|-------|---------|------:|------:|----:|-----:|-----:|-------:|------:|---------:|
| 1 | ali_005 | Ali Abdaal | **100.0** POST | 1.00 | 1.00 | 0.71 | 0.98 | 0.84 | 30,553 | 37.4 |
| 2 | sahil_004 | Sahil Bloom | **98.0** POST | 0.84 | 0.98 | 1.00 | 0.66 | 0.43 | 2,856 | 76.0 |
| 3 | ali_003 | Ali Abdaal | **94.7** POST | 0.91 | 0.87 | 0.75 | 1.00 | 1.00 | 14,272 | 13.9 |
| 4 | ali_001 | Ali Abdaal | **88.8** POST | 0.88 | 0.85 | 0.68 | 0.87 | 0.89 | 10,898 | 66.8 |
| 5 | huberman_005 | Andrew Huberman | **82.2** POST | 0.76 | 0.77 | 0.79 | 0.62 | 0.63 | 90,804 | 38.6 |
| 6 | sahil_001 | Sahil Bloom | **81.0** POST | 0.77 | 0.74 | 0.66 | 0.85 | 0.66 | 1,082 | 42.5 |
| 7 | huberman_002 | Andrew Huberman | **79.2** POST | 0.77 | 0.72 | 0.73 | 0.61 | 0.91 | 119,016 | 19.6 |
| 8 | sahil_006 | Sahil Bloom | **77.5** POST | 0.73 | 0.73 | 0.66 | 0.69 | 0.60 | 4,210 | 38.5 |
| 9 | ali_007 | Ali Abdaal | **73.4** POST | 0.70 | 0.65 | 0.63 | 0.69 | 0.77 | 20,887 | 24.8 |
| 10 | ali_008 | Ali Abdaal | **72.3** POST | 0.67 | 0.60 | 0.69 | 0.69 | 0.71 | 21,335 | 29.0 |
| 11 | ali_004 | Ali Abdaal | **71.9** POST | 0.67 | 0.60 | 0.69 | 0.65 | 0.70 | 12,806 | 42.6 |
| 12 | ali_002 | Ali Abdaal | **66.0** POST | 0.65 | 0.52 | 0.52 | 0.77 | 0.80 | 18,440 | 52.6 |
| 13 | sahil_002 | Sahil Bloom | **62.5** REVISE | 0.52 | 0.64 | 0.67 | 0.38 | 0.14 | 2,938 | 68.8 |
| 14 | huberman_003 | Andrew Huberman | **60.7** REVISE | 0.58 | 0.54 | 0.54 | 0.51 | 0.60 | 82,231 | 28.7 |
| 15 | sahil_008 | Sahil Bloom | **60.0** REVISE | 0.55 | 0.48 | 0.54 | 0.67 | 0.50 | 1,209 | 36.4 |
| 16 | huberman_004 | Andrew Huberman | **57.9** REVISE | 0.54 | 0.48 | 0.57 | 0.48 | 0.55 | 75,351 | 32.0 |
| 17 | ali_006 | Ali Abdaal | **55.5** REVISE | 0.47 | 0.41 | 0.56 | 0.62 | 0.60 | 18,136 | 36.7 |
| 18 | sahil_003 | Sahil Bloom | **51.8** REVISE | 0.48 | 0.44 | 0.46 | 0.52 | 0.45 | 2,140 | 46.3 |
| 19 | huberman_001 | Andrew Huberman | **50.6** REVISE | 0.49 | 0.42 | 0.43 | 0.49 | 0.62 | 73,910 | 16.0 |
| 20 | huberman_008 | Andrew Huberman | **46.8** REVISE | 0.44 | 0.35 | 0.44 | 0.48 | 0.56 | 123,807 | 22.6 |
| 21 | sahil_005 | Sahil Bloom | **44.1** REVISE | 0.38 | 0.33 | 0.42 | 0.54 | 0.28 | 1,881 | 34.6 |
| 22 | huberman_007 | Andrew Huberman | **43.3** REVISE | 0.41 | 0.36 | 0.36 | 0.44 | 0.31 | 336,423 | 23.6 |
| 23 | huberman_006 | Andrew Huberman | **13.0** RETHINK | 0.11 | 0.06 | 0.14 | 0.16 | 0.14 | 59,250 | 21.3 |
| 24 | sahil_007 | Sahil Bloom | **0.0** RETHINK | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 2,214 | 43.8 |

Scores normalized to 0–100 for display. Raw composite values and all per-ROI statistics (hook window, offset window, peak second, temporal slope) are in `scores.csv`.

**Phase 1b verdict (24-video corpus):** The composite score correlates with likes/1K views at only r = 0.25 (p = 0.24, n = 24) — NOT statistically significant. The sample is underpowered and suffers from restriction-of-range, and one ROI (MT/V5) is negatively correlated with engagement. The Phase 2 go/no-go threshold (r > 0.4) was NOT cleared. Treat all scores as exploratory pending the revised validation in docs/VALIDATION-PROTOCOL-AND-ROADMAP.md.

---

## Dashboard Features

- **Corpus Overview** — composite score distribution, top-10 ranked table, mean activation per brain region, per-creator scorecard gallery
- **Engagement Correlations** — scatter plot with OLS trendline, per-ROI correlation heatmap, automatic Go/No-Go verdict
- **Score New Video** — interactive ROI sliders, composite gauge, radar chart vs. corpus average, per-ROI revision recommendations, hook template library, simulated temporal activation breakdown

The dashboard defaults to synthetic data (no files needed). Switch to **"Real corpus (scores.csv)"** in the sidebar to use the pre-scored dataset.

---

## Project Structure

```
tribe-social/
├── demo.py                # Streamlit dashboard (all three tabs)
├── demo_data.py           # Synthetic corpus generator (no credentials needed)
├── score_corpus.py        # E2E pipeline script: fetch → score → rank
├── phase1b_correlation.py # Publishable Phase 1b correlation analysis + figures
├── run_and_save.py        # TRIBE v2 inference script (runs on the RunPod pod)
├── roi_masks.py           # HCP MMP1.0 atlas ROI extraction
├── visualize.py           # Per-video scorecard / creator grid generator
├── tribe_score/           # RunPod orchestration package
│   ├── config.py          # Config loader (.env)
│   ├── pipeline.py        # Batch + single-video scoring orchestration
│   ├── runpod.py          # RunPod pod lifecycle (provision, terminate)
│   └── remote.py          # SSH command execution + file transfer
├── scores.csv             # Pre-scored 24-video corpus results
├── engagement.csv         # Public engagement metrics for the same 24 videos
├── content_output/        # Per-video scorecards + creator grid PNGs
├── Makefile               # Task runner (make demo / make setup / make score-corpus)
└── pyproject.toml         # Python project + dependencies
```

---

## Status

| Phase | Status |
|---|---|
| Phase 0 — TRIBE v2 inference on RunPod | Complete |
| Phase 1a — 24-video pilot corpus collected + scored | Complete |
| Phase 1b — Correlation vs. engagement | Complete — **go/no-go gate NOT cleared** (r = 0.25, p = 0.24, n = 24) |
| Phase 2 — Hardened incremental-validity study | Designed, not run — see [the protocol](../docs/VALIDATION-PROTOCOL-AND-ROADMAP.md) |

Phase 2 is deliberately gated on the validation study rather than on building more product. A pipeline that produces confident-looking scores from an unvalidated signal is the failure mode this project is trying to avoid.
