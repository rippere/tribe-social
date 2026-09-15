"""
Corpus writer — add scored uploads to in-memory corpus and flush to disk.
Railway has no persistent volume, so flush writes back to the committed data dir.
"""
import json
import statistics
from datetime import datetime
from pathlib import Path

from app import state
from tribe_scoring.composite import compute_verdict

_DATA_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "corpus.json"

_ROI_KEYS = ["vmPFC", "TPJ", "IFJa", "IFJp", "area_45", "MT_V5"]


def add_video_to_corpus(job_id: str, filename: str, roi: dict[str, float], composite_score: float) -> None:
    if state.corpus_data is None:
        state.corpus_data = {
            "videos": [],
            "stats": {
                "total_videos": 0,
                "avg_composite": 0.0,
                "post_count": 0,
                "median_likes_per_1k": 0.0,
                "roi_means": {},
                "correlations": {},
                "go_no_go": {},
                "composite_r": 0.0,
                "rois_above_threshold": [],
            },
        }

    entry = {
        "video_id": f"upload_{job_id[:8]}",
        "creator": "user_upload",
        "filename": filename,
        "views": 0,
        "likes": 0,
        "shares": 0,
        "saves": 0,
        "comments": 0.0,
        "likes_per_1k": 0.0,
        "vmPFC_mean": roi.get("vmPFC", 0.0),
        "TPJ_mean": roi.get("TPJ", 0.0),
        "IFJa_mean": roi.get("IFJa", 0.0),
        "IFJp_mean": roi.get("IFJp", 0.0),
        "area_45_mean": roi.get("area_45", 0.0),
        "MT_V5_mean": roi.get("MT_V5", 0.0),
        "composite_score": composite_score,
        "verdict": compute_verdict(composite_score),
        "uploaded_at": datetime.utcnow().isoformat(),
    }
    state.corpus_data["videos"].append(entry)
    _recompute_stats()


def flush_to_disk() -> None:
    if state.corpus_data is None:
        return
    _DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(_DATA_PATH, "w") as f:
        json.dump(state.corpus_data, f, indent=2)


def _recompute_stats() -> None:
    videos = state.corpus_data["videos"]
    if not videos:
        return

    scores = [v["composite_score"] for v in videos]
    roi_means: dict[str, float] = {}
    for roi in _ROI_KEYS:
        col = f"{roi}_mean"
        vals = [v[col] for v in videos if col in v]
        roi_means[roi] = round(statistics.mean(vals), 4) if vals else 0.0

    state.corpus_data["stats"].update(
        {
            "total_videos": len(videos),
            "avg_composite": round(statistics.mean(scores), 1),
            "roi_means": roi_means,
        }
    )
