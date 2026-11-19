"""Per-second norm band: where a clip's predicted response sits against a reference set of
clips, second by second. Stage 2 of the insight pipeline (docs/INSIGHT-PIPELINE.md).

A band is built once from a reference set (e.g. the 64-ad UGC baseline) and stored as JSON:
for every predicted second and every signal (`gfp` plus each ROI in the scorer's masks) it keeps
the sorted reference values, so a new clip's value at that second gets an exact percentile rank.

`diagnose()` turns the ranks into flags: runs of consecutive seconds that sit below the low
percentile (or above the high one). Each flag carries both the predicted second and the video
second it reflects, video second = predicted second - band["lag_s"]. Predicted seconds before
the lag are treated as warm-up and never ranked.

For TRIBE v2 the lag is 0 (LAG_S): its output is already stimulus-aligned, so predicted second t
reflects video second t and there is no warm-up to exclude. tribev2 trains with the fMRI target
shifted by the haemodynamic delay (`grids/defaults.py`: FmriExtractor "offset": 5), and the
speech -> auditory cross-correlation over 64 clips peaks at lag 0. This matches the scorer's
HOOK_WINDOW (predicted s 0-3). The lag stays a band parameter so a model with lagged output
could be banded without changing this code.

Numpy only. Masks are passed in (`run_and_save._BATCH_MASKS`), so this module does not import
the GPU-only scorer.
"""
from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from pathlib import Path

import numpy as np

PERCENTILES = (10, 25, 50, 75, 90)
LAG_S = 0           # TRIBE v2 output is stimulus-aligned: predicted second t ~ video second t
MIN_N = 20          # a second is in the band only if at least this many reference clips reach it
BAND_VERSION = 1


def timecourses(preds: np.ndarray, masks: Mapping[str, np.ndarray]) -> dict[str, np.ndarray]:
    """Per-second signals for one clip: global field power plus the mean of each ROI mask."""
    if preds.ndim != 2:
        raise ValueError(f"preds must be (seconds, vertices), got shape {preds.shape}")
    out = {"gfp": np.sqrt((preds.astype(np.float64) ** 2).mean(axis=1))}
    for dim, idx in masks.items():
        out[dim] = preds[:, idx].astype(np.float64).mean(axis=1)
    return out


def build_band(clips: Iterable[Mapping[str, np.ndarray]], *, name: str, min_n: int = MIN_N,
               meta: Mapping | None = None) -> dict:
    """Build a band from reference clips' timecourses (outputs of `timecourses`).

    The band covers predicted seconds 0..T-1, where T is the last second that at least
    `min_n` clips reach. Shorter clips simply stop contributing after their last second.
    """
    clips = list(clips)
    if len(clips) < min_n:
        raise ValueError(f"need at least {min_n} reference clips, got {len(clips)}")
    signals = list(clips[0])
    if any(list(c) != signals for c in clips):
        raise ValueError("all reference clips must have the same signals")
    for c in clips:
        _check_clip(c)
    lengths = np.array([len(c[signals[0]]) for c in clips])
    n_per_s = [int((lengths > t).sum()) for t in range(int(lengths.max()))]
    covered = sum(1 for n in n_per_s if n >= min_n)   # n_per_s is non-increasing

    band = {"version": BAND_VERSION, "name": name, "n_clips": len(clips), "min_n": min_n,
            "lag_s": LAG_S, "percentiles": list(PERCENTILES), "n_seconds": covered,
            "n_per_second": n_per_s[:covered], "meta": dict(meta or {}), "signals": {}}
    for sig in signals:
        per_s = []
        for t in range(covered):
            vals = np.sort([c[sig][t] for c in clips if len(c[sig]) > t])
            per_s.append(vals)
        band["signals"][sig] = {
            "pct": {str(p): [round(float(np.percentile(v, p)), 6) for v in per_s] for p in PERCENTILES},
            "sorted": [[round(float(x), 6) for x in v] for v in per_s],
        }
    return band


