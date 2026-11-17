"""Shot-cut content-event extractor ("cuts" event family).

Runs inside the `tribe` container on the Spark (CPU only):

    python /tribe/insight/extract_cuts.py            # all included clips
    python /tribe/insight/extract_cuts.py --recompute

Decoding goes through the ffmpeg CLI (OpenCV's bundled ffmpeg cannot decode
AV1, which ~1/4 of the reference clips use). Each clip is decoded once at
native frame rate (passthrough timestamps from `showinfo`) and downscaled to
128x128, then per-transition signals are computed:

  content  - PySceneDetect-style HSV content value: mean over pixels of
             (|dH| + |dS| + |dV|) / 3, 0..255.
  gray_mad - mean absolute grayscale difference, 0..255 (motion energy).
  hist     - Bhattacharyya distance between H-S histograms, 0..1.

Cut rule (adaptive, after PySceneDetect's AdaptiveDetector): transition i is a
cut when
  content[i] >= MIN_CONTENT                      (absolute floor), and
  content[i] / mean(content of non-duplicate neighbours within +-WINDOW frames)
            >= MIN_RATIO                         (it is a spike, not sustained motion)
or when content[i] >= HARD_CONTENT and hist[i] >= HARD_HIST (unconditional
very large change). Cuts closer than MIN_SHOT_S are merged (keep the largest).
Duplicate frames (gray_mad < DUP_MAD, e.g. telecined / frame-repeated uploads)
are ignored as neighbours so they do not deflate the local baseline.

Event time t = timestamp of the first frame of the new shot (video seconds).

per_second features (one value per video second, length ceil(duration)):
  cuts               - number of detected cuts in [k, k+1)
  motion_energy      - mean gray_mad over non-cut transitions in [k, k+1),
                       z-scored within the clip (mean 0, sd 1)
  motion_energy_raw  - the same before normalisation (0..255 units)

Per-frame signals are cached under ~/tribe/insight/cuts_cache/ so the
threshold can be re-tuned without decoding again. No clip identifiers are
stored in this file; per-clip outputs stay on the Spark.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import subprocess
import sys
from multiprocessing import Pool

import cv2
import numpy as np

UGC_DIR = "/tribe/ugc"
VETTING = "/tribe/work/vetting.json"
OUT_JSON = "/tribe/insight/events/cuts.json"
CACHE_DIR = "/tribe/insight/cuts_cache"

SIZE = 128
DUP_MAD = 0.35
WINDOW = 4            # frames on each side used for the local baseline
MIN_CONTENT = 12.0
MIN_RATIO = 3.0
HARD_CONTENT = 45.0
HARD_HIST = 0.5
MIN_SHOT_S = 0.25
N_WORKERS = 12

PTS_RE = re.compile(r"pts_time:\s*([-0-9.]+)")


def probe_duration(path: str) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", path],
        capture_output=True, text=True, check=True).stdout.strip()
    return float(out)


def decode_signals(path: str) -> dict:
    """Decode all frames once; return per-transition signals and timestamps."""
    cmd = ["ffmpeg", "-hide_banner", "-nostats", "-threads", "2", "-i", path,
           "-an", "-sn", "-fps_mode", "passthrough",
           "-vf", f"scale={SIZE}:{SIZE}:flags=area,showinfo",
           "-f", "rawvideo", "-pix_fmt", "bgr24", "-"]
    proc = subprocess.run(cmd, capture_output=True, check=True)
    frame_bytes = SIZE * SIZE * 3
    n = len(proc.stdout) // frame_bytes
    frames = np.frombuffer(proc.stdout[: n * frame_bytes], np.uint8).reshape(n, SIZE, SIZE, 3)
    pts = [float(m.group(1)) for m in PTS_RE.finditer(proc.stderr.decode("utf-8", "replace"))]
    if len(pts) != n:  # fall back to uniform spacing if showinfo parsing misaligns
        dur = probe_duration(path)
        pts = list(np.arange(n) * dur / max(n, 1))
    pts = np.asarray(pts, dtype=np.float64)

    content = np.zeros(n, np.float32)
    gray_mad = np.zeros(n, np.float32)
    hist = np.zeros(n, np.float32)
    prev_hsv = prev_gray = prev_h = None
    for i in range(n):
        f = cv2.GaussianBlur(frames[i], (3, 3), 0)
        hsv_u8 = cv2.cvtColor(f, cv2.COLOR_BGR2HSV)
        hsv = hsv_u8.astype(np.int16)
        gray = cv2.cvtColor(f, cv2.COLOR_BGR2GRAY).astype(np.int16)
        h = cv2.calcHist([hsv_u8], [0, 1], None, [30, 32], [0, 180, 0, 256])
        cv2.normalize(h, h, 1.0, 0.0, cv2.NORM_L1)
        if prev_hsv is not None:
            d = np.abs(hsv - prev_hsv)
            dh = np.minimum(d[..., 0], 180 - d[..., 0])  # hue is circular
            content[i] = float((dh.mean() + d[..., 1].mean() + d[..., 2].mean()) / 3.0)
            gray_mad[i] = float(np.abs(gray - prev_gray).mean())
            hist[i] = float(cv2.compareHist(prev_h, h, cv2.HISTCMP_BHATTACHARYYA))
        prev_hsv, prev_gray, prev_h = hsv, gray, h
    return {"pts": pts, "content": content, "gray_mad": gray_mad, "hist": hist}


def detect_cuts(sig: dict, min_ratio: float = MIN_RATIO, min_content: float = MIN_CONTENT,
                window: int = WINDOW) -> tuple[list[int], np.ndarray]:
    """Return indices of transitions flagged as cuts, plus the ratio array."""
    content, gm, hist = sig["content"], sig["gray_mad"], sig["hist"]
    n = len(content)
    valid = gm >= DUP_MAD
    valid[0] = False
    ratio = np.zeros(n, np.float32)
    cand = []
    for i in range(1, n):
        if not valid[i]:
            continue
        lo, hi = max(1, i - window), min(n, i + window + 1)
        nb = [j for j in range(lo, hi) if j != i and valid[j]]
        base = float(np.mean(content[nb])) if nb else 0.0
        ratio[i] = content[i] / max(base, 1.0)
        spike = content[i] >= min_content and ratio[i] >= min_ratio
        hard = content[i] >= HARD_CONTENT and hist[i] >= HARD_HIST
        if spike or hard:
            cand.append(i)
    # merge cuts closer than MIN_SHOT_S, keep the largest content value
    pts = sig["pts"]
    cuts: list[int] = []
    for i in cand:
        if cuts and pts[i] - pts[cuts[-1]] < MIN_SHOT_S:
            if content[i] > content[cuts[-1]]:
                cuts[-1] = i
        else:
            cuts.append(i)
    return cuts, ratio


def per_second(sig: dict, cuts: list[int], duration: float) -> dict:
    n_sec = int(math.ceil(duration - 1e-6))
    pts = sig["pts"]
    gm = sig["gray_mad"]
    cut_set = set(cuts)
    counts = np.zeros(n_sec, int)
    for i in cuts:
        counts[min(int(pts[i]), n_sec - 1)] += 1
    sums = np.zeros(n_sec)
    ns = np.zeros(n_sec)
    for i in range(1, len(gm)):
        if i in cut_set:
            continue
        k = min(int(max(pts[i], 0.0)), n_sec - 1)
        sums[k] += gm[i]
        ns[k] += 1
    raw = np.where(ns > 0, sums / np.maximum(ns, 1), np.nan)
    if np.isnan(raw).any():  # empty seconds (rare): carry nearest value
        idx = np.where(~np.isnan(raw))[0]
        raw = np.interp(np.arange(n_sec), idx, raw[idx]) if len(idx) else np.zeros(n_sec)
    sd = raw.std()
    z = (raw - raw.mean()) / sd if sd > 1e-9 else np.zeros(n_sec)
    return {"cuts": counts.tolist(),
            "motion_energy": [round(float(x), 4) for x in z],
            "motion_energy_raw": [round(float(x), 4) for x in raw]}


def process(args: tuple[str, bool]) -> tuple[str, dict]:
    stem, recompute = args
    path = os.path.join(UGC_DIR, stem + ".mp4")
    cache = os.path.join(CACHE_DIR, stem + ".npz")
    if os.path.exists(cache) and not recompute:
        z = np.load(cache)
        sig = {k: z[k] for k in ("pts", "content", "gray_mad", "hist")}
    else:
        sig = decode_signals(path)
        np.savez_compressed(cache, **sig)
    duration = probe_duration(path)
    cuts, _ = detect_cuts(sig)
    events = [{"type": "cut", "t": round(float(sig["pts"][i]), 3)} for i in cuts]
    return stem, {"duration_s": round(duration, 3), "events": events,
                  "per_second": per_second(sig, cuts, duration)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--recompute", action="store_true")
    ap.add_argument("--workers", type=int, default=N_WORKERS)
    a = ap.parse_args()
    os.makedirs(CACHE_DIR, exist_ok=True)
    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    stems = [x["name"] for x in json.load(open(VETTING)) if x.get("include")]
    with Pool(min(a.workers, 12)) as pool:
        results = dict(pool.map(process, [(s, a.recompute) for s in stems]))
    out = {s: results[s] for s in stems}
    tmp = OUT_JSON + ".tmp"
    with open(tmp, "w") as fh:
        json.dump(out, fh)
    os.replace(tmp, OUT_JSON)
    n_cuts = [len(v["events"]) for v in out.values()]
    rates = [len(v["events"]) / v["duration_s"] for v in out.values()]
    print(f"clips={len(out)} cuts={sum(n_cuts)} median_cuts/clip={np.median(n_cuts):.1f} "
          f"median_cuts/min={60 * np.median(rates):.1f} zero-cut clips={sum(c == 0 for c in n_cuts)}",
          file=sys.stderr)


if __name__ == "__main__":
    main()
