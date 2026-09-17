# Pre-registration: does predicted cortical response add anything to a content model for short-form hook rate?

**Status:** DRAFT until frozen. Freeze by committing this file, the extracted features and the analysis code, tagging the commit, and recording the tag and SHA in section 12. Nothing is measured before that.
**Version:** 0.2, written 2026-09-17. Changed after the power simulation (`power_sim.py`, `power_sim2.py`) showed version 0.1 could not succeed: the fixed rank bar was unreachable and the rank test was the weaker instrument. Both changes are pre-data.
**Investigator:** Ben Rippere. **Stimuli:** Lucas Blais. **Model license:** TRIBE v2 is CC BY-NC 4.0, so this is non-commercial research only.
**Registry:** OSF (public, no embargo).

---

## 1. The question

Does adding TRIBE v2's predicted cortical response to a content-only model improve prediction of how many people watch past the first 3 seconds of a short-form video?

This is a question about incremental validity, not about whether the brain model "works." A brain model that merely restates loudness, motion or hook category adds nothing a cheaper model cannot provide.

## 2. Why this design and not the last one

The earlier attempt used 24 clips from 3 creators, scored against public view counts. Re-analysis on 2026-09-17 showed why it could not answer anything:

- The independent unit was the creator, so the effective sample was about 3, not 24.
- At n=24 the smallest detectable correlation is 0.55. Plausible effects here are 0.1 to 0.3.
- Every feature was flat against log views (composite -0.04, attention -0.06, brain-wide power -0.01).
- Two features tracked clip length instead of content (brain-wide power -0.49 with duration, attention hook +0.34).
- Views measure a creator's audience and the platform's ranking, not the clip.

A published preprint (arXiv 2607.01400) reached a null on a related question using YouTube replay heatmaps, which carry the same audience confound.

This design fixes all five problems: the hook is manipulated inside each item, delivery is paid and budget-matched, and the outcome is measured by the platform rather than reported by a creator.

## 3. Stimuli

18 base videos about ordinary consumer subjects, 4 opening variants each, 72 clips. The count comes from the power simulation in section 8, not from convenience.

Within a base, the 4 variants share identical body footage, audio, cut and length to the frame. Only the first 3 seconds differ, across four conditions: spoken hook, visual or motion hook, text on screen, and cold open. Across bases everything differs, so results are not about one product.

Fixed specs: vertical 1080 x 1920, 30fps, 15 to 25 seconds, all files normalized to about -14 LUFS, no licensed music, no third-party brands. Full brief: `STIMULUS-BRIEF.md`.

## 4. Delivery protocol

- One ad per ad set, one ad set per clip, 72 ad sets.
- Campaign budget optimization OFF. Equal daily budget on every ad set.
- Identical audience on every ad set: United States, 18 to 65, no detailed targeting.
- Single placement: Instagram Reels.
- Objective: reach. Optimizing for video views would select viewers who were going to watch anyway.
- Frequency cap 1 per person per day.
- All 72 ad sets start and stop at the same time and run at least 3 full days.
- If capacity forces waves, a wave contains complete bases, never a partial base.

Delivery diagnostics, pulled with the results: impressions per clip, frequency, and impression balance across the 4 variants of each base.

## 5. Outcome

**Primary outcome:** hook rate = 3-second video plays divided by impressions, as reported by the platform, analyzed as a logit and weighted by impressions.

**Impressions floor:** 750 per clip, targeting 1,000. The simulation shows power is almost flat in this range, so spend goes to more base videos instead.

**Secondary outcome (reported, not decisive):** hold rate, the share reaching 15 seconds.

## 6. Predictors: four models

| Model | Features |
|---|---|
| **A, content baseline** | Visual embeddings (whole clip and first 3 seconds), audio loudness in LUFS and RMS envelope statistics, motion energy from frame differences, transcript embedding, clip duration |
| **B, brain only** | TRIBE v2 predicted response over the project's ROI set (attention IFJa and IFJp, auditory and social STS, language area 45, social cognition TPJ, valuation vmPFC, motion MT/V5) plus global field power, each summarized over the first 3 seconds, its slope, and the whole clip |
| **C, combined** | A plus B |
| **R, negative control** | A plus random projections with exactly the same dimensionality as B, same pipeline |

Dimensionality reduction, if used, is fit inside training folds only. Scores are produced blind to any performance data.

## 7. Hypotheses and the bars they must clear

**H1, primary, within-base association.** Centre both the model's predicted score and logit hook rate inside each base, then correlate them across all clips.
Bar: permutation p < 0.05, where the null permutes variant labels within each base 10,000 times. The effect size and its base-resampled interval are reported, and mean Kendall tau-b across bases is reported alongside as the readable version.
No fixed effect-size floor. Version 0.1 set one at tau 0.30; the simulation showed that bar needs model skill near rho 0.62, which nothing in this literature approaches, so it would have guaranteed a null regardless of the truth.

**H2, primary, incremental validity.** Leave-one-base-out cross-validated prediction of logit hook rate.
Bar: ΔR²(C minus A) at least 0.03 AND conditional permutation p < 0.05 (brain features permuted within base after regressing out Model A) AND the lower bound of a base-resampled bootstrap interval above 0.

**H3, secondary, beyond hook category.** Model C must beat a baseline of four variant-type dummies by ΔR² at least 0.02. If it does not, the read is restating "spoken hooks win" and adds nothing.

