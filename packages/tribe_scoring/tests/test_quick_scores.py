"""Unit tests for quick_scores() hook windows, run on synthetic prediction arrays.

TRIBE v2 predicts BOLD, which lags the stimulus by about 5 s, so `*_hook` and
`gfp_hook` read predicted seconds 4-8 (indices 4..7). The old 0-3 s value is
kept as `*_hook_0_3` / `gfp_hook_0_3`.

The scorer imports the GPU-only `tribev2` package at import time, so it is
stubbed (see conftest.py). The package is loaded from this checkout under a private name,
so an installed copy of `tribe_scoring` elsewhere cannot shadow it.

Run: uv run --with numpy --with pytest pytest packages/tribe_scoring/tests
"""
from __future__ import annotations

import csv
import io
import json
import math

import numpy as np
import pytest

N_VERTS = 20484


def preds_with_spike(n: int, seconds, value: float = 1.0) -> np.ndarray:
    """All-zero predictions of n seconds, with every vertex set to `value` at `seconds`."""
    preds = np.zeros((n, N_VERTS), dtype=np.float32)
    for s in seconds:
        preds[s, :] = value
    return preds


def test_hook_window_constant(ras):
    assert ras.HOOK_WINDOW == slice(4, 8)


def test_spike_in_seconds_4_to_7_moves_new_hook_not_old(ras):
    row = ras.quick_scores(preds_with_spike(20, range(4, 8)))
    for d in ras._CSV_DIMS:
        assert row[f"{d}_hook"] == pytest.approx(1.0)
        assert row[f"{d}_hook_0_3"] == pytest.approx(0.0)
    assert row["gfp_hook"] == pytest.approx(1.0)
    assert row["gfp_hook_0_3"] == pytest.approx(0.0)
    assert row["hook_window_n"] == 4


def test_spike_in_seconds_0_to_2_moves_old_hook_not_new(ras):
    row = ras.quick_scores(preds_with_spike(20, range(0, 3)))
    for d in ras._CSV_DIMS:
        assert row[f"{d}_hook"] == pytest.approx(0.0)
        assert row[f"{d}_hook_0_3"] == pytest.approx(1.0)
    assert row["gfp_hook"] == pytest.approx(0.0)
    assert row["gfp_hook_0_3"] == pytest.approx(1.0)


@pytest.mark.parametrize("second", [3, 8])
def test_window_edges_are_excluded(ras, second):
    row = ras.quick_scores(preds_with_spike(20, [second]))
    assert row["attention_hook"] == pytest.approx(0.0)
    assert row["gfp_hook"] == pytest.approx(0.0)


@pytest.mark.parametrize("second", [4, 7])
def test_window_edges_are_included(ras, second):
    row = ras.quick_scores(preds_with_spike(20, [second]))
    assert row["attention_hook"] == pytest.approx(0.25)
    assert row["gfp_hook"] == pytest.approx(0.25)
    assert row["attention_hook_0_3"] == pytest.approx(0.0)


def test_single_spike_inside_window_averages_over_four_seconds(ras):
    row = ras.quick_scores(preds_with_spike(20, [6], value=2.0))
    assert row["attention_hook"] == pytest.approx(0.5)
    assert row["gfp_hook"] == pytest.approx(0.5)


@pytest.mark.parametrize("n,expected_n", [(5, 1), (6, 2), (7, 3), (8, 4)])
def test_partial_window_for_clips_shorter_than_8s(ras, n, expected_n):
    # Spike only at the last available second inside the window.
    row = ras.quick_scores(preds_with_spike(n, [n - 1 if n < 8 else 7], value=float(expected_n)))
    assert row["hook_window_n"] == expected_n
    assert row["attention_hook"] == pytest.approx(1.0)  # value / samples in window
    assert row["gfp_hook"] == pytest.approx(1.0)


@pytest.mark.parametrize("n", [1, 2, 3, 4])
def test_clips_of_4s_or_less_fall_back_to_last_second(ras, n):
    preds = np.zeros((n, N_VERTS), dtype=np.float32)
    preds[n - 1, :] = 3.0
    row = ras.quick_scores(preds)
    assert row["hook_window_n"] == 0
    assert row["attention_hook"] == pytest.approx(3.0)
    assert row["gfp_hook"] == pytest.approx(3.0)


@pytest.mark.parametrize("n", [1, 2, 3, 4, 5, 7, 8, 30])
def test_legacy_column_matches_old_formula(ras, n):
    rng = np.random.default_rng(n)
    preds = rng.normal(size=(n, N_VERTS)).astype(np.float32)
    row = ras.quick_scores(preds)
    ts = preds[:, ras._BATCH_MASKS["social"]].mean(axis=1)
    assert row["social_hook_0_3"] == pytest.approx(round(float(ts[:min(3, n)].mean()), 6))
    gfp = np.sqrt((preds ** 2).mean(axis=1))
    assert row["gfp_hook_0_3"] == pytest.approx(round(float(gfp[:min(3, n)].mean()), 6))


@pytest.mark.parametrize("n", range(1, 12))
def test_every_length_gives_finite_json_safe_values(ras, n):
    rng = np.random.default_rng(100 + n)
    row = ras.quick_scores(rng.normal(size=(n, N_VERTS)).astype(np.float32))
    for k, v in row.items():
        assert math.isfinite(v), k
    json.dumps(row, allow_nan=False)  # pod_server / RunPod return this as JSON


def test_row_keys_match_csv_fields_and_write(ras):
    row = ras.quick_scores(preds_with_spike(12, range(4, 8)))
    row.update(filename="a.mp4", label="a", n_seconds=12)
    assert set(row) == set(ras._CSV_FIELDS)
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=ras._CSV_FIELDS)
    writer.writeheader()
    writer.writerow(row)  # DictWriter raises on keys missing from fieldnames
    assert "gfp_hook_0_3" in buf.getvalue().splitlines()[0]
