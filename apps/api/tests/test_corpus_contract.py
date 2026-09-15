"""Contract tests for the /corpus response shape + the shared composite helpers.

Guards the regression where CorpusVideo silently dropped `verdict`
(Pydantic extra="ignore") — which no prior test covered — and pins the shared
scale/verdict behavior the refactor centralized in tribe_scoring.composite.

Self-contained: skips with a clear reason if imports differ, so the suite stays
green across layout changes.
"""
import json
from pathlib import Path

import pytest

try:
    from app.models.scores import CorpusVideo, CorpusResponse
    from tribe_scoring.composite import (
        scale_to_100, compute_verdict, POST_THRESHOLD, REVISE_THRESHOLD,
    )
    _ERR = None
except Exception as exc:  # ImportError, etc.
    _ERR = exc

pytestmark = pytest.mark.skipif(_ERR is not None, reason=f"import failed: {_ERR!r}")

_CORPUS = Path(__file__).resolve().parents[1] / "data" / "corpus.json"


def test_corpus_video_round_trips_verdict():
    """Every corpus row must carry a verdict THROUGH the response model
    (regression guard for the extra='ignore' drop)."""
    data = json.loads(_CORPUS.read_text())
    resp = CorpusResponse(videos=[CorpusVideo(**v) for v in data["videos"]])
    dumped = resp.model_dump()
    assert dumped["videos"], "corpus is empty"
    for v in dumped["videos"]:
        assert v["verdict"] in ("POST", "REVISE", "RETHINK"), v


def test_compute_verdict_thresholds():
    assert compute_verdict(POST_THRESHOLD) == "POST"
    assert compute_verdict(POST_THRESHOLD - 0.1) == "REVISE"
    assert compute_verdict(REVISE_THRESHOLD) == "REVISE"
    assert compute_verdict(REVISE_THRESHOLD - 0.1) == "RETHINK"


def test_scale_to_100_bounds():
    assert scale_to_100(5, 0, 10) == 50.0
    assert scale_to_100(-1, 0, 10) == 0.0     # clips low
    assert scale_to_100(99, 0, 10) == 100.0   # clips high
    assert scale_to_100(1, 5, 5) == 0.0       # degenerate range -> 0
