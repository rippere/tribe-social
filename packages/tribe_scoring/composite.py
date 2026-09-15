"""Single source of truth for the TRIBE composite score, weights, and verdict.

Everything that computes or classifies a composite score imports from here —
the GPU scorer (`run_and_save.py`), the API live-scoring + corpus build, and
(via an API-served config) the web. There is exactly ONE definition of the
weights and thresholds; do not re-declare them anywhere else.
"""
from __future__ import annotations

# 7-ROI composite weights, applied to per-ROI mean activations on the pod.
# Functional ROI names, as emitted by quick_scores().
ROI_WEIGHTS: dict[str, float] = {
    "attention": 0.25,
    "social":    0.30,
    "language":  0.15,
    "valuation": 0.20,
    "auditory":  0.05,
    "motion":    0.03,
    "narrative": 0.02,
}

# Verdict thresholds on the 0-100 composite score.
POST_THRESHOLD:   float = 65.0
REVISE_THRESHOLD: float = 40.0


def compute_composite_raw(roi_means: dict[str, float]) -> float:
    """Weighted sum of per-ROI mean activations — the raw (unscaled) composite."""
    return sum(roi_means.get(dim, 0.0) * w for dim, w in ROI_WEIGHTS.items())


def scale_to_100(composite_raw: float, lo: float, hi: float) -> float:
    """Min-max scale a raw composite onto 0-100 against a [lo, hi] range.

    lo/hi come from the corpus composite_raw range, so a single live clip lands
    on the same scale as the corpus videos. Out-of-range values clip to 0/100.
    """
    if hi <= lo:
        return 0.0
    return max(0.0, min(100.0, (composite_raw - lo) / (hi - lo) * 100.0))


def compute_verdict(score_0_100: float) -> str:
    """POST / REVISE / RETHINK from a 0-100 composite score."""
    if score_0_100 >= POST_THRESHOLD:
        return "POST"
    if score_0_100 >= REVISE_THRESHOLD:
        return "REVISE"
    return "RETHINK"
