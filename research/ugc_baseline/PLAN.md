# UGC baseline batch — analysis plan (written 2026-11-16, before any batch scores existed)

## Question
Do TRIBE v2-derived prepost scores behave like a standard yardstick across short-form ad content?
Specifically, how much of the between-clip spread is explained by content category, by human vs AI
production, and by format (UGC vs polished spot)?

## Sample
- Source: public YouTube Shorts surfaced by yt-dlp search, 12–60 s, one clip per channel.
- Vetting: 8-frame contact sheets judged by a subagent (`vetting.json`); include = single ad for one
  product, format ugc or polished_spot, no celebrity deepfakes. Arm/category are visual judgements from
  stills, unverified. 64 of 88 included (22 human, 25 AI, 17 unclear).
- Thin cells: tech-human n=2, home-AI n=3. Report them, don't lean on them.
- Publication: aggregates only. No names, frames or links to individual clips.

## Compute
TRIBE v2 (facebook/tribev2) on the DGX Spark (GB10, aarch64), NGC torch 2.10 build, whisperx on CPU
(int8) instead of CUDA float16. Parity check: ali_001 re-scored on the Spark vs its RunPod row in
`research/scores.csv` before trusting the batch.

### Parity result (observed 2026-11-16, before batch results)
ali_001, Spark vs RunPod: same shape (63 s), fields correlate r = 0.986, but not identical —
gfp_mean 0.6% apart, composite_raw 9.6%, gfp_hook 4.2%, attention_hook 24%, 2 of 7 peak seconds moved.
Likely cause: whisperx CPU int8 vs CUDA fp16 (different word timings feed the text features) and the
torch build. Consequence: Spark scores are compared only with Spark scores; never mix with RunPod rows.

### Run state
- Spark container `tribe` (nvcr.io/nvidia/vllm:25.11-py3 + tribev2 --no-deps, 28 GB cap, GPU_FRAC 0.22,
  `uvx` shim forcing whisperx to CPU int8). Clips in `~/tribe/ugc`, preds in `~/tribe/ugc_preds`,
  log `~/tribe/work/batch.log` (DONE/FAIL lines). Driver `~/tribe/work/batch.py` skips finished clips,
  so re-launch resumes: `docker exec -d tribe bash -lc "cd /tribe/work && python batch.py /tribe/ugc /tribe/ugc_preds >> batch.log 2>&1"`.
- **v2 hardening (2026-11-16 13:30, supersedes the v1 notes below).** Incident: after a kill, the relaunched
  worker sat silent 29 min — container PID 1 was `sleep`, the killed worker stayed a zombie, and exca's
  `inflight.db` liveness check (`os.kill(pid,0)`) treats zombies as alive. Fixes, all verified live:
  container rebuilt from image `tribe-env:20261116` with `--init` (docker-init reaps); entrypoint is the
  supervisor `run_all.sh` (clears inflight claims before every launch; kills+relaunches on 10 min log
  silence or per-clip limit 900 s + 30 s/clip-second; quarantines a clip after 2 stalls/failures; max 10
  launches then FAILED state; heartbeat.json every 60 s); host cron `*/5 deadman.sh` restarts a stopped
  container and alerts on heartbeat >15 min stale, FAILED state, or no new clip in 60 min. Pushes are
  signal-only ("Spark job: …") to the ntfy brief topic; details in `~/tribe/work/events.log` (supervisor)
  and `~/tribe/deadman/deadman.log` (host). Tests passed: freeze worker → detected 166 s, relaunched,
  encoding again in ~40 s; `docker stop` → cron revived it in <4 min with push; test push delivered.
  Script sources: `research/ugc_baseline/spark/`. Tunables: `~/tribe/work/supervisor.env`.
