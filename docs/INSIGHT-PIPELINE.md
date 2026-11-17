# Insight pipeline

What prepost should hand a creator: **where** a draft falls short, **why**, and **what to try**, specific
enough to act on. An illustrative target (not a result yet): "Seconds 2–6: predicted response is in the bottom 15% of ads. In the
reference set, a face on screen at this point is followed by a rise; yours has none until second 9. Try
moving the face earlier (in model tests this moved the window up ~20 percentile points)."

Everything below is **model-internal**: it says what TRIBE v2 responds to, not what viewers do. Whether
that predicts retention is the pre-registered study's job (stage 5). Until it reports, every insight is
labelled as a model reading, with its sample size (public-repo contract, root `CLAUDE.md`).

## Stages

| # | Stage | Answers | Status | Code |
|---|---|---|---|---|
| 1 | Score | per-second predicted response | done | `packages/tribe_scoring/run_and_save.py` |
| 2 | Locate | "x is low/high here" | **v1** | `packages/tribe_scoring/norms.py`, band `norm_bands/ugc64_v1.json` |
| 3 | Explain | "…because" | not started | content events per second, event-locked response over the reference set |
| 4 | Prescribe | "try y" | not started | single-variable edits on reference clips, re-scored; measured shift per edit type |
| 5 | Validate | "and it holds for viewers" | pre-registered, not run | `research/PREREGISTRATION.md` |

## Output contract (one insight)

```
where:    video seconds a–b (= predicted seconds a–b; TRIBE v2 output is stimulus-aligned, lag 0)
what:     signal, percentile rank vs band, band name + n
because:  content event(s) at those seconds + reference-set effect size, n      (stage 3)
try:      edit type + measured model shift, n edits tested                      (stage 4)
status:   model reading | validated                                             (stage 5)
```

## Stage 2: norm band (v1)

- Reference set: the 64-ad UGC baseline (`research/ugc_baseline/`), scored on the DGX Spark.
  Covers predicted seconds 0–39 (= video seconds 0–39); a second is in the band only if ≥ 20 clips reach it.
- Signals: global field power plus the 7 Destrieux ROI timecourses.
- Predicted second t ≈ video second t (band `lag_s` = 0), and every covered second is ranked, the opening
  included. TRIBE v2 output is already stimulus-aligned: tribev2 trains with the fMRI target shifted 5 s
  (`grids/defaults.py`, `FmriExtractor` `"offset": 5`), and over the 64 clips the speech → auditory
  cross-correlation peaks at lag 0 (r ≈ 0.5). An earlier draft of this band assumed a 4 s BOLD lag and
  skipped predicted s 0–3 as warm-up; that was wrong.
- Calibration (leave-one-out over the 64): 25.2% of ranked seconds below P25 and 25.2% above P75
  (expected 25/25). Measured under the old 4 s lag, i.e. with predicted s 0–3 left out; the stored
  per-second values don't depend on the lag, but these figures (and the flag counts below) need a
  rerun of `build_norm_band.py` to cover s 0–3.
- **Same-stack only.** Spark scores are bit-reproducible run to run but differ from RunPod scores by up to
  24% on some fields. Rank only Spark-scored clips against this band.
- Known gap: median 12 flags per clip, which is too many to act on. Stage 3/4 evidence decides which ones
  are worth surfacing; until then, show the top 3 by size.

Rebuild: `research/ugc_baseline/build_norm_band.py` (runs where the `*_preds.npy` live).
