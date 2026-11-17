"""Unit tests for the per-second norm band (norms.py), on synthetic timecourses.

Run: uv run --with numpy --with pytest pytest packages/tribe_scoring/tests
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pytest

_spec = importlib.util.spec_from_file_location(
    "_tribe_norms_under_test", Path(__file__).resolve().parents[1] / "norms.py")
norms = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(norms)


def ref_clips(n_clips=40, lengths=None, seed=0):
    rng = np.random.default_rng(seed)
    lengths = lengths or [30] * n_clips
    return [{"gfp": rng.normal(1.0, 0.1, L), "attention": rng.normal(0.0, 0.1, L)} for L in lengths]


def test_timecourses_gfp_and_roi_mean():
    preds = np.zeros((5, 10))
    preds[2, :] = 2.0
    preds[3, [1, 3]] = 4.0
    tc = norms.timecourses(preds, {"roi": np.array([1, 3])})
    assert tc["gfp"][2] == pytest.approx(2.0)
    assert tc["roi"][3] == pytest.approx(4.0)
    assert tc["roi"][2] == pytest.approx(2.0)


def test_band_coverage_stops_where_too_few_clips_reach():
    band = norms.build_band(ref_clips(lengths=[30] * 20 + [12] * 10), name="t", min_n=20)
    assert band["n_seconds"] == 30
    band = norms.build_band(ref_clips(lengths=[30] * 15 + [12] * 15), name="t", min_n=20)
    assert band["n_seconds"] == 12
    assert band["n_per_second"][0] == 30


def test_band_rejects_small_reference_set():
    with pytest.raises(ValueError):
        norms.build_band(ref_clips(n_clips=5), name="t", min_n=20)


def test_percentile_rank_edges_and_ties():
    sv = [1.0, 2.0, 3.0, 4.0]
    assert norms.percentile_rank(0.0, sv) == 0.0
    assert norms.percentile_rank(5.0, sv) == 100.0
    assert norms.percentile_rank(2.0, sv) == pytest.approx(37.5)


def test_diagnose_flags_low_stretch_with_video_time():
    band = norms.build_band(ref_clips(), name="t")
    clip = {"gfp": np.full(30, 1.0), "attention": np.zeros(30)}
    clip["gfp"][10:14] = 0.0                       # far below every reference value
    out = norms.diagnose(clip, band)
    low = [f for f in out["flags"] if f["signal"] == "gfp" and f["direction"] == "low"]
    assert len(low) == 1
    f = low[0]
    assert (f["pred_start_s"], f["pred_end_s"]) == (10, 13)
    assert (f["video_start_s"], f["video_end_s"]) == (10 - norms.LAG_S, 13 - norms.LAG_S)
    assert f["extreme_rank"] == 0.0


def test_diagnose_never_ranks_warmup_or_past_coverage():
    band = norms.build_band(ref_clips(lengths=[20] * 40), name="t")
    clip = {"gfp": np.zeros(30), "attention": np.zeros(30)}
    out = norms.diagnose(clip, band)
    r = out["ranks"]["gfp"]
    assert all(x is None for x in r[: norms.LAG_S])
    assert all(x is None for x in r[20:])
    assert out["ranked_seconds"] == [norms.LAG_S, 19]
    for f in out["flags"]:
        assert f["pred_start_s"] >= norms.LAG_S and f["pred_end_s"] <= 19


def test_diagnose_ignores_single_second_blips():
    band = norms.build_band(ref_clips(), name="t")
    clip = {"gfp": np.full(30, 1.0), "attention": np.zeros(30)}
    clip["gfp"][15] = 0.0
    out = norms.diagnose(clip, band, min_run=2)
    assert not [f for f in out["flags"] if f["signal"] == "gfp"]


def test_band_roundtrip(tmp_path):
    band = norms.build_band(ref_clips(), name="t")
    p = tmp_path / "b.json"
    norms.save_band(band, p)
    assert norms.load_band(p)["signals"]["gfp"]["pct"]["50"] == band["signals"]["gfp"]["pct"]["50"]


def test_nan_in_query_raises_instead_of_ranking_p100():
    band = norms.build_band(ref_clips(), name="t")
    clip = {"gfp": np.full(30, 1.0), "attention": np.zeros(30)}
    clip["gfp"][6:9] = np.nan
    with pytest.raises(ValueError, match="non-finite"):
        norms.diagnose(clip, band)


def test_nan_in_reference_rejected():
    clips = ref_clips()
    clips[3]["gfp"][5] = np.nan
    with pytest.raises(ValueError, match="non-finite"):
        norms.build_band(clips, name="t")


def test_unequal_signal_lengths_rejected():
    band = norms.build_band(ref_clips(), name="t")
    with pytest.raises(ValueError, match="different lengths"):
        norms.diagnose({"gfp": np.ones(30), "attention": np.zeros(20)}, band)


def test_missing_signals_reported():
    band = norms.build_band(ref_clips(), name="t")
    out = norms.diagnose({"gfp": np.ones(30), "other": np.zeros(30)}, band)
    assert out["missing_signals"] == ["attention", "other"]