- (v1) Self-healing (verified 2026-11-16 by killing batch.py; supervisor relaunched it, skipped 5 done clips):
  `~/tribe/work/run_all.sh` (flock-guarded) retries the batch up to 5x until all 64 have preds, then runs
  the analysis into `~/tribe/ugc_results/` and writes `~/tribe/ugc_results/DONE`. Container restart
  policy `unless-stopped`; Spark crontab `@reboot` restarts run_all.sh. Log: `~/tribe/work/run_all.log`.
  Check: `tailscale ssh rippere@spark-8519 'cat ~/tribe/ugc_results/DONE; cat ~/tribe/work/run_all.log'`.
- Manual fallback after BATCH_END: copy `analyze_baseline.py` + `vetting.json` into the container and run
  `python analyze_baseline.py /tribe/ugc_preds vetting.json /tribe/ugc_results`. Also check arm effect
  within category (arm is unevenly spread across categories) and re-score ali_001 once to test
  Spark run-to-run determinism.

## Primary metrics (3, fixed now)
1. `composite_raw` — the existing prepost composite (unchanged code).
2. `gfp_mean` — global field power over the whole clip.
3. `gfp_hook_lag` — GFP mean over predicted seconds 4–8 (index 4 through 7), NOT 0–3.
   The existing `*_hook` columns average seconds 0–3, which is the BOLD warm-up window; they are
   reported for comparison only.
   *(Superseded after scoring: TRIBE v2 output is already stimulus-aligned, so s 0–3 is the hook and
   s 4–8 is the body of the ad. See Deviation 4 below. Text above kept as pre-registered.)*

## Tests (per primary metric)
- eta² (between-group SS / total SS) for category (beauty/food/home/tech; "other" dropped), arm
  (human vs ai; "unclear" dropped), format (ugc vs polished_spot).
- Permutation p-value, 10,000 shuffles of group labels.
- Clip length is a known confound for whole-clip means: also report Spearman rho of each metric with
  n_seconds.

## How results map to the post
- Category eta² small (< 0.06) and p > 0.05 → "one shared baseline is defensible at this n".
- Category eta² large → "standardizing creative review needs per-category norms".
- Either way: n is small, sample is YouTube-search-shaped, and nothing here measures performance.

## Results (added 2026-11-17, after scoring; everything above was written before)

Batch finished 2026-11-17 03:43 UTC: 64/64 scored, 0 quarantined, 1 supervisor restart. Aggregates only in
`results/`; per-clip scores stay off the public repo (they carry clip IDs).

