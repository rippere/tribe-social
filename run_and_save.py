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
import os
import argparse
import tempfile
import numpy as np
from pathlib import Path

os.environ["HF_TOKEN"] = os.environ.get("HF_TOKEN", "your_token_here")
os.environ["HF_HUB_DOWNLOAD_TIMEOUT"] = "300"

from tribev2.demo_utils import TribeModel


# ---------------------------------------------------------------------------
# Approximate ROI masks for RunPod (numpy-only, no neuromaps dependency).
# These match the Phase 0 baseline; analyze.py uses full HCP MMP1.0 masks locally.
# ---------------------------------------------------------------------------
_R = 10242          # right hemisphere vertex offset (fsaverage5)
_N_VERTS = 20484    # total vertices in TRIBE v2 output


def _bilateral(*ranges: tuple[int, int]) -> np.ndarray:
    lh = np.concatenate([np.arange(a, b) for a, b in ranges])
    lh = lh[lh < _R]   # guard: LH indices must be < 10242
    rh = lh + _R
    return np.concatenate([lh, rh])


# fsaverage5 LH vertex approximations (all < 10242).
# social/auditory were previously out-of-bounds (indices 12000+ / 10200+).
_BATCH_MASKS = {
    "attention": _bilateral((8200, 8350), (8350, 8500)),
    "social":    _bilateral((6500, 6900),),    # TPJ: posterior parietal-temporal
    "language":  _bilateral((7800, 8000),),
    "valuation": _bilateral((400, 700),),
    "auditory":  _bilateral((8800, 9200),),    # STS: lateral superior temporal
    "motion":    _bilateral((9800, 10000),),
    "narrative": _bilateral((1200, 1600),),
}

_WEIGHTS = {
    "attention": 0.25, "social": 0.30, "language": 0.15,
    "valuation": 0.20, "auditory": 0.05, "motion": 0.03, "narrative": 0.02,
}

_CSV_DIMS = list(_BATCH_MASKS.keys())
_CSV_FIELDS = (
    ["filename", "label", "n_seconds"]
    + [f"{d}_mean"   for d in _CSV_DIMS]
    + [f"{d}_hook"   for d in _CSV_DIMS]
    + [f"{d}_offset" for d in _CSV_DIMS]
    + [f"{d}_peak_s" for d in _CSV_DIMS]
    + [f"{d}_ts_ratio" for d in _CSV_DIMS]
    + ["composite_raw", "gfp_mean", "gfp_hook", "gfp_offset",
       "vmPFC_TPJ_coupling", "pleasantness_index"]
)


def quick_scores(preds: np.ndarray) -> dict:
    """
    Compute per-ROI summary stats from a raw TRIBE v2 prediction array.
    Returns a flat dict suitable for the batch CSV row.
    Uses approximate vertex masks (numpy-only, no nilearn needed on RunPod).

    Metrics:
      mean/hook/offset/peak_s — Berns 2020 (onset + offset outperform clip average)
      ts_ratio                — transient/sustained ratio (BOLD transient lit)
      gfp_*                   — Global Field Power (Frontiers Psych 2017)
      vmPFC_TPJ_coupling      — viral circuit Pearson r (Scholz 2017)
      pleasantness_index      — left-right PFC asymmetry (Frontiers 2017)
    """
    n   = preds.shape[0]
    row: dict = {}
    weighted_sum = 0.0

    # Per-ROI stats
    ts_store: dict = {}
    for dim, idx in _BATCH_MASKS.items():
        ts = preds[:, idx].mean(axis=1)
        ts_store[dim] = ts

        mean_act  = float(ts.mean())
        hook_act  = float(ts[:min(3, n)].mean())
        offset_act = float(ts[-min(5, n):].mean())
        peak_s    = int(ts.argmax())

        onset  = float(ts[:min(4, n)].mean())
        steady = float(ts[min(6, n):].mean()) if n > 6 else mean_act
        ts_ratio = onset / (abs(steady) + 1e-9)

        row[f"{dim}_mean"]     = round(mean_act,   6)
        row[f"{dim}_hook"]     = round(hook_act,   6)
        row[f"{dim}_offset"]   = round(offset_act, 6)
        row[f"{dim}_peak_s"]   = peak_s
        row[f"{dim}_ts_ratio"] = round(ts_ratio,   4)
        weighted_sum += mean_act * _WEIGHTS[dim]

    row["composite_raw"] = round(weighted_sum, 6)

    # Global Field Power (total cortical energy per second)
    gfp = np.sqrt((preds ** 2).mean(axis=1))
    row["gfp_mean"]   = round(float(gfp.mean()),              6)
    row["gfp_hook"]   = round(float(gfp[:min(3, n)].mean()),  6)
    row["gfp_offset"] = round(float(gfp[-min(5, n):].mean()), 6)

    # vmPFC–TPJ coupling (Scholz 2017 viral circuit) — valuation × social Pearson r
    if n >= 4:
        r = float(np.corrcoef(ts_store["valuation"], ts_store["social"])[0, 1])
        row["vmPFC_TPJ_coupling"] = round(r, 4) if np.isfinite(r) else 0.0
    else:
        row["vmPFC_TPJ_coupling"] = 0.0

    # Pleasantness Index: left-hemisphere vertices (0–10241) vs right (10242–20483)
    # Using attention ROI (IFJa/IFJp) as frontal proxy — Frontiers Psych 2017
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
