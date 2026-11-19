"""
roi_masks.py — ROI vertex indices for TRIBE v2 (fsaverage5, 20484 vertices).

Three sources, chosen explicitly. Nothing falls back silently: a missing source
raises, and every load prints which source it used.

  destrieux  (default) The committed anatomical masks in
             packages/tribe_scoring/roi_masks_fsaverage5.json, the same ones the
             product scorer uses. Destrieux is native to fsaverage5, so these are
             exact label lookups. Five regions are close matches to the HCP areas
             below; attention (IFJ) and motion (MT/V5) are approximate, because
             Destrieux has no unit for either.
  hcp        Exact HCP MMP1.0 areas (Glasser 2016, the names in HCP_AREAS), built
             from the fsaverage projection lh/rh.HCP-MMP1.annot (Mills 2016,
             figshare 3498446). fsaverage5 is the first 10242 vertices of each
             fsaverage hemisphere, so the masks are a direct subset, no resampling.
             Put the two .annot files in $TRIBE_HCP_ANNOT_DIR (default
             ~/.tribe_social/hcp/) and run `python roi_masks.py --build-hcp`.

History: before 2026-11-16 the HCP path called neuromaps fetch_atlas("glasser"),
which is not a neuromaps atlas, and the exception handler silently returned
index-range masks. Those ranges were scattered points rather than regions, and
the Social range ran past vertex 20483, so analyze.py could not have scored a
clip with them. They are removed. (The pilot scores.csv came from the batch
scorer's own index-range masks, replaced in packages/tribe_scoring by PR #17.)

Usage:
    from roi_masks import get_roi_masks
    masks = get_roi_masks()                  # destrieux
    masks = get_roi_masks(source="hcp")      # needs --build-hcp once
"""

from __future__ import annotations

import argparse
import json
import re
import numpy as np
from pathlib import Path

import os

HCP_ANNOT_DIR = Path(os.environ.get("TRIBE_HCP_ANNOT_DIR", Path.home() / ".tribe_social" / "hcp"))
HCP_CACHE_PATH = Path.home() / ".tribe_social" / "roi_masks_hcp.json"
DESTRIEUX_PATH = Path(__file__).resolve().parent.parent / "packages" / "tribe_scoring" / "roi_masks_fsaverage5.json"
N_VERTS_PER_HEMI = 10242  # fsaverage5

# HCP MMP1.0 short area names (Glasser et al. 2016) per ROI category.
# References:
#   Attention (IFJa/IFJp): Glasser et al. 2016 areas 97/98 — inferior frontal junction
#   Social (PGi/PGp/IP1):  Scholz et al. 2017 TPJ proxy — angular + intraparietal
#   Language (44/45):      Broca's complex (pars opercularis + triangularis)
#   Valuation (10v/25/s32): vmPFC / subgenual ACC — cortico-striatal valuation node
#   Auditory (STS/A5/TE1a): superior temporal sulcus + early auditory belt
#   Motion (MT/MST/V4t):   MT/V5 complex — visual motion processing
#   Narrative (PCC/DMN):   posterior default-mode — narrative engagement
HCP_AREAS: dict[str, list[str]] = {
    "Attention":  ["IFJa", "IFJp"],
    "Social":     ["PGi", "PGp", "IP1"],
    "Language":   ["44", "45"],
    "Valuation":  ["10v", "25", "s32"],
    "Auditory":   ["STSvp", "STSva", "A5", "TE1a"],
    "Motion":     ["MT", "MST", "V4t"],
    "Narrative":  ["v23ab", "d23ab", "7m", "POS1", "RSC"],
}