### Deviations from this plan
1. **`composite_raw` recomputed with anatomical masks.** The batch ran on the scorer copy with vertex-index
   ROI ranges (fixed by PR #17). Primary composite results are the `results/v2_anatomical_masks/` run
   (main @ 3510ec7 scorer on the same `*_preds.npy`, no re-inference). `results/baseline_stats.json` is the
   original run, kept for the record. `gfp_mean` and `gfp_hook_lag` are whole-cortex and identical in both.
2. In the v2 run the column `gfp_hook_0_3` holds main's `gfp_hook`, which after PR #16 is the s 4–8 window,
   not 0–3. Not a primary metric; read the 0–3 comparison from the original run.
3. Added `analyze_within_category.py` (arm effect inside category: stratified permutation + OLS with
   category and length), as the "check arm within category" step above. n = 44 (human/ai, 4 categories).
4. **Hook window (PR #22, 2026-11-19).** The plan assumed predictions lag the video by ~5 s, so it read the hook
   from s 4–8 (`gfp_hook_lag`). TRIBE v2 is trained with that delay removed (`FmriExtractor` offset = 5), and a
   speech → auditory-cortex check on these 64 clips peaks at lag 0. So `gfp_hook_lag` measures seconds 4–8 of the
   ad, and the hook is s 0–3. Results below keep the planned metric name; RESULTS.md reports both windows.
   True hook (s 0–3) on Ben's labels: human > AI +11% pooled (p = 0.061), within category +0.028 (p = 0.016),
   higher for human in all 4 categories.

### Findings (primary metrics, v2 masks)
| Metric | Category eta² (p) | Arm eta² (p) | Format eta² (p) |
|---|---|---|---|
| composite_raw | 0.019 (0.78) | 0.001 (0.80) | **0.131 (0.004)**, UGC > polished |
| gfp_mean | 0.043 (0.47) | **0.153 (0.006)**, human > AI | 0.017 (0.31) |
| gfp_hook_lag | 0.035 (0.56) | **0.160 (0.004)**, human > AI | 0.003 (0.68) |

- **Planned question:** category eta² < 0.06 and p > 0.05 on all three → "one shared baseline is defensible at this n."
- **Human vs AI** survives within category: gfp_hook_lag +0.041 (stratified p = 0.006; +0.040 adjusted for length),
  gfp_mean +0.032 (p = 0.012). Higher for human in all 4 categories on hook_lag. Rests mostly on beauty + food.
- **UGC vs polished** on composite: +0.037 (~0.9 SD) adjusted for category, arm and length, permutation p < 0.001.
- **Mask artifact:** with the old masks composite showed a category effect (eta² 0.17, p = 0.014) and no format
  effect. Both flipped with correct masks.
- Caveats unchanged: arm/category are unverified visual labels, thin cells, YouTube-search sample, no outcome data.

### Spark run-to-run determinism (2026-11-17)
ali_001 re-scored from a fresh copy (transcription redone, no cached TSV) vs its first Spark run:
predictions bit-identical (max abs diff 0.0), transcript identical, every score 0.0% apart, 0 peak seconds moved.
The Spark-vs-RunPod gap (up to 24%) is a stack difference (whisperx CPU int8 vs CUDA fp16, torch build), not
run-to-run noise. Same-machine comparisons are exact; cross-machine scores still must not be mixed.

### Hand-label check (2026-11-19)
Ben labelled all 64 included clips blind (`label_review.py`: anonymous IDs, shuffled, no file name or prior
label shown; video + contact sheet). Labels in `human_labels.json` (carries clip IDs: keep off the public repo).
- **Agreement** with the search+subagent labels: 45/47 (96%). Of the 17 "unclear", Ben called 15 AI and 2 unclear.
  Totals: 40 AI, 21 human, 3 unclear. Cues in his notes: physics/motion, voice not matching the person,
  "too perfect", diction; human calls cite imperfection, noise, real cuts.
- **Human vs AI on Ben's labels (n=61, v2 scores):**
  - gfp_mean: human +15% pooled (eta² 0.139, p = 0.003); within category +0.031 (stratified p = 0.013);
    adjusted for category + length +0.032.
  - gfp_hook_lag: human +14% pooled (eta² 0.085, p = 0.019); within category +0.036 (p = 0.015);
    adjusted +0.035.
  - composite_raw: no arm effect (p = 0.40).
  - By category (gfp_hook_lag, human − AI; n human/AI): beauty +0.036 (4/15), food +0.025 (4/11),
    home +0.010 (8/3), tech +0.074 (2/11). gfp_mean in home is −0.009. Home is flat; tech has 2 human clips.
- **Agreed-only subset (n=45):** effect slightly larger (gfp_hook_lag within-category +0.046, p = 0.007).
- **Exploratory, not planned:** the 15 AI clips the automated check couldn't call ("hard AI") score
  between obvious AI and human on gfp_hook_lag (obvious AI 0.171, hard AI 0.201, human 0.208;
  hard − obvious p = 0.027, uncorrected). gfp_mean shows the same order, not significant (p = 0.32).
  n = 15 and post hoc: a hypothesis for the next batch, not a finding.
- Labels are still one person's judgement, not creator disclosure; very realistic AI may sit in "human".
- **Next avenue (Ben, 2026-11-19):** test whether prepost can flag when a video *reads as artificial*,
  second by second, rather than detect who made it. Needs a larger labelled set, per-second features, a held-out
  test, and outcome data. Provenance (C2PA credentials, generator watermarks) would be a separate signal.
