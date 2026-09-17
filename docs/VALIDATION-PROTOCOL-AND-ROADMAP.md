# TRIBE v2 — Hardened Incremental-Validity Validation Protocol & Staged Roadmap
**Version 2.0 · 2026-05-28**

---

## 1. EXECUTIVE SUMMARY

For roughly $500–700 in compute and ~14–16 weeks, this protocol runs a pre-registered, prospective study that settles **one** question — does TRIBE's predicted cortical attention signal add real, incremental predictive value over a strong modern content baseline (VideoLLaMA2 + audio) for content-driven watch-time retention — using a corpus of **~250–320 YouTube Shorts from ~30–35 small (≤50k) creators**, scored blind, with the brain layer tested against an early-window retention metric, a backbone-embedding negative control, and a positive control, under creator-grouped nested cross-validation with a *conditional* (residual) permutation test. The study is deliberately gated behind a prior licensing feasibility check, since TRIBE v2's CC-BY-NC terms constrain what any positive result could be used for. The validation study returns one of four pre-committed verdicts — GO, content-pivot NO-GO, instrument-failure, or INDETERMINATE — and clears at most an FTC Claim-Level-2 (directional, single-study, effect-size-disclosed) ceiling that only **replication** can raise. A GO licenses a narrow, honest claim about within-creator retention, not a virality or audience-attention claim.

**The single most important caveat:** a clean GO establishes a narrow statistical result, not a mandate to build on it. Incremental validity is one constraint among several — licensing is another, and it is both cheaper and faster to test. A positive ΔR² is worth little if the model's license forbids the use you had in mind.

---

## 2. THE HARDENED VALIDATION PROTOCOL

### 2.0 What it exists to settle
Does TRIBE's BOLD-prediction head add incremental out-of-sample predictive value **over a same-backbone content baseline**, for a **content-driven early-retention** outcome, with the algorithm/follower/niche confounds controlled — and is that increment attributable to the *brain head* rather than to generic representational richness? The whole design is built so a "no" is as credible and publishable as a "yes."

### 2.1 Pre-registered hypotheses
Three nested models, identical corpus, identical creator-grouped folds:
- **Model A — Content baseline:** VideoLLaMA2 (8 keyframes + audio + transcript) → PCA-in-fold → ridge. Pre-committed as primary so it cannot be called sandbagged; CLIP-L/14 + VideoMAE-v2 + CLAP + Whisper-large-v3 fallback is named in the pre-reg (non-sandbagging) and becomes default if VideoLLaMA2 setup exceeds ~2 days.
- **Model B — Brain only:** TRIBE features → PCA-in-fold → ridge. Diagnostic.
- **Model C — Combined:** A ⊕ B → ridge. **C vs A is decisive.**
- **Model N — Negative control:** A ⊕ (raw V-JEPA2/VideoMAE backbone PCs, dimension-matched to B). Pre-registered. *(Causal-lens S4.)*
- **Positive control:** a feature known to track retention (first-second motion energy, loudness, hook-cut density) entered alone, to prove the outcome metric can detect a real signal. *(Decision-lens Obj 3.)*

**H1 (PRIMARY, confirmatory, one-tailed).** ΔR²(C−A) > 0 on the primary outcome, evaluated by creator-grouped nested CV. **Bars: ΔR² ≥ 0.03 AND conditional-permutation p < 0.05 AND the creator-block bootstrap 95% lower bound > 0.**
**H1-NC (PRIMARY gate, new).** ΔR²(C−A) must **exceed** ΔR²(N−A) by a pre-registered margin. If the backbone negative control adds as much as TRIBE, H1 is **not** a neuroscience result and GO is denied regardless of H1. *(Causal S4 — load-bearing.)*
**H2 (PRIMARY, confirmatory).** Model B tracks the primary outcome: creator-clustered Spearman ρ ≥ 0.20, permutation p < 0.05 (one-tailed), powered for an effect *at* the attenuation ceiling, not above it.
**H3 (SECONDARY).** H1 increment survives adding log(follower_count) + creator-tier to A. BH-FDR.
**H4 (EXPLORATORY).** Modality ablation (video/audio/transcript). No inferential weight; drives the creative brief, never the gate.
**H5 (EXPLORATORY).** Niche-conditional increment. Effect heterogeneity only; never confirmatory.
**Kill hypothesis (explicit):** ΔR² < 0.03 OR p ≥ 0.05 OR ΔR²(C−A) ≤ ΔR²(N−A) → H1 not supported → NO-GO on the neuroscience thesis.

