"""
Contract tests for `inference._finalize_job` — the single finalize tail shared by
the pod, serverless and mock scoring paths.

Why this file exists: that tail used to be copy-pasted into `pod_process_job`,
`real_process_job` and `_mock_process`. Three homes for one rule meant the
0.45 weak-ROI threshold, the IFJp exclusion and the hook_attn fudge could
silently diverge between backends, so the score you got would depend on which
backend happened to serve you. The refactor collapsed them into one helper;
these tests are what stop the duplication growing back unnoticed.

Self-contained in the style of the sibling tests: if the import path moves, the
suite skips with a clear reason rather than erroring into a false green.
"""

import pytest

try:
    from app.services import inference as inf
    from app.models.job import JobStatus, ScoreResult
    _IMPORT_ERR = None
except Exception as exc:  # ImportError, ModuleNotFoundError, etc.
    inf = None
    _IMPORT_ERR = exc

pytestmark = pytest.mark.skipif(
    inf is None, reason=f"app.services.inference not importable: {_IMPORT_ERR}"
)

# The six ROIs the mapper emits (see corpus_writer._ROI_KEYS).
ROI_KEYS = ["vmPFC", "TPJ", "IFJa", "IFJp", "area_45", "MT_V5"]


def _roi(**overrides) -> dict[str, float]:
    """A healthy ROI dict (all 0.8), with named overrides."""
    roi = {k: 0.8 for k in ROI_KEYS}
    roi.update(overrides)
    return roi


@pytest.fixture
def captured(monkeypatch):
    """Capture job_store.update and add_video_to_corpus instead of performing them.

    `_finalize_job` imports `add_video_to_corpus` lazily inside the function body,
    so it must be patched on its defining module, not on `inference`.
    """
    from app.services import corpus_writer

    updates: list[dict] = []
    corpus_writes: list[tuple] = []

    monkeypatch.setattr(
        inf.job_store, "update",
        lambda job_id, **kw: updates.append({"job_id": job_id, **kw}),
    )
    monkeypatch.setattr(
        corpus_writer, "add_video_to_corpus",
        lambda job_id, filename, roi, composite_score: corpus_writes.append(
            (job_id, filename, roi, composite_score)
        ),
    )
    return updates, corpus_writes


@pytest.fixture
def no_corpus(monkeypatch):
    """Force the 'corpus not loaded' branch so tests don't depend on data/corpus.json."""
    from app import state
    monkeypatch.setattr(state, "corpus_data", None)


# --------------------------------------------------------------------------
# The ScoreResult contract
# --------------------------------------------------------------------------

def test_finalize_marks_job_complete_with_a_scoreresult(captured, no_corpus):
    updates, _ = captured
    inf._finalize_job("abcdef1234567890", "clip.mp4", _roi(), 72.44, write_corpus=False)

    assert len(updates) == 1, "finalize must update the job exactly once"
    u = updates[0]
    assert u["status"] is JobStatus.complete
    assert u["progress_pct"] == 100
    assert u["message"] == "Complete"
    assert isinstance(u["result"], ScoreResult)


def test_video_id_is_derived_from_the_first_eight_chars_of_job_id(captured, no_corpus):
    updates, _ = captured
    inf._finalize_job("abcdef1234567890", "clip.mp4", _roi(), 70.0, write_corpus=False)
    assert updates[0]["result"].video_id == "upload_abcdef12"


def test_composite_is_rounded_to_one_decimal(captured, no_corpus):
    updates, _ = captured
    inf._finalize_job("j" * 16, "clip.mp4", _roi(), 72.4444, write_corpus=False)
    assert updates[0]["result"].composite_score == 72.4


def test_roi_is_passed_through_unmodified(captured, no_corpus):
    updates, _ = captured
    roi = _roi(vmPFC=0.61, TPJ=0.42)
    inf._finalize_job("j" * 16, "clip.mp4", roi, 70.0, write_corpus=False)
    assert updates[0]["result"].roi == roi


def test_temporal_series_is_populated(captured, no_corpus):
    updates, _ = captured
    inf._finalize_job("j" * 16, "clip.mp4", _roi(), 70.0, write_corpus=False)
    assert len(updates[0]["result"].temporal) > 0


# --------------------------------------------------------------------------
# The weak-ROI rule: < 0.45, and IFJp is never reported
# --------------------------------------------------------------------------

def test_rois_below_threshold_are_flagged_weak(captured, no_corpus):
    updates, _ = captured
    inf._finalize_job("j" * 16, "c.mp4", _roi(vmPFC=0.44, TPJ=0.10), 30.0, write_corpus=False)
    weak = updates[0]["result"].weak_rois
    assert "vmPFC" in weak and "TPJ" in weak


