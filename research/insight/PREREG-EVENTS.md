# Pre-registration: event-locked TRIBE v2 responses on fresh held-out clips

Written and committed 2026-11-17 (~21:50 UTC), **before any holdout clip was searched for, downloaded,
vetted or scored**. The git commit that adds this file is the timestamp. Nothing below changes after
that commit; any deviation is logged at the end, in a section added after the results are in.

## Why

The event-locked results so far (12–20 of 56 event × signal tests at q < 0.10 at lag 0) were found
post hoc, on the same 64 clips that were used to choose the analysis window (the lag was changed
from 4 s to 0 s after looking at the data). This is a confirmatory test on new clips, with the design
and the hypothesis set fixed in advance.

What is being tested is model-internal: whether TRIBE v2's **predicted** cortical response moves
around content events (speech onsets, pauses, cuts, faces, on-screen text) in a consistent direction.
It says nothing about real viewers, attention or ad performance.

## Design (fixed)

Implementation: `research/insight/event_confirm.py` (this commit). Constants in that file are the
design; this section restates them.

- **Signals** (8): `norms.timecourses(preds, run_and_save._BATCH_MASKS)` → gfp + 7 ROI means
  (attention, social, language, valuation, auditory, motion, narrative). Each z-scored within clip over
  **all** predicted seconds (no warm-up exclusion), which also demeans it.
- **Lag 0.** TRIBE v2 output is already stimulus-aligned (tribev2 FmriExtractor offset = 5 at training).
- **Window.** Event at video time t → s = floor(t). Kept if s ≥ 3 and s + 3 ≤ n − 1.
  baseline = mean z over predicted s−3..s−1; response = mean z over predicted s..s+3;
  effect = response − baseline (within-clip SD units).
- **Unit = clip.** Effects averaged within clip, then across clips. A test runs only if ≥ 10 clips
  have a kept event of that type.