def _build_hcp(annot_dir: Path) -> dict[str, np.ndarray]:
    """Exact HCP MMP1.0 masks from the fsaverage .annot pair (see module docstring)."""
    for hemi in ("lh", "rh"):
        path = annot_dir / f"{hemi}.HCP-MMP1.annot"
        if not path.exists():
            raise FileNotFoundError(f"{path} not found (see roi_masks.py docstring)")
    import nibabel as nib  # only needed for this one-off build

    masks: dict[str, list[np.ndarray]] = {c: [] for c in HCP_AREAS}
    for hemi, offset in (("lh", 0), ("rh", N_VERTS_PER_HEMI)):
        path = annot_dir / f"{hemi}.HCP-MMP1.annot"
        labels, _ctab, names = nib.freesurfer.read_annot(str(path))
        if labels.shape[0] < N_VERTS_PER_HEMI:
            raise ValueError(f"{path}: {labels.shape[0]} vertices, expected fsaverage (163842)")
        labels = labels[:N_VERTS_PER_HEMI]  # fsaverage5 = first 10242 fsaverage vertices
        lookup: dict[str, int] = {}
        for i, raw in enumerate(names):
            clean = re.sub(r"^[LRlr][Hh]?_", "", raw.decode())
            lookup[re.sub(r"_ROI$", "", clean)] = i
        for category, areas in HCP_AREAS.items():
            missing = [a for a in areas if a not in lookup]
            if missing:
                raise ValueError(f"{path}: HCP areas {missing} not in the annotation")
            for area in areas:
                masks[category].append(np.where(labels == lookup[area])[0] + offset)
    out = {c: np.sort(np.concatenate(v)) for c, v in masks.items()}
    for c, v in out.items():
        if len(v) == 0:
            raise ValueError(f"HCP mask for {c} is empty")
    return out


def _load_destrieux() -> dict[str, np.ndarray]:
    if not DESTRIEUX_PATH.exists():
        raise FileNotFoundError(f"{DESTRIEUX_PATH} not found")
    regions = json.loads(DESTRIEUX_PATH.read_text())["regions"]
    out = {}
    for category in HCP_AREAS:
        key = category.lower()
        if key not in regions:
            raise KeyError(f"{DESTRIEUX_PATH.name} has no region '{key}'")
        out[category] = np.asarray(regions[key]["vertices"], dtype=int)
    return out


SOURCES = ("destrieux", "hcp")


def get_roi_masks(source: str = "destrieux", rebuild: bool = False) -> dict[str, np.ndarray]:
    """Return {category: vertex_index_array} on fsaverage5 from the named source.

    Raises rather than substituting another source. `rebuild` only applies to hcp.
    """
    if source == "destrieux":
        masks = _load_destrieux()
    elif source == "hcp":
        if rebuild or not HCP_CACHE_PATH.exists():
            masks = _build_hcp(HCP_ANNOT_DIR)
            HCP_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
            HCP_CACHE_PATH.write_text(json.dumps({k: v.tolist() for k, v in masks.items()}))
        else:
            raw = json.loads(HCP_CACHE_PATH.read_text())
            masks = {k: np.array(v, dtype=int) for k, v in raw.items()}
    else:
        raise ValueError(f"unknown mask source {source!r}; expected one of {SOURCES}")
    _check(masks, source)
    print(f"ROI masks: source={source}")
    return masks


def _check(masks: dict[str, np.ndarray], source: str) -> None:
    if set(masks) != set(HCP_AREAS):
        raise ValueError(f"{source} masks have regions {sorted(masks)}, expected {sorted(HCP_AREAS)}")
    for c, v in masks.items():
        if len(v) == 0 or v.min() < 0 or v.max() >= 2 * N_VERTS_PER_HEMI:
            raise ValueError(f"{source} mask {c} is empty or out of range")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Inspect or build fsaverage5 ROI masks.")
    parser.add_argument("--source", choices=SOURCES, default="destrieux")
    parser.add_argument("--build-hcp", action="store_true",
                        help="Build the HCP cache from $TRIBE_HCP_ANNOT_DIR")
    args = parser.parse_args()

    source = "hcp" if args.build_hcp else args.source
    masks = get_roi_masks(source=source, rebuild=args.build_hcp)
    total = 0
    for cat, verts in masks.items():
        total += len(verts)
        print(f"  {cat:12s}: {len(verts):5d} vertices")
    print(f"  {'Total':12s}: {total:5d} vertices")