### 2.2 Why incremental validity, not raw correlation
TRIBE's video backbone is the *same representational family* as the content baseline's. Any raw TRIBE↔retention correlation is mostly shared content variance. The only defensible question is what the BOLD head adds **after** content has extracted everything from the same frames/audio/transcript — i.e., ΔR²(C−A). The negative control (H1-NC) closes the remaining loophole: "any 3–5 PCs from a rich same-backbone embedding would add this much." This is the analysis that defeats "you're just re-detecting CLIP through a brain-shaped lens."

### 2.3 Design — prospective, cold-start, confound-controlled
- **Platform:** YouTube Shorts only for the confirmatory tier (native retention curve via OAuth Analytics API). TikTok only for a robustness subset; no Reels pooling.
- **Creators (the binding resource):** recruit **35–40**, target **~30–35 analyzable**, **≥5 videos each** (not 8 — decouples N from cadence; ≥4–5 suffices for normalization). ≤50k followers for the confirmatory tier. **Week-3 kill-gate: <20 committed creators → descope to exploratory before any GPU spend.** *(Feasibility Obj 1/4 — fatal-as-written, now fixed.)*
- **Niches:** **4** (not 5–6), ≥4 creators each, so cells survive attrition; niche collapses to a high/low-stimulus binary if any niche drops below 3 creators. Mid-tier (50k–500k) arm deferred entirely to a post-GO stage. *(Feasibility Obj 5.)*

### 2.4 Sample & power — re-derived, simulation-based
The original analytic calc was **wrong and unconservative** (statistical-lens F1, conceded valid): f² for an incremental test = ΔR²/(1−R²_full) ≈ 0.053, which needs ~230–240 under an in-sample F-test — and the actual instrument is permuted *nested-CV* ΔR², which has **no closed-form power** and is noisier. The effective unit is **creators (~30), not videos (~300)** because of GroupKFold + within-creator normalization (statistical-lens S1/S3, causal-lens, valid).
**Fix (binding, pre-freeze):** frozen **simulation-based power analysis** — simulate ~30–35 creators × ~6–9 videos with creator-level random intercepts, R²_A taken from the pilot (not assumed at 0.20; M2), true ΔR² ∈ {0.02–0.05}, run the *exact* frozen pipeline, set N so empirical power ≥ 0.80 at true ΔR²=0.04. Expected landing: **~250–320 videos / ~30–35 creators.** Report the minimum-detectable-ΔR² and confirm it is ≤ 0.03 so both bars are active (S2). Power H2 the same way (clustered). Below the simulated confirmatory floor → relabel exploratory.

