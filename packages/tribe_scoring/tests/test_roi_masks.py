"""Tests for the anatomical ROI masks quick_scores() reads.

The masks are Destrieux-atlas vertex sets on fsaverage5, precomputed by
build_roi_masks.py into roi_masks_fsaverage5.json. They replaced contiguous
vertex-index ranges, which were scatters of points across the cortex because
fsaverage5 vertex order is not spatial.

Most tests need numpy only. The tests marked "atlas" need nilearn (the atlas
and the fsaverage5 mesh); they skip without it. Run all of them with:

  uv run --no-project --with numpy --with pytest --with nilearn \\
      pytest packages/tribe_scoring/tests
"""
from __future__ import annotations

import ast
import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest

PKG_DIR = Path(__file__).resolve().parents[1]
REPO = PKG_DIR.parents[1]
MASKS_JSON = PKG_DIR / "roi_masks_fsaverage5.json"
N_HEMI = 10242
N_VERTS = 2 * N_HEMI
SIGNALS = ["attention", "social", "language", "valuation", "auditory", "motion", "narrative"]

# The CSV row layout before this change; it must not move.
EXPECTED_FIELDS = (
    ["filename", "label", "n_seconds"]
    + [f"{d}_{s}" for s in ("mean", "hook", "hook_0_3", "offset", "peak_s", "ts_ratio") for d in SIGNALS]
    + ["composite_raw", "gfp_mean", "gfp_hook", "gfp_hook_0_3", "gfp_offset",
       "hook_window_n", "vmPFC_TPJ_coupling", "pleasantness_index"]
)


@pytest.fixture(scope="module")
def meta() -> dict:
    return json.loads(MASKS_JSON.read_text())


