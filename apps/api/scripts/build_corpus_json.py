"""
Build corpus.json from scores.csv + engagement.csv.

Run with:
    /mnt/external/Projects/tribe-social/.venv/bin/python \
        apps/api/scripts/build_corpus_json.py
"""

import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

# ── Paths ──────────────────────────────────────────────────────────────────────
PROTOTYPE_DIR   = Path("/mnt/external/Projects/tribe-social")
SCORES_PATH     = PROTOTYPE_DIR / "scores.csv"
ENGAGEMENT_PATH = PROTOTYPE_DIR / "engagement.csv"

REPO_ROOT   = Path(__file__).resolve().parents[1]       # apps/api/
DATA_DIR    = REPO_ROOT / "data"
OUTPUT_PATH = DATA_DIR / "corpus.json"

DATA_DIR.mkdir(parents=True, exist_ok=True)

ROI_COLS = [
    "vmPFC_mean", "TPJ_mean", "IFJa_mean",
    "IFJp_mean", "area_45_mean", "MT_V5_mean",
]

# short keys used in the stats block (strip "_mean")
ROI_SHORT = {
    "vmPFC_mean":   "vmPFC",
    "TPJ_mean":     "TPJ",
    "IFJa_mean":    "IFJa",
    "IFJp_mean":    "IFJp",
    "area_45_mean": "area_45",
    "MT_V5_mean":   "MT_V5",
}


def min_max(series: pd.Series) -> pd.Series:
    lo, hi = series.min(), series.max()
    if hi == lo:
        return pd.Series(0.0, index=series.index)
    return (series - lo) / (hi - lo)


def load_and_normalize() -> pd.DataFrame:
    scores = pd.read_csv(SCORES_PATH)
    eng    = pd.read_csv(ENGAGEMENT_PATH)

    # ── Column rename: TRIBE v2 raw → display names ───────────────────────────
    col_map = {
        "valuation_mean":  "vmPFC_mean",
        "social_mean":     "TPJ_mean",
        "attention_mean":  "IFJa_mean",
        "language_mean":   "area_45_mean",
        "motion_mean":     "MT_V5_mean",
    }
    scores = scores.rename(columns=col_map)

    # IFJp_mean — proxy from IFJa (no dedicated column)
    scores["IFJp_mean"] = scores["IFJa_mean"] * 0.90

    # ── Min-max normalise ROI columns to 0–1 ─────────────────────────────────
    for col in ROI_COLS:
        scores[col] = min_max(scores[col]).round(4)

    # ── Composite score 0–100 ─────────────────────────────────────────────────
    scores["composite_score"] = (
        min_max(scores["composite_raw"]) * 100
    ).round(1)

    # ── Identity columns ──────────────────────────────────────────────────────
    scores["video_id"] = scores["filename"].str.replace(".mp4", "", regex=False)
    scores["creator"]  = scores["filename"].str.split("_").str[0]

    # ── Merge engagement ──────────────────────────────────────────────────────
    merged = scores.merge(eng, on="filename", how="left")

    # Proxy metric: likes per 1 000 views
    merged["likes_per_1k"] = (
        merged["likes"] / merged["views"].replace(0, np.nan) * 1000
    ).round(1)

    # Ensure shares / saves columns exist
    merged["shares"] = merged.get("shares", pd.Series(0, index=merged.index)).fillna(0).astype(int)
    merged["saves"]  = 0

    return merged


def build_corpus() -> dict:
    df = load_and_normalize()

    # ── Videos list ───────────────────────────────────────────────────────────
    keep = [
        "video_id", "creator", "filename",
        "views", "likes", "shares", "saves", "comments", "likes_per_1k",
    ] + ROI_COLS + ["composite_score"]
    keep = [c for c in keep if c in df.columns]

    videos = []
    for _, row in df[keep].iterrows():
        v = row.to_dict()
        # replace NaN with None so JSON serialises cleanly
        v = {k: (None if (isinstance(val, float) and np.isnan(val)) else val)
             for k, val in v.items()}
        videos.append(v)

    # ── Corpus stats ──────────────────────────────────────────────────────────
    total_videos       = len(df)
    avg_composite      = round(float(df["composite_score"].mean()), 1)
    post_count         = int((df["composite_score"] >= 65).sum())
    median_likes_per_1k = round(float(df["likes_per_1k"].median()), 1)

    roi_means = {
        ROI_SHORT[col]: round(float(df[col].mean()), 4)
        for col in ROI_COLS
    }

    # ── Correlations ──────────────────────────────────────────────────────────
    valid = df[["composite_score", "likes_per_1k"] + ROI_COLS].dropna()

    def safe_pearson(a: pd.Series, b: pd.Series) -> dict:
        if len(a) < 3:
            return {"r": None, "p": None}
        r, p = stats.pearsonr(a, b)
        return {"r": round(float(r), 4), "p": round(float(p), 4)}

    correlations: dict = {
        "composite_vs_likes_per_1k": safe_pearson(
            valid["composite_score"], valid["likes_per_1k"]
        )
    }
    for col in ROI_COLS:
        key = f"{ROI_SHORT[col]}_vs_likes_per_1k"
        correlations[key] = safe_pearson(valid[col], valid["likes_per_1k"])

    # ── Go / No-Go ────────────────────────────────────────────────────────────
    composite_r = correlations["composite_vs_likes_per_1k"]["r"] or 0.0
    rois_above  = sum(
        1 for col in ROI_COLS
        if (correlations[f"{ROI_SHORT[col]}_vs_likes_per_1k"]["r"] or 0.0) > 0.3
    )
    go_no_go = "GO" if (composite_r > 0.4 or rois_above >= 2) else "NO-GO"

    stats_block = {
        "total_videos":        total_videos,
        "avg_composite":       avg_composite,
        "post_count":          post_count,
        "median_likes_per_1k": median_likes_per_1k,
        "roi_means":           roi_means,
        "correlations":        correlations,
        "go_no_go":            go_no_go,
        "composite_r":         round(float(composite_r), 4),
        "rois_above_threshold": rois_above,
    }

    return {"videos": videos, "stats": stats_block}


if __name__ == "__main__":
    corpus = build_corpus()

    with open(OUTPUT_PATH, "w") as f:
        json.dump(corpus, f, indent=2)

    s = corpus["stats"]
    print(f"corpus.json written to {OUTPUT_PATH}")
    print(f"  total_videos:        {s['total_videos']}")
    print(f"  avg_composite:       {s['avg_composite']}")
    print(f"  post_count (>=65):   {s['post_count']}")
    print(f"  median_likes_per_1k: {s['median_likes_per_1k']}")
    print(f"  roi_means:           {s['roi_means']}")
    print(f"  composite_r:         {s['composite_r']}  p={s['correlations']['composite_vs_likes_per_1k']['p']}")
    print(f"  rois_above_0.3:      {s['rois_above_threshold']}")
    print(f"  go_no_go:            {s['go_no_go']}")