### 2.5 Confound controls, outcome metric & collection
- **Primary outcome (changed):** an **early-retention fraction** — 3s/5s survival on the first-cohort/first 6–12h window — not full-video Average % Viewed. This matches TRIBE's onset (first-3s) feature window *and* minimizes algorithmic re-routing contamination. *(Causal F1/S1, decision Obj-aligned — load-bearing; the original predictor↔outcome window mismatch was a real flaw.)* Full-video APV demoted to secondary.
- **Algorithm-mediation control:** the ≤50k clamp controls *seeding scale*, not *served-audience composition*. Add **traffic-source split (Shorts feed vs browse vs subscriptions) and subscriber/non-subscriber share as covariates**; capture the **whole retention curve**, not just a scalar. *(Causal F1 — valid; cold-start does not remove the recommender, it makes it do more work.)*
- **Normalization (changed):** drop the self-including ratio (it induces mechanical negative dependence and strips the most stable between-creator signal). Use a **mixed model with creator random intercept** on the raw early-retention metric, or a **leave-self-out** creator mean. **Pre-register both the within-creator and between-creator estimands as distinct, separately-powered tests, and state which one the product claim rests on.** *(Causal F2 — valid, changes what is being claimed.)*
- **Niche partialled inside all three models** (A, B, C) before ΔR² — plus a **niche-orthogonalized TRIBE** robustness arm and a **within-niche/within-creator co-primary**, so a positive ΔR² cannot be niche-detection masquerading as brain. *(Causal F3 — valid; the average-brain model is exactly the thing that captures coarse category-level salience.)*
- **Closed covariate set, frozen pre-collection:** log(follower), duration + 15–30/30–60s strata, posting hour (cyclical), niche, traffic-source, platform. No covariate added after collection starts.
- **Exclusions:** impression floor **re-derived from pilot to exclude ≤10% of corpus** (pre-register the exclusion-rate cap, not the raw 500 number — the 500 floor was non-random selection on the low-outcome tail). Exclude paid-promoted, duets/stitches, deletions, cross-posts; report whether excluded videos differ in TRIBE score.

### 2.6 Feature pipelines (frozen)
- **TRIBE ROIs (theory-anchored, no hand weights):** NAcc + anterior insula (Tong/Berns onset anchor; flagged low-fidelity subcortical) **plus STS + DMN/mPFC cortical parcels** (Chan 2024 social-cognition signal) as co-primary. Explicitly stated: this **extends** Tong/Berns to cortex, it does not replicate it. *(Causal N3.)*
- **Window:** first 3s (onset), mean across frames. Full-video = Bonferroni secondary.
- **Dimensionality:** PCA on TRIBE vertex outputs → **top-K by variance (K fixed a priori, e.g. smallest K explaining ≥80% pilot variance), fit inside the outer training fold only.** No component is *selected* on the pilot; only the rule is frozen. No hand-tuned weights anywhere. *(Statistical S5, ethics S5.)*
- **Pilot (20–30 videos, creators disjoint from main corpus):** freezes only integer K, ROI list, window, and the pilot R²_A feeding the power sim. Discarded, never reused.

### 2.7 Analysis plan
- **CV:** leave-one-creator-out (or ≥15 folds), GroupKFold by creator; inner 5-fold for ridge α and K. **All PCA fit inside the outer training fold only** (Varoquaux; >20% inflation otherwise). Negative-fold ΔR² kept and averaged (pre-stated). *(M1.)*
- **Inference (changed):** **conditional/residual permutation** — regress out A, permute the A-residualized outcome against the brain block within creator×niche×duration strata, recompute nested-CV ΔR² 5,000×. This tests the *correct* null ("B adds nothing beyond A"), not the easier "nothing predicts anything" null that over-rejects H1. Add a **creator-block bootstrap CI on ΔR²** (resample creators); require lower 95% bound > 0. *(Statistical F2 — valid and load-bearing; original outcome-shuffle tested the wrong, easier null. Restricted strata also fixes causal S5.)* Note that ~30 creator blocks govern permutation granularity, not the 5,000 draws (M3).
- **Multiplicity:** primary = H1 + H1-NC + H2. Secondary (H3, ECR, ER) BH-FDR. **The GO/NO-GO tree reads ONLY the primary-window, primary-outcome H1/H1-NC/H2 statistics; no §robustness result can upgrade or downgrade the gate.** *(Statistical S4 — closes the robustness-battery forking path.)*
- **Robustness battery (diagnostic, cannot move the gate):** H3; raw vs normalized; onset vs full-video (Bonferroni); impression-floor sensitivity; positive-control check.

### 2.8 GO / NO-GO — set before data