@pytest.fixture(scope="module")
def builder():
    spec = importlib.util.spec_from_file_location("_build_roi_masks_under_test", PKG_DIR / "build_roi_masks.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# The committed masks (numpy only)
# ---------------------------------------------------------------------------
def test_scorer_uses_the_seven_signals_in_order(ras):
    assert list(ras._BATCH_MASKS) == SIGNALS
    assert ras._CSV_DIMS == SIGNALS


def test_mask_names_match_composite_weights(ras):
    from importlib import import_module
    composite = import_module(ras.__name__.rsplit(".", 1)[0] + ".composite")
    assert set(composite.ROI_WEIGHTS) == set(ras._BATCH_MASKS)


@pytest.mark.parametrize("dim", SIGNALS)
def test_mask_is_non_empty_in_range_unique_and_bilateral(ras, dim):
    idx = ras._BATCH_MASKS[dim]
    assert idx.size > 0
    assert idx.min() >= 0 and idx.max() < N_VERTS
    assert np.unique(idx).size == idx.size
    assert (idx < N_HEMI).sum() > 0, "no left-hemisphere vertices"
    assert (idx >= N_HEMI).sum() > 0, "no right-hemisphere vertices"


def test_masks_do_not_overlap(ras):
    seen = np.zeros(N_VERTS, dtype=int)
    for idx in ras._BATCH_MASKS.values():
        seen[idx] += 1
    assert seen.max() == 1


@pytest.mark.parametrize("dim", SIGNALS)
def test_stored_spatial_coherence(meta, dim):
    """Each mask is a few solid areas, not a scatter (numbers from the mesh, see
    build_roi_masks.shape_stats; recomputed in test_stored_stats_match_mesh)."""
    r = meta["regions"][dim]
    assert r["coherence"] >= 0.95            # vertices with a mask neighbour
    for h in ("lh", "rh"):
        assert 1 <= r[f"components_{h}"] <= 3
        assert r[f"largest_component_share_{h}"] >= 0.9


def test_json_labels_match_generator(meta, builder):
    assert list(meta["regions"]) == list(builder.REGIONS)
    for dim, (area, labels) in builder.REGIONS.items():
        assert meta["regions"][dim]["destrieux_labels"] == labels
        assert meta["regions"][dim]["area"] == area


def test_json_records_provenance(meta):
    assert "Destrieux" in meta["atlas"]
    assert meta["nilearn_version"]
    assert meta["n_vertices"] == N_VERTS
    assert meta["generator"].endswith("build_roi_masks.py")


def test_labels_match_clip_page_when_present(builder):
    """One source of truth with the live clip page. research/clip_chat_context.py
    is not on every branch yet; when it is, its REGIONS must equal ours."""
    path = REPO / "research" / "clip_chat_context.py"
    if not path.exists():
        pytest.skip("research/clip_chat_context.py not in this tree")
    tree = ast.parse(path.read_text())
    for node in tree.body:
        target = getattr(node, "target", None) or (node.targets[0] if isinstance(node, ast.Assign) else None)
        if isinstance(target, ast.Name) and target.id == "REGIONS":
            assert ast.literal_eval(node.value) == builder.REGIONS
            return
    pytest.fail("REGIONS not found in clip_chat_context.py")


# ---------------------------------------------------------------------------
# quick_scores() on the new masks
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("n", [3, 12, 40])
def test_quick_scores_row_layout_unchanged(ras, n):
    rng = np.random.default_rng(n)
    row = ras.quick_scores(rng.normal(size=(n, N_VERTS)).astype(np.float32))
    row.update(filename="a.mp4", label="a", n_seconds=n)
    assert ras._CSV_FIELDS == EXPECTED_FIELDS
    assert set(row) == set(EXPECTED_FIELDS) and len(row) == len(EXPECTED_FIELDS) == 53
    for k, v in row.items():
        if k not in ("filename", "label"):
            assert np.isscalar(v), k


@pytest.mark.parametrize("dim", SIGNALS)
def test_activation_in_a_region_moves_only_that_signal(ras, dim):
    preds = np.zeros((12, N_VERTS), dtype=np.float32)
    preds[:, ras._BATCH_MASKS[dim]] = 1.0
    row = ras.quick_scores(preds)
    for other in SIGNALS:
        assert row[f"{other}_mean"] == pytest.approx(1.0 if other == dim else 0.0)


def test_pleasantness_index_reads_left_minus_right_attention(ras):
    idx = ras._BATCH_MASKS["attention"]
    preds = np.zeros((10, N_VERTS), dtype=np.float32)
    preds[:, idx[idx < N_HEMI]] = 2.0
    assert ras.quick_scores(preds)["pleasantness_index"] == pytest.approx(2.0)


def test_coupling_uses_valuation_and_social(ras):
    t = np.linspace(0, 6, 20)
    preds = np.zeros((20, N_VERTS), dtype=np.float32)
    preds[:, ras._BATCH_MASKS["valuation"]] = np.sin(t)[:, None]
    preds[:, ras._BATCH_MASKS["social"]] = np.sin(t)[:, None]
    assert ras.quick_scores(preds)["vmPFC_TPJ_coupling"] == pytest.approx(1.0, abs=1e-4)


@pytest.mark.parametrize("breakage", ["out_of_range", "empty", "duplicate", "missing_signal"])
def test_loader_rejects_bad_mask_files(ras, tmp_path, meta, breakage):
    bad = json.loads(json.dumps(meta))
    if breakage == "out_of_range":
        bad["regions"]["motion"]["vertices"] = [0, N_VERTS]
    elif breakage == "empty":
        bad["regions"]["motion"]["vertices"] = []
    elif breakage == "duplicate":
        bad["regions"]["motion"]["vertices"] = [5, 5]
    else:
        del bad["regions"]["motion"]
    p = tmp_path / "bad.json"
    p.write_text(json.dumps(bad))
    with pytest.raises(ValueError):
        ras._load_masks(p)


# ---------------------------------------------------------------------------
# Against the atlas and the mesh (needs nilearn)
# ---------------------------------------------------------------------------
def _old_index_range_masks() -> dict[str, np.ndarray]:
    """The masks this change replaced (contiguous fsaverage5 index ranges)."""
    ranges = {
        "attention": [(8200, 8350), (8350, 8500)], "social": [(6500, 6900)],
        "language": [(7800, 8000)], "valuation": [(400, 700)], "auditory": [(8800, 9200)],
        "motion": [(9800, 10000)], "narrative": [(1200, 1600)],
    }
    out = {}
    for k, rs in ranges.items():
        lh = np.concatenate([np.arange(a, b) for a, b in rs])
        out[k] = np.concatenate([lh, lh + N_HEMI])
    return out


@pytest.fixture(scope="module")
def atlas():
    datasets = pytest.importorskip("nilearn.datasets")
    a = datasets.fetch_atlas_surf_destrieux()
    names = [n.decode() if isinstance(n, bytes) else str(n) for n in a["labels"]]
    return names, np.asarray(a["map_left"]), np.asarray(a["map_right"])


@pytest.fixture(scope="module")
def edges(builder, atlas):
    return builder.mesh_edges()


def test_committed_masks_match_a_fresh_build(meta, builder, atlas):
    fresh = builder.build()
    for dim in SIGNALS:
        assert fresh["regions"][dim]["vertices"] == meta["regions"][dim]["vertices"], dim


@pytest.mark.parametrize("dim", SIGNALS)
def test_stored_stats_match_mesh(meta, builder, edges, dim):
    idx = np.asarray(meta["regions"][dim]["vertices"])
    stats = builder.shape_stats(idx, *edges)
    for k, v in stats.items():
        assert meta["regions"][dim][k] == pytest.approx(v), k


@pytest.mark.parametrize("dim", SIGNALS)
def test_activation_planted_in_destrieux_label_moves_matching_signal(ras, builder, atlas, dim):
    """Plant activity in one Destrieux label, located with nilearn directly
    (not via the committed JSON); only the matching signal should move."""
    names, lh, rh = atlas
    label = builder.REGIONS[dim][1][0]
    lab_id = names.index(label)
    planted = np.concatenate([np.where(lh == lab_id)[0], np.where(rh == lab_id)[0] + N_HEMI])
    assert planted.size > 0
    preds = np.zeros((12, N_VERTS), dtype=np.float32)
    preds[:, planted] = 1.0
    row = ras.quick_scores(preds)
    mask = ras._BATCH_MASKS[dim]
    assert np.isin(planted, mask).all()
    assert row[f"{dim}_mean"] == pytest.approx(planted.size / mask.size, abs=1e-5)
    for other in SIGNALS:
        if other != dim:
            assert row[f"{other}_mean"] == pytest.approx(0.0), other


def test_old_index_range_masks_fail_the_coherence_check(builder, edges):
    """Regression evidence: the replaced masks split into many pieces."""
    failing = 0
    for idx in _old_index_range_masks().values():
        s = builder.shape_stats(idx, *edges)
        if s["components_lh"] > 3 or s["largest_component_share_lh"] < 0.9:
            failing += 1
    assert failing == 7
