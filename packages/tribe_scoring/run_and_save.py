"""
Run TRIBE v2 on content and save predictions for analysis.
Upload this script to RunPod alongside your content files.

Single-video usage:
    uv run python run_and_save.py --input clip.mp4 --label "reel_001"
    uv run python run_and_save.py --text "your text here" --label "text_test"

Batch usage (process an entire folder):
    uv run python run_and_save.py --batch-dir ./reels/ --results-csv scores.csv

Batch output:
    - One <label>_preds.npy per video (download selectively for full analysis)
    - scores.csv with per-ROI activation stats for all videos (small — always download)
"""

import csv
import json
import os
import argparse
import tempfile
import numpy as np
from pathlib import Path

os.environ["HF_TOKEN"] = os.environ.get("HF_TOKEN", "your_token_here")
os.environ["HF_HUB_DOWNLOAD_TIMEOUT"] = "300"

from tribev2.demo_utils import TribeModel


# ---------------------------------------------------------------------------
# Anatomical ROI masks (numpy-only at runtime).
# Each signal is the set of fsaverage5 vertices in a few Destrieux 2009 atlas
# labels, the same region -> label mapping the live clip page uses
# (research/clip_chat_context.py REGIONS). The atlas lookup needs nilearn, so
# it is done once by build_roi_masks.py and the vertex indices are committed in
# roi_masks_fsaverage5.json; this module only reads that file.
#
# Before this, the masks were contiguous vertex-index ranges ("approximate ROI
# masks"). fsaverage5 vertex order is not spatially contiguous, so those
# ranges were scatters of points across the cortex, not regions. Scores made
# with them are not comparable with scores made with these masks; rescore saved
# *_preds.npy files with --rescore-dir.
#
# research/analyze.py still uses HCP MMP1.0 masks (research/roi_masks.py);
# Destrieux is a coarser, anatomical approximation of those areas.
# ---------------------------------------------------------------------------
from .composite import ROI_WEIGHTS, compute_composite_raw  # single source of truth

_R = 10242          # right hemisphere vertex offset (fsaverage5)
_N_VERTS = 20484    # total vertices in TRIBE v2 output
ROI_MASKS_PATH = Path(__file__).resolve().parent / "roi_masks_fsaverage5.json"


def _load_masks(path: Path = ROI_MASKS_PATH) -> tuple[dict[str, np.ndarray], dict]:
    with open(path) as f:
        meta = json.load(f)
    if meta.get("n_vertices") != _N_VERTS:
        raise ValueError(f"{path.name}: expected {_N_VERTS} vertices, got {meta.get('n_vertices')}")
    if set(meta["regions"]) != set(ROI_WEIGHTS):
        raise ValueError(f"{path.name}: signals {sorted(meta['regions'])} != {sorted(ROI_WEIGHTS)}")
    masks = {}
    for dim, region in meta["regions"].items():
        idx = np.asarray(region["vertices"], dtype=np.intp)
        if idx.size == 0 or idx.min() < 0 or idx.max() >= _N_VERTS:
            raise ValueError(f"{path.name}: mask {dim!r} is empty or out of range")
        if np.unique(idx).size != idx.size:
            raise ValueError(f"{path.name}: mask {dim!r} has duplicate vertices")
        masks[dim] = idx
    return masks, meta


_BATCH_MASKS, ROI_MASKS_META = _load_masks()

# ---------------------------------------------------------------------------
# Hook window.
# TRIBE v2 predicts fMRI (BOLD) responses, and BOLD lags the stimulus by about
# 5 s (the haemodynamic delay). Predicted seconds 0-3 are the haemodynamic
# warm-up, not the brain's response to the video's opening seconds. The
# response to the hook shows up in predicted seconds 4-8 (indices 4..7), so
# `*_hook` and `gfp_hook` average that window.
#
# Short clips (n = number of predicted seconds):
#   n >= 8     the full window, indices 4..7 (hook_window_n = 4)
#   4 < n < 8  the part of the window that exists, indices 4..n-1
#              (hook_window_n = n - 4)
#   n <= 4     no lagged sample exists; fall back to the last predicted second
#              (index n-1), the sample closest to the lagged window
#              (hook_window_n = 0, so callers can filter these rows out)
# The values are always finite: no NaN reaches the CSV or the JSON responses.
#
# The old 0-3 s value is kept as `*_hook_0_3` / `gfp_hook_0_3` so old and new
# can be compared. Pre-registered research analyses that used the old window
# are not changed here.
# ---------------------------------------------------------------------------
HOOK_WINDOW = slice(4, 8)
LEGACY_HOOK_WINDOW = slice(0, 3)


def _hook_window(n: int) -> tuple[slice, int]:
    """Return the slice of predicted seconds used for the hook, and how many
    of them fall inside HOOK_WINDOW (0 means the short-clip fallback)."""
    start, stop = HOOK_WINDOW.start, HOOK_WINDOW.stop
    if n > start:
        end = min(stop, n)
        return slice(start, end), end - start
    return slice(max(n - 1, 0), n), 0