| Verdict | Condition | Action |
|---|---|---|
| **GO** | ΔR²(C−A) ≥ 0.03 AND perm p<0.05 AND bootstrap LB>0 AND ΔR²(C−A) > ΔR²(N−A)+margin AND survives H3 AND positive-control detected | Brain layer real, additive, and not generic-embedding. Proceed to Stage 1 **replication** (not product). Quote full stats + CIs. |
| **NO-GO (content pivot)** | H1 fails BUT R²_A meaningful (pilot-calibrated, p<0.05) | Neuroscience thesis dead. Pure content-scorer is itself a real result; drop all neuro framing and report the null on the neural increment. |
| **INDETERMINATE (new)** | 90% CI on ΔR² spans 0.03 (e.g. [−0.01, 0.07]) OR positive control undetected | One pre-committed confirmatory re-run at the simulated higher N, **or STOP** if infeasible. Do not declare a brain result. *(Decision Obj 3 — valid; this is the most probable outcome given ceiling+clustering, and must be a planned, costed branch.)* |
| **INSTRUMENT FAILURE** | R²_A and R²_C both near zero AND positive control undetected | Outcome too noisy / over-normalized. Redesign before any claim. Must be published too (no hiding unfavorable results here). *(Ethics M3.)* |

Hard rule: GO requires the **increment over A and over the negative control**, not merely a significant B. A significant B with no increment = redundant with content = NO-GO.

### 2.9 Ethics / FTC / credibility hardening (blocking, pre-freeze)
- **Human-subjects & data governance (new Section):** independent IRB review (~$1–2k, also unlocks arXiv/ICWSM/CHI publishability) **or** documented exemption; written informed consent naming model-scoring, feature storage, retention + deletion-on-request, and aggregate-only publication; explicit YouTube API ToS compliance (OAuth, honor retention/deletion, flag that this data is not freely repurposable for the later product). *(Ethics F1 — valid, blocking; $0 budget here was the tell it was skipped.)*
- **Verifiable blinding (new):** replace self-administered hash with a third-party-timestamped sequence on OSF — freeze analysis code → freeze features → seal + hash outcomes → run frozen code once. Analytics pulled programmatically only after the hash file exists. Acknowledge primary outcome (early-retention) is OAuth-gated and not publicly visible (a genuine defense), while raw view counts are. *(Ethics F2 — valid; solo-operator blind is otherwise unfalsifiable.)*
- **OAuth at scale (feasibility Obj 2):** build the Google Cloud app + consent screen in Phase 0; start Google verification early or cap confirmatory tier under the unverified-user ceiling; API-pulled analytics only, no screenshots in the confirmatory set.
- **Approved-claims appendix (new):** write the exact permitted and prohibited sentences. Permitted (post-replication only): "predicts a cortical attention/salience pattern; in prospective studies this added a small increment (ΔR²≈X, 95% CI …) in early watch-time retention over a content baseline, on ≤50k-follower Shorts." Prohibited forever: virality prediction, audience-specific attention, manipulation/persuasion detection, anything tying the diagnostic to the customer's future performance. Effect size + CI + population limits must travel with every claim. *(Ethics F3/S1/S2 — valid; single-study ΔR²=0.03 cannot substantiate an implied efficacy claim under "competent and reliable scientific evidence.")*
- **COI + publication commitment:** OSF-registered dissemination clause (publish GO, NO-GO, and instrument-failure); mandatory COI disclosure; advisor/PI named and reviewing **before** freeze (after-the-fact co-authorship reads as credibility-laundering). *(Ethics S3/S6/M4.)*

