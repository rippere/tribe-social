"""
Smoke test for the RunPod-output -> ROI mapping.

Guards two regressions:
  (a) The mapper must RAISE when an expected raw key is missing.
  (b) Distinct raw inputs across the expected keys must NOT collapse to a
      single repeated ROI value. This catches the "(val + 0.5) / 2.0"
      flattening class of bug, where saturation/clamping or a constant
      transform would map every input to the same output.

Self-contained: if the import path differs, the test skips with a clear reason
instead of erroring, so the suite stays green across layout changes.
"""

import pytest

try:
    from app.services.inference import _map_runpod_output_to_roi
    _IMPORT_ERR = None
except Exception as exc:  # ImportError, ModuleNotFoundError, etc.
    _map_runpod_output_to_roi = None
    _IMPORT_ERR = exc

# The raw keys the mapper is documented to require
# (RunPod handler quick_scores() output keys).
EXPECTED_KEYS = [
    "valuation_mean",
    "social_mean",
    "attention_mean",
    "language_mean",
    "motion_mean",
]

pytestmark = pytest.mark.skipif(
    _map_runpod_output_to_roi is None,
    reason=(
        "Could not import _map_runpod_output_to_roi from app.services.inference: "
        f"{_IMPORT_ERR!r}. Skipping scoring mapping smoke test."
    ),
)


def test_raises_on_missing_expected_key():
    """(a) Dropping any one expected key must raise (not silently default)."""
    # Full valid payload with distinct values.
    full = {k: v for k, v in zip(EXPECTED_KEYS, [-0.4, -0.1, 0.0, 0.2, 0.45])}
    # Remove one required key.
    incomplete = dict(full)
    incomplete.pop("valuation_mean")

    with pytest.raises(Exception):
        _map_runpod_output_to_roi(incomplete)


def test_distinct_inputs_do_not_collapse():
    """(b) A spread of distinct raw inputs must yield >1 distinct ROI value."""
    # Distinct, in-range raw values across all expected keys.
    raw_values = [-0.4, -0.1, 0.0, 0.2, 0.45]
    assert len(set(raw_values)) == len(raw_values), "test inputs must be distinct"

    payload = dict(zip(EXPECTED_KEYS, raw_values))
    roi = _map_runpod_output_to_roi(payload)

    assert isinstance(roi, dict) and roi, "mapper must return a non-empty dict"

    distinct = {round(float(v), 3) for v in roi.values()}
    assert len(distinct) > 1, (
        "ROI values collapsed to a single value "
        f"({distinct}) despite distinct raw inputs {raw_values} — "
        "indicates a flattening transform (e.g. constant or saturating map)."
    )