_CSV_DIMS = list(_BATCH_MASKS.keys())
_CSV_FIELDS = (
    ["filename", "label", "n_seconds"]
    + [f"{d}_mean"   for d in _CSV_DIMS]
    + [f"{d}_hook"   for d in _CSV_DIMS]
    + [f"{d}_hook_0_3" for d in _CSV_DIMS]
    + [f"{d}_offset" for d in _CSV_DIMS]
    + [f"{d}_peak_s" for d in _CSV_DIMS]
    + [f"{d}_ts_ratio" for d in _CSV_DIMS]
    + ["composite_raw", "gfp_mean", "gfp_hook", "gfp_hook_0_3", "gfp_offset",
       "hook_window_n", "vmPFC_TPJ_coupling", "pleasantness_index"]
)


def quick_scores(preds: np.ndarray) -> dict:
    """
    Compute per-ROI summary stats from a raw TRIBE v2 prediction array.
    Returns a flat dict suitable for the batch CSV row.
    Uses Destrieux-atlas vertex masks from roi_masks_fsaverage5.json
    (numpy-only, no nilearn needed on RunPod).

    Metrics:
      mean/hook/offset/peak_s — Berns 2020 (onset + offset outperform clip average)
                                hook = predicted s 4-8 (BOLD-lagged, see HOOK_WINDOW);
                                hook_0_3 = the old, unlagged 0-3 s window
      hook_window_n           — samples inside HOOK_WINDOW (4 full, <4 short, 0 fallback)
      ts_ratio                — transient/sustained ratio (BOLD transient lit)
      gfp_*                   — Global Field Power (Frontiers Psych 2017)
      vmPFC_TPJ_coupling      — viral circuit Pearson r (Scholz 2017)
      pleasantness_index      — left-right PFC asymmetry (Frontiers 2017)
    """
    n   = preds.shape[0]
    row: dict = {}
    roi_means: dict = {}
    hook_sl, hook_n = _hook_window(n)

    # Per-ROI stats
    ts_store: dict = {}
    for dim, idx in _BATCH_MASKS.items():
        ts = preds[:, idx].mean(axis=1)
        ts_store[dim] = ts

        mean_act  = float(ts.mean())
        hook_act  = float(ts[hook_sl].mean())
        hook_0_3  = float(ts[LEGACY_HOOK_WINDOW].mean())
        offset_act = float(ts[-min(5, n):].mean())
        peak_s    = int(ts.argmax())

        onset  = float(ts[:min(4, n)].mean())
        steady = float(ts[min(6, n):].mean()) if n > 6 else mean_act
        ts_ratio = onset / (abs(steady) + 1e-9)

        row[f"{dim}_mean"]     = round(mean_act,   6)
        row[f"{dim}_hook"]     = round(hook_act,   6)
        row[f"{dim}_hook_0_3"] = round(hook_0_3,   6)
        row[f"{dim}_offset"]   = round(offset_act, 6)
        row[f"{dim}_peak_s"]   = peak_s
        row[f"{dim}_ts_ratio"] = round(ts_ratio,   4)
        roi_means[dim] = mean_act

    row["composite_raw"] = round(compute_composite_raw(roi_means), 6)

    # Global Field Power (total cortical energy per second)
    gfp = np.sqrt((preds ** 2).mean(axis=1))
    row["gfp_mean"]   = round(float(gfp.mean()),              6)
    row["gfp_hook"]   = round(float(gfp[hook_sl].mean()),     6)
    row["gfp_hook_0_3"] = round(float(gfp[LEGACY_HOOK_WINDOW].mean()), 6)
    row["gfp_offset"] = round(float(gfp[-min(5, n):].mean()), 6)
    row["hook_window_n"] = hook_n

    # vmPFC–TPJ coupling (Scholz 2017 viral circuit) — valuation × social Pearson r
    if n >= 4:
        r = float(np.corrcoef(ts_store["valuation"], ts_store["social"])[0, 1])
        row["vmPFC_TPJ_coupling"] = round(r, 4) if np.isfinite(r) else 0.0
    else:
        row["vmPFC_TPJ_coupling"] = 0.0

    # Pleasantness Index: left-hemisphere vertices (0–10241) vs right (10242–20483)
    # Using the attention ROI (IFJ: inferior frontal + inferior precentral
    # sulci) as frontal proxy — Frontiers Psych 2017
    att_idx = _BATCH_MASKS["attention"]
    lh_att  = att_idx[att_idx < 10242]
    rh_att  = att_idx[att_idx >= 10242]
    if len(lh_att) > 0 and len(rh_att) > 0:
        pi = float(preds[:, lh_att].mean() - preds[:, rh_att].mean())
        row["pleasantness_index"] = round(pi, 6)
    else:
        row["pleasantness_index"] = 0.0

    return row


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def load_model(cache_folder: str = "./cache") -> TribeModel:
    print("Loading TRIBE v2 …")
    return TribeModel.from_pretrained("facebook/tribev2", cache_folder=cache_folder)


