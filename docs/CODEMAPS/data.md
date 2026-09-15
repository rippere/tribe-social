# Data — tribe-social
<!-- Generated: 2026-09-15 | Scope: research pipeline + scoring data | Token estimate: ~750 -->

No relational DB. Data is **CSV + on-GPU model artifacts** flowing through the research pipeline; the "tables" are CSVs in `research/`.

## Files & schemas (field names only)
| File | Rows | Fields |
|---|---|---|
| `research/scores.csv` | 24 × 43 | `filename, label, n_seconds`, then per-ROI `{roi}_{mean,hook,offset,peak_s,ts_ratio}` ×7, `composite_raw`, `gfp_{mean,hook,offset}`, `vmPFC_TPJ_coupling`, `pleasantness_index` |
| `research/engagement.csv` | 24 | `filename, platform, views, likes, shares, comments` |
| `research/engagement_template.csv` | — | `filename, views, saves, shares, comments` |
| `research/urls_demo.txt` | 15 | commented list of viral Shorts URLs (yt-dlp source) |

> ⚠ **Schema drift (real):** the template carries `saves` but the live `engagement.csv` omits `saves` and instead has `platform` + `likes`. Consistent with `research/PROJECT.md`'s note that saves/shares were never actually collected (the original primary metric). Anything reading `saves` off `engagement.csv` gets nothing. Reconcile before the pilot uses engagement as an outcome.

## Join
`filename` is the key. `apps/api/scripts/build_corpus_json.py` joins `scores.csv` ⨝ `engagement.csv` on `filename` → dashboard corpus JSON. `phase1b_correlation.py` correlates ROI columns ↔ engagement columns on the same key.

## The scoring model (packages/tribe_scoring, `_BATCH_MASKS`)
7 ROIs, hardcoded fsaverage5 vertex ranges, composite weights:
`attention .25 · social/TPJ .30 · language .15 · valuation/vmPFC .20 · auditory .05 · motion .03 · narrative .02`
Derived signals: `composite_raw`, `gfp_{mean,hook,offset}`, `vmPFC_TPJ_coupling` (Scholz 2017), `pleasantness_index`.
Atlas: `roi_masks.py` — HCP MMP1.0 / Glasser 2016 → resampled to **fsaverage5 (20,484 vertices)** via neuromaps; `_approximate_masks()` is the Phase-0 fallback.

## Pipeline data flow
```
urls_demo.txt ──make fetch (yt-dlp)──▶ research/reels/*.mp4
       │
       ├─ tribe-score CLI  ─┐   or  score_corpus.py (make score-corpus)
       ▼                    │
  RunPod A100 provision ────┤ (tribe_score/runpod.py + remote.py: ssh upload run_and_save.py + mp4)
       ▼                    │
  TRIBE v2 (facebook/tribev2 via HF) → preds (69 timepoints × 20,484 vertices)
       │  quick_scores() → per-ROI extraction (HCP MMP1.0)
       ▼                    │
  research/scores.csv ◀── download ── terminate pod ─┘
       │
       ├─▶ phase1b_correlation.py  → figure1_correlation_panel.{png,pdf}   (Go/No-Go)
       ├─▶ visualize.py / analyze.py → research/content_output/*.png
       └─▶ demo.py (Streamlit dashboard; synthetic fallback via demo_data.py)
```

## Artifacts (not persisted to repo)
TRIBE preds `(69 × 20484)` per clip live on the GPU only. Figures: `research/figure1_correlation_panel.{png,pdf}`, `research/content_output/*.png`.
