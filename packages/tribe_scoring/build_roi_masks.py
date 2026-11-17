"""
build_roi_masks.py — generate roi_masks_fsaverage5.json, the anatomical ROI
masks quick_scores() reads at runtime.

The scorer runs on RunPod with numpy only, so the Destrieux atlas lookup is
done here, once, and the resulting vertex indices are committed next to the
scorer. Re-run this script only when the region -> label mapping changes:

    uv run --no-project --with nilearn --with numpy \\
        python packages/tribe_scoring/build_roi_masks.py

Region -> Destrieux labels is the same mapping the live clip page uses
(research/clip_chat_context.py, REGIONS). Keep the two identical: the scorer
test compares them whenever that file is present in the tree.

Destrieux (aparc.a2009s) is native to fsaverage5, so no resampling happens:
the masks are exact label lookups on the 10242-vertex-per-hemisphere mesh
TRIBE v2 predicts on (LH 0-10241, RH 10242-20483).

The file also stores, per region, spatial-coherence numbers computed on the
fsaverage5 pial mesh: the share of mask vertices with at least one mask
neighbour ("coherence"), and the number and relative size of connected pieces
per hemisphere. The numpy-only tests check these, so the masks are known to be
areas rather than scattered points. (Neighbour share alone is not enough: the
old index-range masks score 1.0 on it for most regions, because fsaverage
vertex order runs in short local strips, yet split into 4-800 pieces.)
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

N_HEMI = 10242
OUT_PATH = Path(__file__).resolve().parent / "roi_masks_fsaverage5.json"

# Functional region -> (area description, Destrieux 2009 labels).
# Copied verbatim from research/clip_chat_context.py REGIONS (the clip page).
REGIONS: dict[str, tuple[str, list[str]]] = {
    "attention": ("inferior frontal junction (IFJ)", ["S_front_inf", "S_precentral-inf-part"]),
    "social": ("temporo-parietal junction / angular gyrus", ["G_pariet_inf-Angular", "G_pariet_inf-Supramar"]),
    "language": ("Broca's area (44/45)", ["G_front_inf-Opercular", "G_front_inf-Triangul"]),
    "valuation": ("ventromedial PFC / subgenual cingulate", ["G_rectus", "G_subcallosal", "S_suborbital"]),
    "auditory": ("superior temporal cortex / STS", ["G_temp_sup-G_T_transv", "G_temp_sup-Plan_tempo", "G_temp_sup-Lateral", "S_temporal_sup"]),
    "motion": ("MT/V5 complex (lateral occipito-temporal)", ["S_occipital_ant", "G_occipital_middle"]),
    "narrative": ("posterior cingulate / precuneus (default mode)", ["G_cingul-Post-dorsal", "G_cingul-Post-ventral", "G_precuneus", "S_subparietal"]),
}

# How well each Destrieux approximation matches the HCP MMP1.0 areas the
# signal was named after (research/roi_masks.py HCP_AREAS).
MATCH_NOTES: dict[str, str] = {
    "attention": "approximate: IFJ is the junction of the inferior frontal and inferior precentral sulci; "
                 "Destrieux has no junction unit, so the mask is both whole sulci (larger than IFJa/IFJp).",
    "social": "close: angular gyrus covers PGi/PGp; supramarginal is added for the anterior TPJ; IP1 (intraparietal) is not included.",
    "language": "clean: pars opercularis + pars triangularis = areas 44/45.",
    "valuation": "close: gyrus rectus + subcallosal + suborbital sulcus cover 10v/25/s32.",
    "auditory": "close: transverse temporal, planum temporale, lateral STG and STS cover A5/TE1a/STSva/STSvp (broader than the HCP set).",
    "motion": "approximate: MT/V5 has no Destrieux unit; anterior occipital sulcus + middle occipital gyrus is the nearest lateral occipito-temporal cover.",
    "narrative": "close: posterior cingulate (dorsal, ventral) + precuneus + subparietal sulcus cover v23ab/d23ab/7m/POS1; RSC is only partly covered.",
}


def _sha256(path: str) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def mesh_edges() -> tuple[np.ndarray, np.ndarray]:
    """Unique undirected edges (u < v) of the fsaverage5 pial mesh, per hemisphere."""
    from nilearn.datasets import load_fsaverage

    pial = load_fsaverage("fsaverage5")["pial"]
    out = []
    for hemi in ("left", "right"):
        faces = np.asarray(pial.parts[hemi].faces)
        assert faces.max() < N_HEMI, "fsaverage5 mesh has unexpected vertex count"
        e = np.concatenate([faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]])
        e.sort(axis=1)
        out.append(np.unique(e, axis=0))
    return out[0], out[1]


def coherence(idx: np.ndarray, edges_lh: np.ndarray, edges_rh: np.ndarray) -> float:
    """Share of mask vertices (global 0-20483 indices) with >= 1 mask neighbour."""
    mask = np.zeros(2 * N_HEMI, dtype=bool)
    mask[idx] = True
    has_nb = np.zeros(2 * N_HEMI, dtype=bool)
    for edges, off in ((edges_lh, 0), (edges_rh, N_HEMI)):
        u, v = edges[:, 0] + off, edges[:, 1] + off
        both = mask[u] & mask[v]
        has_nb[u[both]] = True
        has_nb[v[both]] = True
    return float(has_nb[idx].mean()) if idx.size else 0.0


def components(idx: np.ndarray, edges: np.ndarray, offset: int) -> list[int]:
    """Sizes of the connected pieces (largest first) of the mask vertices in one
    hemisphere, using only mesh edges whose two ends are both in the mask."""
    local = idx[(idx >= offset) & (idx < offset + N_HEMI)] - offset
    if local.size == 0:
        return []
    mask = np.zeros(N_HEMI, dtype=bool)
    mask[local] = True
    e = edges[mask[edges[:, 0]] & mask[edges[:, 1]]]
    lab = np.arange(N_HEMI)
    while True:  # min-label propagation until stable
        m = np.minimum(lab[e[:, 0]], lab[e[:, 1]])
        new = lab.copy()
        np.minimum.at(new, e[:, 0], m)
        np.minimum.at(new, e[:, 1], m)
        new = new[new]
        if np.array_equal(new, lab):
            break
        lab = new
    return sorted(np.bincount(lab[local]).tolist(), reverse=True)


def shape_stats(idx: np.ndarray, edges_lh: np.ndarray, edges_rh: np.ndarray) -> dict:
    """Spatial-coherence numbers for one mask, stored in the JSON."""
    comp_lh = [c for c in components(idx, edges_lh, 0) if c]
    comp_rh = [c for c in components(idx, edges_rh, N_HEMI) if c]
    n_lh, n_rh = sum(comp_lh), sum(comp_rh)
    return {
        "coherence": round(coherence(idx, edges_lh, edges_rh), 4),
        "components_lh": len(comp_lh),
        "components_rh": len(comp_rh),
        "largest_component_share_lh": round(comp_lh[0] / n_lh, 4) if n_lh else 0.0,
        "largest_component_share_rh": round(comp_rh[0] / n_rh, 4) if n_rh else 0.0,
    }


def build() -> dict:
    import nilearn
    from nilearn.datasets import fetch_atlas_surf_destrieux

    atlas = fetch_atlas_surf_destrieux()
    names = [n.decode() if isinstance(n, bytes) else str(n) for n in atlas["labels"]]
    lh, rh = np.asarray(atlas["map_left"]), np.asarray(atlas["map_right"])
    assert lh.size == rh.size == N_HEMI, "Destrieux map is not fsaverage5"

    # Record the source annot files when nilearn exposes them.
    sources = {}
    data_dir = Path(nilearn.datasets.get_data_dirs()[0]) / "destrieux_surface"
    for fn in ("left.aparc.a2009s.annot", "right.aparc.a2009s.annot"):
        p = data_dir / fn
        if p.exists():
            sources[fn] = _sha256(str(p))

    edges_lh, edges_rh = mesh_edges()
    regions = {}
    for key, (area, labels) in REGIONS.items():
        missing = [lbl for lbl in labels if lbl not in names]
        assert not missing, f"{key}: labels not in Destrieux atlas: {missing}"
        ids = [names.index(lbl) for lbl in labels]
        lh_idx = np.where(np.isin(lh, ids))[0]
        rh_idx = np.where(np.isin(rh, ids))[0] + N_HEMI
        idx = np.concatenate([lh_idx, rh_idx]).astype(int)
        regions[key] = {
            "area": area,
            "destrieux_labels": labels,
            "match": MATCH_NOTES[key],
            "n_lh": int(lh_idx.size),
            "n_rh": int(rh_idx.size),
            **shape_stats(idx, edges_lh, edges_rh),
            "vertices": idx.tolist(),
        }

    return {
        "atlas": "Destrieux 2009 (FreeSurfer aparc.a2009s), via nilearn.datasets.fetch_atlas_surf_destrieux",
        "atlas_files_sha256": sources,
        "nilearn_version": nilearn.__version__,
        "mesh": "fsaverage5 (10242 vertices per hemisphere; LH 0-10241, RH 10242-20483)",
        "n_vertices": 2 * N_HEMI,
        "coherence_definition": "share of mask vertices with at least one mask neighbour on the fsaverage5 pial mesh",
        "components_definition": "connected pieces of the mask per hemisphere on the fsaverage5 pial mesh (edges with both ends in the mask)",
        "label_source": "research/clip_chat_context.py REGIONS (live clip page)",
        "generator": "packages/tribe_scoring/build_roi_masks.py",
        "regions": regions,
    }


def dump(data: dict) -> str:
    """Readable JSON with each vertex list kept on one line."""
    lists = {}
    shallow = json.loads(json.dumps(data))
    for key, r in shallow["regions"].items():
        token = f"@@VERTICES_{key}@@"
        lists[token] = json.dumps(r["vertices"], separators=(",", ":"))
        r["vertices"] = token
    text = json.dumps(shallow, indent=1)
    for token, flat in lists.items():
        text = text.replace(f'"{token}"', flat)
    return text + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=OUT_PATH)
    args = ap.parse_args()
    data = build()
    args.out.write_text(dump(data))
    print(f"wrote {args.out}")
    for key, r in data["regions"].items():
        print(f"  {key:10s} lh={r['n_lh']:4d} rh={r['n_rh']:4d} coherence={r['coherence']:.3f} "
              f"pieces={r['components_lh']}/{r['components_rh']} "
              f"largest={r['largest_component_share_lh']:.2f}/{r['largest_component_share_rh']:.2f}")


if __name__ == "__main__":
    main()
