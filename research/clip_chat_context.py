"""
clip_chat_context.py — ground truth for the landing page's "Ask about this clip" chat.

Reduces a TRIBE v2 prediction [T, 20484] (fsaverage5, LH 0-10241, RH 10242-20483)
to one value per second for each of the seven functional regions, using the
Destrieux atlas, which is native to fsaverage5 (no resampling). The chat answers
only from this file, so every number it quotes traces back to the model output.

Region -> Destrieux labels is an anatomical approximation of the scorer's HCP
MMP1.0 areas (roi_masks.py), not the same parcellation. The file says so, and
the chat is told to say so.

Usage:
  uv run --no-project --with nilearn --with numpy python clip_chat_context.py \\
      --preds ../business/explainer/demo_mac_and_cheese_preds.npy \\
      --out ../apps/web/lib/clip-context.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

N_HEMI = 10242

# Functional region -> Destrieux 2009 labels, chosen to cover the HCP areas in
# roi_masks.HCP_AREAS as closely as Destrieux's gyral/sulcal units allow.
REGIONS: dict[str, tuple[str, list[str]]] = {
    "attention": ("inferior frontal junction (IFJ)", ["S_front_inf", "S_precentral-inf-part"]),
    "social": ("temporo-parietal junction / angular gyrus", ["G_pariet_inf-Angular", "G_pariet_inf-Supramar"]),
    "language": ("Broca's area (44/45)", ["G_front_inf-Opercular", "G_front_inf-Triangul"]),
    "valuation": ("ventromedial PFC / subgenual cingulate", ["G_rectus", "G_subcallosal", "S_suborbital"]),
    "auditory": ("superior temporal cortex / STS", ["G_temp_sup-G_T_transv", "G_temp_sup-Plan_tempo", "G_temp_sup-Lateral", "S_temporal_sup"]),
    "motion": ("MT/V5 complex (lateral occipito-temporal)", ["S_occipital_ant", "G_occipital_middle"]),
    "narrative": ("posterior cingulate / precuneus (default mode)", ["G_cingul-Post-dorsal", "G_cingul-Post-ventral", "G_precuneus", "S_subparietal"]),
}

# What the viewer sees and hears, per 8-second Veo shot (business/explainer/stimulus/shot*.json).
TIMELINE = [
    {"from": 0, "to": 8, "shot": "Hook: woman leans into a selfie camera, grinning, holds up cream cheese by the pot. "
     "Says fast and excited: \"This one ingredient makes boxed mac and cheese taste like a restaurant made it. I did not believe it either.\""},
    {"from": 8, "to": 16, "shot": "Instructions: she stirs the pot, steady camera, even and slightly flat tone. "
     "\"So, you skip the milk the box tells you to use. You save a little pasta water, add a spoonful of cream cheese, and stir for about a full minute.\""},
    {"from": 16, "to": 25, "shot": "Payoff: cheese pull toward the camera, she takes a bite, eyes widen, laughs. "
     "\"Okay. Yeah. I am never going back.\""},
]


def region_masks() -> dict[str, np.ndarray]:
    from nilearn.datasets import fetch_atlas_surf_destrieux

    atlas = fetch_atlas_surf_destrieux()
    names = [n.decode() if isinstance(n, bytes) else str(n) for n in atlas["labels"]]
    lh, rh = np.asarray(atlas["map_left"]), np.asarray(atlas["map_right"])
    assert lh.size == rh.size == N_HEMI, "Destrieux map is not fsaverage5"
    masks = {}
    for key, (_, labels) in REGIONS.items():
        ids = [names.index(lbl) for lbl in labels]
        masks[key] = np.concatenate([np.where(np.isin(lh, ids))[0], np.where(np.isin(rh, ids))[0] + N_HEMI])
    return masks


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--preds", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()

    preds = np.load(args.preds).astype(np.float64)
    T, V = preds.shape
    assert V == 2 * N_HEMI, f"expected 20484 vertices, got {V}"

    masks = region_masks()
    whole = preds.mean(axis=1)
    # z-score each region's time course against the whole cortex at the same
    # second, so "high" means above the cortex average, not just a global swell.
    cortex_sd = preds.std(axis=1)

    regions = {}
    for key, idx in masks.items():
        ts = preds[:, idx].mean(axis=1)
        rel = (ts - whole) / cortex_sd
        regions[key] = {
            "area": REGIONS[key][0],
            "destrieux_labels": REGIONS[key][1],
            "n_vertices": int(idx.size),
            "mean": round(float(ts.mean()), 4),
            "per_second": [round(float(x), 4) for x in ts],
            "vs_cortex_z": [round(float(x), 2) for x in rel],
            "peak_second": int(ts.argmax()),
            "low_second": int(ts.argmin()),
        }

    gfp = preds.std(axis=1)
    out = {
        "clip": "Sample creator clip (AI-generated, Google Veo 3.1): boxed mac and cheese hack, 3 shots x 8 s, 9:16.",
        "model": "Meta TRIBE v2, predicted cortical response on fsaverage5 (20,484 surface vertices), 1 value per second.",
        "units": "Model output units (z-scored BOLD-like scale); compare within this clip, not across clips.",
        "seconds": T,
        "timeline": TIMELINE,
        "whole_cortex": {
            "mean_per_second": [round(float(x), 4) for x in whole],
            "global_field_power_per_second": [round(float(x), 4) for x in gfp],
            "peak_second": int(gfp.argmax()),
        },
        "regions": regions,
        "parcellation_note": "Regions are Destrieux-atlas approximations of the scorer's HCP MMP1.0 areas.",
    }
    args.out.write_text(json.dumps(out, indent=1) + "\n")
    print(f"wrote {args.out} ({T} s)")
    for key, r in regions.items():
        print(f"  {key:10s} n={r['n_vertices']:5d} mean={r['mean']:+.3f} peak@{r['peak_second']:2d}s low@{r['low_second']:2d}s")


if __name__ == "__main__":
    main()