- **Null.** Per clip, the kept event seconds are circularly shifted by one random integer offset
  within that clip's valid range [3, n−4] (same count and spacing); same offset for all 8 signals;
  5000 shuffles; seed 20261118. The null is **centred**: μ = null mean, centred effect = obs − μ
  (μ ≠ 0 when a signal drifts within a clip). Two-sided p = (1 + #{|null−μ| ≥ |obs−μ|}) / 5001.
- **CI.** 95% percentile bootstrap over clips (5000), for the raw and the centred effect.
- **Event detectors**: the four discovery extractors (`extract_speech/cuts/faces/text.py`), same
  code and parameters, run on the holdout through `event_confirm.py --extract` (paths only change).
  Measured detector precision on discovery clips: cuts 20/20, face_appear 85%, face_disappear 75%,
  speech_onset 70%, pause_start 40%, text 30–55%. Speech events need the whisperx word timings that
  scoring writes, so speech extraction on the holdout runs after scoring.

## Discovery (64 clips, this design, run before this commit)

`event_confirm.py --discover`: 64 clips, 56 tests (7 event types × 8 signals), none skipped.
Hypothesis set = tests with BH q < 0.10 over all 56 → **16 hypotheses**. Direction = sign of the
centred effect. Full aggregates: `results/event_confirm_discovery.json`; the frozen set:
`results/prereg_events_hypotheses.json`
(sha256 `899ab1a0f1ecc8193bc838b45da672ed513b968142e86b7358211b48f5d10d8a`).

| Hypothesis | Dir | Centred effect (SD) | 95% CI | Raw effect | q (disc.) | Clips / events |
|---|---|---|---|---|---|---|
| speech_onset:auditory *(control)* | + | +0.628 | [+0.434, +0.820] | +0.665 | 0.002 | 29 / 84 |
| speech_onset:language | + | +0.326 | [+0.175, +0.481] | +0.545 | 0.002 | 29 / 84 |
| speech_onset:motion | − | −0.244 | [−0.512, +0.029] | −0.261 | 0.061 | 29 / 84 |
| pause_start:auditory *(control)* | − | −0.486 | [−0.749, −0.216] | −0.519 | 0.002 | 33 / 91 |
| pause_start:narrative | + | +0.266 | [+0.071, +0.465] | +0.459 | 0.007 | 33 / 91 |
| pause_start:social | + | +0.177 | [−0.013, +0.381] | +0.410 | 0.048 | 33 / 91 |
| pause_start:language | − | −0.214 | [−0.391, −0.029] | +0.022 | 0.048 | 33 / 91 |
| pause_start:attention | − | −0.217 | [−0.383, −0.041] | −0.157 | 0.099 | 33 / 91 |
| face_appear:auditory | + | +0.398 | [+0.198, +0.610] | +0.521 | 0.002 | 36 / 88 |
| face_appear:language | + | +0.267 | [+0.122, +0.426] | +0.561 | 0.006 | 36 / 88 |
| face_appear:gfp | − | −0.265 | [−0.509, −0.032] | −0.221 | 0.052 | 36 / 88 |
| face_appear:valuation | + | +0.189 | [+0.033, +0.356] | +0.311 | 0.090 | 36 / 88 |
| face_appear:motion | − | −0.223 | [−0.418, −0.027] | −0.247 | 0.090 | 36 / 88 |
| face_disappear:auditory | − | −0.388 | [−0.597, −0.189] | −0.321 | 0.002 | 37 / 94 |
| face_disappear:gfp | + | +0.355 | [+0.135, +0.582] | +0.453 | 0.006 | 37 / 94 |
| face_disappear:social | + | +0.255 | [+0.092, +0.419] | +0.554 | 0.006 | 37 / 94 |

No cut or on-screen-text test reached q < 0.10 in discovery. These numbers are optimistic
(winner's curse): the window was chosen on these clips. Expect smaller holdout effects.

## Confirmation rule (fixed)

`event_confirm.py --confirm` on the holdout, reading the frozen hypothesis file (its sha256 is
written into the output).

- Test **only the 16 hypotheses**, each one-sided in its discovery direction:
  p = (1 + #{d·(null−μ) ≥ d·(obs−μ)}) / 5001, d = discovery sign.
- BH over the 16. **A hypothesis replicates iff q < 0.05 AND the holdout centred effect has the
  discovery sign.** A hypothesis whose test cannot run (< 10 clips with that event) counts as not
  replicated (p = 1 in the BH set).
- **Positive controls**: speech_onset:auditory and pause_start:auditory. If either fails to
  replicate, read it as a pipeline/detector problem first, not as evidence about the other 14.
- Report holdout effect sizes, CIs and two-sided p/q for **all 56** tests, descriptively only.
- Report: n replicated / 16, each with discovery and holdout centred effects and CIs.

## Holdout sample (fixed)

- **Target 40 included clips, minimum 30.** If fewer than 30 are included after sourcing, the
  confirmation still runs and is reported as underpowered.
- **Source**: public YouTube Shorts via `yt-dlp` search, the same query templates as discovery
  (`ugc ad <kw> creator #shorts` for the human arm and `ai ugc ad <kw> #shorts` for the AI arm, with
  the same 3 keywords per category for beauty/food/home/tech; plus discovery's top-up queries if a
  cell is short). Same title filters (the discovery's later, stricter AI and junk regexes), duration
  12–60 s, one clip per channel. Searches go deeper (more results per query) so they get past
  results already used.
- **Excluded**: every channel and every video in the discovery set's 88 vetted clips (and any
  channel or video in discovery's candidate pools).
- **Vetting**: same rule as discovery, from 8-frame contact sheets: include = single ad for one
  product, format `ugc` or `polished_spot`, no celebrity deepfakes. Vetting is done before any
  holdout clip is scored, and include/exclude is never revisited after scoring.
- Clips that fail to score (quarantined) are dropped and counted.
- Clip identifiers stay on the Spark. This repo gets aggregates only.

## Limits stated in advance

- Model-internal: predicted responses only, no viewer data.
- Small n (~40 clips; ~20 with any given event type); YouTube-search sample; vetting from stills.
- Detector precision for pause_start (40%) and text (30–55%) is low, which biases those effects
  toward zero.
- Speech events co-occur with each other and with faces (see `verify_event_confounds.py`); a
  replicated face effect may partly be a speech effect.