**Negative control.** Model R must not clear the H2 bar. If it does, the pipeline is leaking and the result is void.

Secondary tests are corrected with Benjamini-Hochberg.

## 8. Power, simulated before freezing

Run with `power_sim.py` and `power_sim2.py` (seed 20260917), 8,000 to 40,000 simulations per cell. Both default to the registered design of 1,000 impressions per clip at an $8 CPM, so running them reproduces the table below rather than a differently-parameterised one. The independent unit is the base video. "Model skill" (rho) is the correlation between the model's prediction and a variant's real hook quality, after the content baseline has taken its share.

Power of the primary test at 1,000 impressions per clip:

| Bases | Clips | Ad spend at $8 CPM | Power if rho = 0.3 | Power if rho = 0.4 | Power if rho = 0.5 |
|---|---|---|---|---|---|
| 10 | 40 | $320 | 0.48 | 0.70 | 0.88 |
| 15 | 60 | $480 | 0.63 | 0.85 | 0.96 |
| 18 | 72 | $576 | 0.69 | 0.91 | 0.98 |
| 20 | 80 | $640 | 0.74 | 0.93 | 0.99 |

Regenerate this table with `uv run python power_sim2.py` (seed 20260917); it is printed verbatim at the end of that run. Cell values move by about a point between runs at these simulation counts — the design choice does not turn on that margin.

Three findings that set the design:

1. **Base videos buy power; impressions do not.** Moving from 750 to 2,000 impressions per clip changes power by 1 to 3 points while nearly tripling cost. Measurement noise is not the limit.
2. **The continuous test beats the rank test everywhere.** At 15 bases and rho 0.4, 0.87 against 0.66. Ranks discard too much.
3. **Ten bases can only rule out a large effect.** Since the existing literature points to small effects, a null at 10 bases would repeat the mistake this study exists to fix.

**Chosen design: 18 base videos, 4 variants each, 72 clips, 1,000 impressions per clip.** That detects a moderate effect (rho 0.4) with 90% power and costs about $580.

If the result lands with rho near 0.3, the study is underpowered by design and the verdict is INCONCLUSIVE, not a null. That branch is priced: 24 bases would be needed for 80% power at rho 0.3.

## 9. Exclusions, fixed in advance

- A clip that delivers **below 750 impressions — 75% of the 1,000 bought** — excludes its whole base from the primary analysis. This is a delivery-shortfall guard, not a floor on the buy: it fires when the platform under-delivers against the registered spend, and it is set below the buy so a design that is delivered as ordered is never excluded by it. (Corrected 2026-09-17, pre-data: this previously read "below 1,500 impressions", which exceeded the 1,000-per-clip buy and would have excluded every base.)
- A variant rejected by ad review excludes its whole base. Rejections are reported.
- If impressions differ by more than 20% across the variants of a base, that base is dropped and the imbalance is reported as a delivery failure.
- No ads are relaunched, edited or rebudgeted after results are visible. Results are pulled once, at the end.

## 10. The four verdicts

| Verdict | Condition | What follows |
|---|---|---|
| **GO** | H1 and H2 both clear, negative control clean | Replicate on a fresh set of bases before any product claim |
| **NO-GO** | Both fail | The brain layer adds nothing here. Publish it. The product becomes a content scorer or gets shelved |
| **INCONCLUSIVE** | Mixed, or the minimum detectable effect sits above the bar | One costed re-run at 20 bases, or stop. No claim either way |
| **INSTRUMENT FAILURE** | Delivery diagnostics fail, or the negative control clears the bar | Fix the instrument, report the failure, re-run once |

## 11. What we may and may not say afterward

**Permitted after GO, single study:** "In one pre-registered test of 18 short videos with 4 openings each, adding predicted cortical response improved prediction of 3-second view rate over a content-only model by ΔR² = X, 95% CI [a, b], on Instagram Reels in the United States." Effect size, interval and population travel with every statement.

**Permitted after NO-GO:** "Predicted cortical response added nothing beyond content features for early retention in this setting."

**Prohibited regardless of outcome:** virality prediction, "predicts performance," audience-specific attention, anything implying a customer's future results, and any commercial use of TRIBE v2 outputs.

## 12. Freeze record

Filled in at freeze time, before any ad spend:

- Frozen commit SHA: ______  Tag: ______  Date and time: ______
- Feature file hash (all 72 clips scored): ______
- Analysis script hash: ______
- OSF registration URL: ______

Any deviation after this point is logged below with the date, what changed and why, and appears in the write-up.

## 13. Budget, timeline, roles

- Ad spend: about $580 for 72 clips at 1,000 impressions each at an $8 CPM. Plan $700 with a $200 reserve, since Reels CPM varies.
- GPU scoring: about $30 to $80.
- Timeline: stimuli produced, then scoring and freeze in one day, ads run 4 days, one data pull, analysis and write-up in about two weeks.
- Roles: Lucas produces stimuli and grants written permission. Ben runs scoring, delivery, analysis and the write-up.

## 14. Publication

A preprint goes up whichever way the result lands, together with the evaluation harness, the frozen features and the analysis code. A null is the deliverable in that case, and it is worth publishing because only one negative result exists in this area so far.

## 15. Ethics

Creator clips are used with written permission and may be withdrawn before publication. No personal data about viewers is collected; only platform-level aggregates. Ads comply with platform policy and avoid restricted categories. Nothing here is a commercial product test.