### 2.10 Objections I judged INVALID or over-weighted (intellectual honesty)
- **"Move the ΔR² bar up for commercial significance" — partially rejected as stated.** Decision-lens Obj 2 is right that a 3% statistical increment may be commercially trivial, but you must **not** raise the pre-registered statistical threshold (post-hoc bar-moving is worse than the disease). The correct fix is **additive**: keep ΔR²≥0.03 as the scientific gate and add a *separate* commercial-significance check (precision@k / NDCG on the retention ranking; decision-concordance: does acting on the brief flip held-out rankings A alone wouldn't). GO-science and GO-commercial are two stamps, not one moved threshold.
- **"Incumbent-class comparator inside the study" — accepted but demoted.** Decision Obj 4 is valid that beating your own Model A ≠ beating a $29 saliency tool or zero-shot VideoLLaMA2. But loading an off-the-shelf saliency baseline + zero-shot prompt into the confirmatory pre-reg risks baseline-proliferation and dilutes the one clean test. Add **one** zero-shot incumbent-class baseline as a *reported secondary*, and make "beats the cheapest adequate incumbent" a **Stage-1/demand-gate** question, not a confirmatory-study gate.
- **Subcortical-to-cortical ROI shift "abandons the anchor" — noted, not a flaw.** Causal N3 is a fair caveat, handled by stating plainly that we extend Tong/Berns to cortex (where TRIBE is high-fidelity) rather than replicate their NAcc/insula result (where TRIBE is weakest). Keeping NAcc/insula as co-primary preserves the anchor honestly.

---

## 3. UNRESOLVED RISKS — what a perfect study does NOT fix

1. **The license is a hard, independent kill switch.** TRIBE v2 is CC-BY-NC. No commercial launch is legal on v2 weights as-is. A perfect GO is worthless if FAIR won't license commercially and no permissive substitute (CONFORM / Nature-2025 foundation model / Algonauts v1 terms) exists. This is gated *before* the study (Section 5).
2. **No moat / Meta vertical integration.** TRIBE is Meta's public model; Meta owns Reels and the engagement ground truth and could do this natively and better. Even a validated, licensed, differentiated tool sits in the blast radius of the one company that owns both the model lineage and the outcome data. The study cannot fix this; only a defensible niche, proprietary outcome data, or speed can.
3. **Average-brain ceiling is structural, not a bug to be fixed.** TRIBE predicts the *average* cortical response. Virality is a social-graph/tail phenomenon and resonance is audience-specific; an average-subject model is structurally blind to both. The attention pivot narrows the claim to a population-average *stimulus property* — which is honest and defensible, but permanently narrower than what a buyer hears in "neural attention diagnostics." The gap lives in the claim layer forever and must be policed by the claims appendix.
4. **The effect is theoretically small (r≈0.20–0.26 ceiling).** Even a true GO yields a brain layer explaining single-digit incremental variance. That can be real science and still too weak to change a creative decision — which is exactly why the commercial-significance check (precision@k / decision-concordance) is separate from the statistical gate.
5. **Cold-start trust loop.** You need real outcomes to earn trust and trust to get outcomes; the study bootstraps a first corpus but does not solve the ongoing supply of proprietary outcome data that a durable product needs.
6. **Actionability gap.** A score is not a creative decision. Only the modality-ablation brief (H4, exploratory) gestures at closing it; that has no confirmatory weight and is a product-design problem the study leaves open.
7. **Opportunity cost.** Every week spent here is a week not spent on work with a clearer path. The cheapest-test-first sequencing exists precisely to make an early stop cheap.

How to think about them: items 1, 2, 7 are **constraints the study cannot touch** and must be worked in parallel or first; items 3, 4 are **permanent claim-ceiling constraints** to be lived with honestly; items 5, 6 are **downstream problems** that only matter given a GO.

---

---

## 4. WHAT A RESULT WOULD AND WOULD NOT LICENSE

The verdict tree in §2.8 returns one of four outcomes. What each permits:

- **GO** — a narrow, directional claim about within-creator early retention on ≤50k-follower Shorts, carrying its effect size, CI, and population limits. It does **not** license a virality claim, an audience-specific attention claim, or any manipulation/persuasion framing. Under the §2.9 claims appendix those are prohibited permanently, not pending more data. A single study reaches at most an FTC Claim-Level-2 ceiling; only independent replication raises it.
- **Content-pivot NO-GO** — the content baseline (Model A) is itself a real result. The correct response is to report the null on the neural increment plainly and, if the content model is useful, treat it as its own artifact with all neuro framing dropped.
- **INSTRUMENT FAILURE** — the outcome metric could not detect the positive control. Fix the metric, publish the failure, re-run the gate once.
- **INDETERMINATE** — one costed confirmatory re-run at the higher simulated N, or stop. Do not treat an indeterminate result as a weak GO.

A null here is a publishable contribution. The design exists so that "no" is as credible as "yes," and the 24-video pilot plus arXiv:2607.01400 both currently point that direction.