def run_single(model: TribeModel, path: str | None, text: str | None, label: str) -> np.ndarray:
    if path:
        if path.endswith((".mp4", ".mov", ".avi")):
            df = model.get_events_dataframe(video_path=path)
        else:
            df = model.get_events_dataframe(audio_path=path)
    elif text:
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".txt", mode="w")
        tmp.write(text)
        tmp.flush()
        os.fsync(tmp.fileno())
        tmp.close()
        df = model.get_events_dataframe(text_path=tmp.name)
        os.unlink(tmp.name)
    else:
        raise ValueError("Provide --input or --text")

    preds, _ = model.predict(events=df)
    print(f"Predictions shape: {preds.shape}")
    return preds


def main():
    parser = argparse.ArgumentParser()
    # Single-video args
    parser.add_argument("--input",       help="Path to video or audio file")
    parser.add_argument("--text",        help="Text string to analyze")
    parser.add_argument("--label",       default="content", help="Output filename label")
    # Batch args
    parser.add_argument("--batch-dir",    help="Directory of .mp4/.mov files to process")
    parser.add_argument("--rescore-dir",  help="Rescore existing *_preds.npy files without re-running inference")
    parser.add_argument("--results-csv",  default="scores.csv",
                        help="Output CSV filename (written inside --batch-dir / --rescore-dir)")
    parser.add_argument("--cache",        default="./cache", help="Model cache folder")
    args = parser.parse_args()

    if args.rescore_dir:
        # ----------------------------------------------------------------
        # RESCORE MODE — read saved .npy files, recompute ROI scores only
        # ----------------------------------------------------------------
        rescore_dir = Path(args.rescore_dir)
        npy_files = sorted(rescore_dir.glob("*_preds.npy"))
        if not npy_files:
            raise FileNotFoundError(f"No *_preds.npy files found in {rescore_dir}")
        print(f"Rescoring {len(npy_files)} .npy file(s) in {rescore_dir}")
        rows = []
        for nf in npy_files:
            label = nf.stem.replace("_preds", "")
            try:
                preds = np.load(nf)
                print(f"[{label}] shape={preds.shape}")
                row = quick_scores(preds)
                row["filename"]  = label + ".mp4"
                row["label"]     = label
                row["n_seconds"] = preds.shape[0]
                rows.append(row)
                print(f"  composite_raw={row['composite_raw']:.4f}")
            except Exception as exc:
                print(f"  ERROR: {exc} — skipping {nf.name}")
        out_csv = rescore_dir / args.results_csv
        with open(out_csv, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=_CSV_FIELDS)
            writer.writeheader()
            writer.writerows(rows)
        print(f"\nRescore complete: {len(rows)}/{len(npy_files)} succeeded → {out_csv}")

    elif args.batch_dir:
        # ----------------------------------------------------------------
        # BATCH MODE
        # ----------------------------------------------------------------
        batch_dir = Path(args.batch_dir)
        video_files = sorted(
            list(batch_dir.glob("*.mp4")) + list(batch_dir.glob("*.mov"))
        )
        if not video_files:
            raise FileNotFoundError(f"No .mp4/.mov files found in {batch_dir}")

        print(f"Found {len(video_files)} video(s) in {batch_dir}")
        model = load_model(args.cache)

        rows = []
        for vf in video_files:
            label = vf.stem
            print(f"\n[{label}] Processing …")
            try:
                preds, _ = model.predict(
                    events=model.get_events_dataframe(video_path=str(vf))
                )
                npy_path = batch_dir / f"{label}_preds.npy"
                np.save(npy_path, preds)
                print(f"  Saved: {npy_path.name}  shape={preds.shape}")

                row = quick_scores(preds)
                row["filename"]  = vf.name
                row["label"]     = label
                row["n_seconds"] = preds.shape[0]
                rows.append(row)
                print(f"  composite_raw={row['composite_raw']:.4f}")
            except Exception as exc:
                print(f"  ERROR: {exc} — skipping {vf.name}")

        out_csv = batch_dir / args.results_csv
        with open(out_csv, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=_CSV_FIELDS)
            writer.writeheader()
            writer.writerows(rows)

        print(f"\nBatch complete: {len(rows)}/{len(video_files)} succeeded → {out_csv}")
        print(f"Download {out_csv.name} for Phase 1b correlation analysis.")
        print(f"Download individual *_preds.npy files only if you need full viz.")

    else:
        # ----------------------------------------------------------------
        # SINGLE-VIDEO MODE
        # ----------------------------------------------------------------
        model = load_model(args.cache)
        preds = run_single(model, args.input, args.text, args.label)

        out_file = f"{args.label}_preds.npy"
        np.save(out_file, preds)
        print(f"Saved: {out_file}")
        print(f"Download this file, then run:")
        print(f"  python analyze.py --input {out_file} --label '{args.label}'")


if __name__ == "__main__":
    main()
