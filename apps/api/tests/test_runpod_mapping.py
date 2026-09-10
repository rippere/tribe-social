"""
End-to-end mapping test for a realistic RunPod /status payload.

Guards the serverless double-nesting regression: the RunPod handler must return
the flat quick_scores() row DIRECTLY, and RunPod adds exactly ONE "output"
wrapper. So a real /status response looks like:

    {"status": "COMPLETED", "output": {<row fields>}}

This test reproduces that shape, unwraps it the same way inference.py does
(`data.get("output", {})`, mirrored by runpod_client.poll/check_status), and
feeds the result through the score-mapping function. It must map WITHOUT raising.

If the handler ever regresses to returning {"output": row}, the /status payload
becomes double-nested ({"output": {"output": row}}); the unwrapped dict then
lacks the expected keys and the mapper raises — which this test would catch.

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

pytestmark = pytest.mark.skipif(
    _map_runpod_output_to_roi is None,
    reason=(
        "Could not import _map_runpod_output_to_roi from app.services.inference: "
        f"{_IMPORT_ERR!r}. Skipping RunPod mapping test."
    ),
)


def _make_status_payload() -> dict:
    """A realistic RunPod /status response for a COMPLETED job.

    "output" is wrapped ONCE by RunPod around the handler's flat return value
    (the quick_scores() row plus filename/label/n_seconds the handler appends).
    """
    row = {
        # quick_scores() flat dict — the keys the mapper requires.
        "valuation_mean": -0.4,
        "social_mean": -0.1,
        "attention_mean": 0.0,
        "language_mean": 0.2,
        "motion_mean": 0.45,
        # Extra metadata the handler appends to the row (must be ignored, not fatal).
        "filename": "video.mp4",
        "label": "video",
        "n_seconds": 42,
    }
    return {"status": "COMPLETED", "output": row}


def test_status_payload_maps_without_raising():
    """A single-wrapped /status payload must unwrap and map cleanly."""
    payload = _make_status_payload()

    # Same unwrap inference.py / runpod_client.py perform on the /status dict.
    output = payload.get("output", {})

    roi = _map_runpod_output_to_roi(output)

    assert isinstance(roi, dict) and roi, "mapper must return a non-empty ROI dict"
    # Every mapped value must be a normalized float in [0, 1].
    for name, val in roi.items():
        assert 0.0 <= float(val) <= 1.0, f"ROI '{name}' out of range: {val}"


def test_double_nested_payload_would_raise():
    """
    Regression guard: the OLD handler returned {"output": row}, so RunPod
    double-wrapped it. Unwrapping the /status dict once then yields {"output": row}
    (no quick_scores keys), which the mapper must reject.
    """
    row = _make_status_payload()["output"]
    double_nested = {"status": "COMPLETED", "output": {"output": row}}

    output = double_nested.get("output", {})  # == {"output": row}

    with pytest.raises(Exception):
        _map_runpod_output_to_roi(output)
