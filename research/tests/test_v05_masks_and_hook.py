"""Pre-registration v0.5: anatomical ROI masks with no silent fallback, and the
hook window (predicted s 0-3, stimulus-aligned) shared by research and the product scorer."""
from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

RESEARCH = Path(__file__).resolve().parents[1]
REPO = RESEARCH.parent
sys.path.insert(0, str(RESEARCH))

import roi_masks  # noqa: E402


def test_default_source_is_destrieux_with_all_regions():
    masks = roi_masks.get_roi_masks()
    assert set(masks) == set(roi_masks.HCP_AREAS)
    for c, v in masks.items():
        assert len(v) > 100, c
        assert v.min() >= 0 and v.max() < 20484, c
        lh, rh = (v < 10242).sum(), (v >= 10242).sum()
        assert lh > 0 and rh > 0, f"{c} should be bilateral"


def test_hcp_without_annots_raises_instead_of_falling_back(tmp_path, monkeypatch):
    monkeypatch.setattr(roi_masks, "HCP_ANNOT_DIR", tmp_path)
    monkeypatch.setattr(roi_masks, "HCP_CACHE_PATH", tmp_path / "cache.json")
    with pytest.raises(FileNotFoundError):
        roi_masks.get_roi_masks(source="hcp")


def test_unknown_source_raises():
    with pytest.raises(ValueError):
        roi_masks.get_roi_masks(source="phase0")


def test_check_rejects_out_of_range_masks():
    bad = {c: np.array([1, 2, 3]) for c in roi_masks.HCP_AREAS}
    bad["Social"] = np.array([22242])  # the old Social range ran past the mesh
    with pytest.raises(ValueError):
        roi_masks._check(bad, "test")


def _slice_constants(path: Path) -> dict[str, tuple[int, int]]:
    out = {}
    for node in ast.parse(path.read_text()).body:
        if (isinstance(node, ast.Assign) and isinstance(node.value, ast.Call)
                and getattr(node.value.func, "id", "") == "slice"):
            out[node.targets[0].id] = tuple(a.value for a in node.value.args)
    return out


def test_hook_window_matches_product_scorer():
    research = _slice_constants(RESEARCH / "analyze.py")
    product = _slice_constants(REPO / "packages" / "tribe_scoring" / "run_and_save.py")
    assert research["HOOK_WINDOW"] == product["HOOK_WINDOW"] == (0, 3)
    assert research["LEGACY_HOOK_WINDOW"] == product["LEGACY_HOOK_WINDOW"] == (0, 3)


def test_phase1b_refuses_pre_v05_scores(tmp_path):
    old = tmp_path / "scores.csv"
    old.write_text("filename,label,n_seconds,attention_hook\nx.mp4,x,10,0.1\n")
    r = subprocess.run(
        [sys.executable, str(RESEARCH / "phase1b_correlation.py")],
        cwd=tmp_path, capture_output=True, text=True, timeout=120,
        env={"TRIBE_SCORES_CSV": str(old), "PATH": "/usr/bin:/bin", "MPLBACKEND": "Agg"},
    )
    assert r.returncode != 0
    assert "predates pre-registration v0.5" in (r.stdout + r.stderr)


def test_phase1b_refuses_lagged_window_scores(tmp_path):
    lagged = tmp_path / "scores.csv"
    lagged.write_text("filename,label,n_seconds,attention_hook,hook_window_n\nx.mp4,x,10,0.1,4\n")
    r = subprocess.run(
        [sys.executable, str(RESEARCH / "phase1b_correlation.py")],
        cwd=tmp_path, capture_output=True, text=True, timeout=120,
        env={"TRIBE_SCORES_CSV": str(lagged), "PATH": "/usr/bin:/bin", "MPLBACKEND": "Agg"},
    )
    assert r.returncode != 0
    assert "reverted lagged hook window" in (r.stdout + r.stderr)