def _check_clip(tc: Mapping[str, np.ndarray]) -> int:
    """All signals the same length and finite (NaN would rank as P100 or skew a band)."""
    lengths = {len(v) for v in tc.values()}
    if len(lengths) != 1:
        raise ValueError(f"signals have different lengths: {sorted(lengths)}")
    for sig, v in tc.items():
        if not np.all(np.isfinite(v)):
            raise ValueError(f"signal {sig!r} has non-finite values")
    return lengths.pop()


def percentile_rank(value: float, sorted_vals) -> float:
    """Share of reference values below `value` (ties count half), in 0..100."""
    sv = np.asarray(sorted_vals, dtype=np.float64)
    lo = np.searchsorted(sv, value, side="left")
    hi = np.searchsorted(sv, value, side="right")
    return float(100.0 * (lo + hi) / 2.0 / len(sv))


def _runs(mask: np.ndarray) -> list[tuple[int, int]]:
    """Inclusive (start, end) index pairs of consecutive True values."""
    out, start = [], None
    for i, m in enumerate(mask):
        if m and start is None:
            start = i
        elif not m and start is not None:
            out.append((start, i - 1))
            start = None
    if start is not None:
        out.append((start, len(mask) - 1))
    return out


def diagnose(tc: Mapping[str, np.ndarray], band: Mapping, *, low: float = 25.0, high: float = 75.0,
             min_run: int = 2) -> dict:
    """Rank a clip's timecourses against a band and flag sustained low/high stretches.

    Seconds before the band's lag (warm-up; none for TRIBE v2, lag 0) and past the band's
    coverage are not ranked.
    Flags are sorted by size: distance from the median times run length, largest first.
    """
    lag = int(band["lag_s"])
    n_clip = _check_clip(tc)
    stop = min(n_clip, int(band["n_seconds"]))
    ranks: dict[str, list[float | None]] = {}
    flags = []
    missing = sorted(set(band["signals"]) ^ set(tc))
    for sig, b in band["signals"].items():
        if sig not in tc:
            continue
        r: list[float | None] = [None] * n_clip
        for t in range(lag, stop):
            # band values are stored rounded to 6 dp; round the query the same way so ties stay ties
            r[t] = round(percentile_rank(round(float(tc[sig][t]), 6), b["sorted"][t]), 1)
        ranks[sig] = r
        arr = np.array([np.nan if x is None else x for x in r], dtype=np.float64)
        with np.errstate(invalid="ignore"):
            masks = (("low", arr < low), ("high", arr > high))
        for direction, mask in masks:
            for s, e in _runs(mask):
                if e - s + 1 < min_run:
                    continue
                seg = arr[s:e + 1]
                flags.append({
                    "signal": sig, "direction": direction,
                    "pred_start_s": s, "pred_end_s": e,
                    "video_start_s": s - lag, "video_end_s": e - lag,
                    "mean_rank": round(float(seg.mean()), 1),
                    "extreme_rank": round(float(seg.min() if direction == "low" else seg.max()), 1),
                })
    flags.sort(key=lambda f: abs(f["mean_rank"] - 50.0) * (f["pred_end_s"] - f["pred_start_s"] + 1),
               reverse=True)
    return {"band": band["name"], "n_seconds": n_clip,
            "ranked_seconds": [lag, stop - 1] if stop > lag else None,
            "low": low, "high": high, "missing_signals": missing, "ranks": ranks, "flags": flags}


def save_band(band: Mapping, path: Path) -> None:
    Path(path).write_text(json.dumps(band, separators=(",", ":")))


def load_band(path: Path) -> dict:
    band = json.loads(Path(path).read_text())
    if band.get("version") != BAND_VERSION:
        raise ValueError(f"{path}: band version {band.get('version')} != {BAND_VERSION}")
    return band