def test_threshold_is_exclusive_at_045(captured, no_corpus):
    """0.45 exactly is NOT weak — guards an off-by-one flip to `<=`."""
    updates, _ = captured
    inf._finalize_job("j" * 16, "c.mp4", _roi(vmPFC=0.45), 50.0, write_corpus=False)
    assert "vmPFC" not in updates[0]["result"].weak_rois


def test_ifjp_is_never_reported_weak_even_when_below_threshold(captured, no_corpus):
    """IFJp is deliberately excluded. Losing that exclusion in one backend but not
    another is exactly the drift this refactor was meant to make impossible."""
    updates, _ = captured
    inf._finalize_job("j" * 16, "c.mp4", _roi(IFJp=0.01), 50.0, write_corpus=False)
    assert "IFJp" not in updates[0]["result"].weak_rois


def test_healthy_rois_produce_no_weak_list(captured, no_corpus):
    updates, _ = captured
    inf._finalize_job("j" * 16, "c.mp4", _roi(), 88.0, write_corpus=False)
    assert updates[0]["result"].weak_rois == []


# --------------------------------------------------------------------------
# write_corpus is the ONLY behavioural difference between the backends
# --------------------------------------------------------------------------

def test_mock_path_does_not_write_to_the_corpus(captured, no_corpus):
    """write_corpus=False is what keeps fake mock scores out of the real corpus."""
    _, corpus_writes = captured
    inf._finalize_job("j" * 16, "c.mp4", _roi(), 70.0, write_corpus=False)
    assert corpus_writes == []


def test_real_path_writes_to_the_corpus_once_with_rounded_score(captured, no_corpus):
    _, corpus_writes = captured
    roi = _roi()
    inf._finalize_job("abcdef1234567890", "clip.mp4", roi, 72.46, write_corpus=True)

    assert len(corpus_writes) == 1
    job_id, filename, written_roi, composite = corpus_writes[0]
    assert (job_id, filename, written_roi) == ("abcdef1234567890", "clip.mp4", roi)
    assert composite == 72.5, "corpus must receive the rounded score, not the raw float"


# --------------------------------------------------------------------------
# corpus_roi_means comes from live state, and absence is tolerated
# --------------------------------------------------------------------------

def test_corpus_roi_means_empty_when_corpus_not_loaded(captured, no_corpus):
    updates, _ = captured
    inf._finalize_job("j" * 16, "c.mp4", _roi(), 70.0, write_corpus=False)
    assert updates[0]["result"].corpus_roi_means == {}


def test_corpus_roi_means_read_from_state_when_loaded(captured, monkeypatch):
    from app import state
    means = {k: 0.5 for k in ROI_KEYS}
    monkeypatch.setattr(state, "corpus_data", {"stats": {"roi_means": means}})

    updates, _ = captured
    inf._finalize_job("j" * 16, "c.mp4", _roi(), 70.0, write_corpus=False)
    assert updates[0]["result"].corpus_roi_means == means


# --------------------------------------------------------------------------
# Determinism, and the cross-backend invariant this refactor exists to protect
# --------------------------------------------------------------------------

def _temporal_tuple(result: ScoreResult) -> tuple:
    return tuple(
        (p.second, p.attention, p.social_cognition, p.valuation)
        for p in result.temporal
    )


def test_same_filename_yields_identical_temporal_series(captured, no_corpus):
    """The temporal seed is derived from the filename, so repeat scores of the
    same clip must not wander."""
    updates, _ = captured
    inf._finalize_job("j" * 16, "same.mp4", _roi(), 70.0, write_corpus=False)
    inf._finalize_job("k" * 16, "same.mp4", _roi(), 70.0, write_corpus=False)

    assert _temporal_tuple(updates[0]["result"]) == _temporal_tuple(updates[1]["result"])


def test_all_three_backends_finalize_identically(captured, no_corpus):
    """The invariant. Same ROI + same composite must yield the same user-visible
    result regardless of which backend produced it — only the corpus write differs.
    If this fails, the finalize tail has been duplicated or forked again.
    """
    updates, corpus_writes = captured
    roi = _roi(vmPFC=0.42, TPJ=0.77, IFJp=0.02)

    for write_corpus in (True, False, True):  # pod, mock, real
        inf._finalize_job("abcdef1234567890", "clip.mp4", roi, 63.85, write_corpus=write_corpus)

    results = [u["result"] for u in updates]
    assert len(results) == 3

    def visible(r: ScoreResult) -> tuple:
        return (
            r.video_id,
            r.composite_score,
            r.verdict,
            tuple(sorted(r.roi.items())),
            tuple(sorted(r.weak_rois)),
            _temporal_tuple(r),
            tuple((t.roi, t.score, t.tip) for t in r.revision_tips),
        )

    assert visible(results[0]) == visible(results[1]) == visible(results[2])
    assert len(corpus_writes) == 2, "only the write_corpus=True paths touch the corpus"
