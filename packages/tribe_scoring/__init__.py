"""tribe_scoring — shared TRIBE v2 scoring.

`composite` (weights / thresholds / verdict — dependency-free) is imported
eagerly so it is available on hosts WITHOUT the GPU-only `tribev2` dependency
(the API and the web build). The heavy scorer in `run_and_save` (which needs
tribev2) is imported directly by its GPU-side consumers via
`from tribe_scoring.run_and_save import ...`, and is also exposed lazily here so
`from tribe_scoring import quick_scores` keeps working without importing tribev2
at package-import time.
"""
from .composite import (
    ROI_WEIGHTS, POST_THRESHOLD, REVISE_THRESHOLD,
    compute_composite_raw, scale_to_100, compute_verdict,
)

__all__ = [
    "load_model", "quick_scores", "_BATCH_MASKS",
    "ROI_WEIGHTS", "POST_THRESHOLD", "REVISE_THRESHOLD",
    "compute_composite_raw", "scale_to_100", "compute_verdict",
]


def __getattr__(name):
    # Lazy: only import the tribev2-dependent scorer when actually accessed.
    if name in ("load_model", "quick_scores", "_BATCH_MASKS"):
        from . import run_and_save
        return getattr(run_and_save, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
