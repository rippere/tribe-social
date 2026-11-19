# UGC baseline: results

64 short-form video ads scored with prepost's brain-response model. Aggregates only: no clip names,
frames or links. The analysis plan (`PLAN.md`) was written on 2026-11-16, before any scores existed.
Deviations from it are listed below.

## What was measured
- **Model:** Meta's TRIBE v2 (`facebook/tribev2`), which predicts the brain's response (fMRI, whole cortex)
  to a video, second by second. It predicts a typical brain's response. It does not measure real viewers,
  and nothing here measures ad performance (views, clicks or sales).
- **Sample:** public YouTube Shorts, 12–60 s, one ad per channel, found by search. 88 candidates, 64 included
  (a single ad for one product, UGC or polished format, no celebrity deepfakes).
- **Primary metrics (fixed in the plan):**
  - `gfp_mean`: global field power, the overall strength of the predicted whole-cortex response, averaged over the clip.
  - `gfp_hook_lag`: the same, averaged over predicted seconds 4–8. The plan treated this as the hook window,
    assuming the predictions lag the video by about 5 s. A later check (PR #22) showed TRIBE v2's output is
    already aligned to the video, so this window reads **seconds 4–8 of the ad**, not the hook. The hook
    itself (seconds 0–3) is reported as `gfp_hook_0_3` below; see Deviations.
  - `composite_raw`: prepost's composite score from anatomical region masks.
- **Tests:** eta² and a permutation p-value (10,000 shuffles) for each factor; within-category stratified
  permutation and a regression adjusting for category and clip length for human vs AI.
- **Compute:** NVIDIA DGX Spark. Scores are compared only with scores from the same machine (see Reliability).

## 1. Planned question: does each kind of ad need its own yardstick?
No, at this sample size. Category (beauty, food, home, tech) explains little of the spread on any primary metric.

| Metric | Category eta² | p |
|---|---|---|
| composite_raw | 0.019 | 0.78 |
| gfp_mean | 0.043 | 0.47 |
| gfp_hook_lag | 0.035 | 0.56 |

Format did matter for the composite: UGC scored above polished spots (eta² 0.131, p = 0.004; +0.037 after
adjusting for category, AI or human, and length, p < 0.001).

## 2. Human-made vs AI-made
Labels are hand labels, made blind (see Labels). n = 61: 21 human, 40 AI.

| Metric | Human vs AI | eta² (p) | Within category (stratified p) | Adjusted for category + length |
|---|---|---|---|---|
| gfp_mean | **+15%** | 0.139 (0.003) | +0.031 (0.013) | +0.032 |
| gfp_hook_lag (s 4–8) | **+14%** | 0.085 (0.019) | +0.036 (0.015) | +0.035 |
| gfp_hook_0_3 (hook, s 0–3) | +11% | 0.060 (0.061) | +0.028 (0.016) | +0.026 |
| composite_raw | n.s. | 0.012 (0.40) | n.s. | n.s. |

By category (human minus AI):

| Category | Human / AI clips | Whole clip (`gfp_mean`) | Seconds 4–8 | Hook, s 0–3 |
|---|---|---|---|---|
| beauty | 4 / 15 | +0.044 | +0.036 | +0.014 |
| food | 4 / 11 | +0.036 | +0.025 | +0.016 |
| home | 8 / 3 | −0.009 | +0.010 | +0.031 |
| tech | 2 / 11 | +0.052 | +0.074 | +0.052 |

Over the whole clip the gap comes mainly from beauty and food, and home is flat. In the hook (s 0–3) human is higher
in all four, but the pooled hook difference is weaker (p = 0.061) and only clear within category. Tech rests on 2 human clips.

**Group difference, not a detector.** The scores of individual human and AI clips overlap a lot. Used alone to
tell one clip from another, `gfp_mean` gets an AUC of 0.71 and `gfp_hook_lag` 0.69 (0.5 is a coin flip, 1.0 is perfect).

## Labels
- **Original labels:** from the search query (an "AI" or "human" ad search), confirmed by an automated visual check of
  8 frames per clip. 22 human, 25 AI, 17 unclear.
- **Hand labels (2026-11-19):** one reviewer labelled all 64 clips blind: anonymous IDs, shuffled order, no file
  name or original label shown, with the full video available.
- **Agreement:** 45 of 47 (96%) on clips with an original label. Of the 17 unclear, 15 were labelled AI.
- On the original labels (n = 47) the human vs AI result was similar: eta² 0.153 (p = 0.006) for `gfp_mean`,
  0.160 (p = 0.004) for `gfp_hook_lag`. The result doesn't depend on which label set is used.
- Labels are judgements, not creator disclosure. A very realistic AI ad could be labelled human.

## Exploratory (not planned)
AI clips the automated check couldn't call ("hard to spot", n = 15) scored between obvious AI and human on
seconds 4–8 (`gfp_hook_lag`): obvious AI 0.171, hard-to-spot AI 0.201, human 0.208. Hard minus obvious: p = 0.027, uncorrected for
multiple comparisons. `gfp_mean` has the same order but is not significant (p = 0.32). Small and post hoc: a
hypothesis for the next batch. It would mean the response tracks how artificial an ad looks rather than
who made it.

## Reliability
- **Same machine:** one clip re-scored from scratch on the Spark gave bit-identical predictions and scores.
- **Different machines:** the same clip scored on the Spark and on a cloud GPU differed by up to 24% on some fields
  (different transcription precision and torch build). Scores from different machines are never mixed.

## Deviations from the plan
1. The batch first ran with region masks that were index ranges, not anatomical regions (a bug, since fixed).
   `composite_raw` was recomputed from the saved predictions with anatomical masks; that is the version reported here.
   With the old masks, the composite showed a category effect and no format effect; both flipped once fixed.
   `gfp_*` metrics use the whole cortex and were unaffected.
2. The human vs AI check within category and the hand labelling were added after the results, as checks.
3. The hard-to-spot AI comparison was not planned (see Exploratory).
4. **Hook window.** The plan's `gfp_hook_lag` (s 4–8) assumed the predictions lag the video by ~5 s. TRIBE v2 is trained
   with that delay already removed (`FmriExtractor` offset = 5), and a speech → auditory-cortex check on these 64 clips
   peaks at lag 0 (PR #22). So `gfp_hook_lag` measures the body of the ad, and the hook is seconds 0–3
   (`gfp_hook_0_3`, from the original run; in the v2 run that column holds s 4–8). Both are reported.

## Limits
Small n, thin cells (tech-human 2, home-AI 3), a sample shaped by YouTube search, a model's prediction of a typical
brain rather than real viewers, and no outcome data. Linking scores to ad performance is the next step.
