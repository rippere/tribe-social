"""Faces content-event extractor for the TRIBE insight study.

Samples each included reference clip at 4 fps, runs OpenCV's YuNet face
detector (cv2.FaceDetectorYN, CPU) on every sample, and writes the shared
event format:

    {"<stem>": {"duration_s": float,
                "events": [{"type": "face_appear"|"face_disappear", "t": float}],
                "per_second": {"face": [...], "face_area": [...]}}}

Definitions
-----------
* A sample "has a face" if YuNet returns at least one box with score >=
  --score-thr whose area is >= --min-area of the frame.
* per_second bins are [s, s+1) video seconds, s = 0 .. ceil(duration)-1
  (matches the number of rows TRIBE predicts for a clip).
    - face      : fraction of that second's samples with a face.
    - face_area : mean over that second's samples of
                  (largest face box area / frame area); samples without a
                  face contribute 0.
    - a trailing partial second with no sample on the 0.25 s grid takes
      the nearest sample (within 0.5 s); otherwise the value is null.
* Events use a debounced presence state (hysteresis): the state only flips
  when the opposite value holds for >= --min-run seconds (default 0.5 s =
  2 samples at 4 fps). face_appear is stamped at the first sample of a
  present run that follows a stable absent state (so the face was absent
  for >= 0.5 s before it); face_disappear is the mirror. The initial state
  at t=0 is not an event.

Raw per-sample detections (boxes in downscaled-frame pixels, see
frame_hw) go to --raw-out for spot checks.

Decoding uses an ffmpeg pipe (fps=4 filter) because the container's OpenCV
FFmpeg backend cannot decode the AV1 clips.

Run inside the `tribe` container, e.g.
    python extract_faces.py --workers 12
"""
from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import sys
import time
from multiprocessing import Pool

import cv2
import numpy as np

FPS_SAMPLE = 4.0

DEFAULTS = {
    "vetting": "/tribe/work/vetting.json",
    "clips": "/tribe/ugc",
    "model": "/tribe/insight/models/face_detection_yunet_2023mar.onnx",
    "out": "/tribe/insight/events/faces.json",
    "raw_out": "/tribe/insight/raw/faces_samples.json",
}

# Set per worker by _init_worker.
_DET = None
_CFG = None


def _init_worker(cfg: dict) -> None:
    global _DET, _CFG
    cv2.setNumThreads(1)
    _CFG = cfg
    _DET = cv2.FaceDetectorYN.create(
        cfg["model"], "", (320, 320),
        score_threshold=cfg["score_thr"], nms_threshold=0.3, top_k=50,
    )


def probe(path: str) -> tuple[float, int, int, str]:
    """Return (duration_s, display_width, display_height, codec)."""
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
         "stream=width,height,codec_name:stream_side_data=rotation:format=duration",
         "-of", "json", path],
        capture_output=True, text=True, check=True,
    ).stdout
    info = json.loads(out)
    st = info["streams"][0]
    w, h = int(st["width"]), int(st["height"])
    rot = 0
    for sd in st.get("side_data_list", []) or []:
        if "rotation" in sd:
            rot = int(sd["rotation"])
    if abs(rot) % 180 == 90:
        w, h = h, w
    return float(info["format"]["duration"]), w, h, st.get("codec_name", "")


def detect(frame: np.ndarray) -> list[dict]:
    """Run YuNet on one (already downscaled) BGR frame; boxes in its pixels."""
    h, w = frame.shape[:2]
    _DET.setInputSize((w, h))
    _, faces = _DET.detect(frame)
    out = []
    if faces is None:
        return out
    for f in faces:
        x, y, bw, bh = (float(v) for v in f[:4])
        # clip box to frame
        x0, y0 = max(0.0, x), max(0.0, y)
        x1, y1 = min(float(w), x + bw), min(float(h), y + bh)
        if x1 <= x0 or y1 <= y0:
            continue
        area = (x1 - x0) * (y1 - y0) / (w * h)
        if area < _CFG["min_area"]:
            continue
        out.append({"box": [round(x0, 1), round(y0, 1), round(x1 - x0, 1),
                            round(y1 - y0, 1)],
                    "score": round(float(f[14]), 3),
                    "area": round(area, 5)})
    return out


def sample_clip(path: str, w: int, h: int, codec: str):
    """Decode with ffmpeg at 4 fps (fps filter, nearest-frame rounding),
    downscaled so the long side is <= max_side. Yields (t, frame) with
    t = k / 4 video seconds. OpenCV's FFmpeg backend here cannot decode AV1,
    so ffmpeg (libdav1d for AV1) is used for every codec for consistency."""
    scale = min(1.0, _CFG["max_side"] / max(w, h))
    sw = max(2, int(round(w * scale / 2)) * 2)
    sh = max(2, int(round(h * scale / 2)) * 2)
    cmd = ["ffmpeg", "-v", "error", "-nostdin", "-threads", "1"]
    if codec == "av1":
        cmd += ["-c:v", "libdav1d"]
    cmd += ["-i", path, "-an", "-sn",
            "-vf", f"fps={FPS_SAMPLE:g}:round=near,scale={sw}:{sh}:flags=area",
            "-pix_fmt", "bgr24", "-f", "rawvideo", "-threads", "1", "pipe:1"]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    nbytes = sw * sh * 3
    k = 0
    finished = False
    try:
        while True:
            buf = proc.stdout.read(nbytes)
            if len(buf) < nbytes:
                break
            yield k / FPS_SAMPLE, np.frombuffer(buf, np.uint8).reshape(sh, sw, 3)
            k += 1
        finished = True
    finally:
        if not finished:
            proc.kill()
        proc.stdout.close()
        err = proc.stderr.read().decode(errors="replace")
        proc.stderr.close()
        rc = proc.wait()
    if finished and rc != 0:
        raise RuntimeError(f"ffmpeg failed on {os.path.basename(path)}: {err[:300]}")


def debounced_events(times: list[float], present: list[bool],
                     min_run: int) -> list[dict]:
    events = []
    if not present:
        return events
    state = present[0]
    i, n = 0, len(present)
    while i < n:
        if present[i] != state:
            j = i
            while j < n and present[j] == present[i]:
                j += 1
            if j - i >= min_run:
                state = present[i]
                events.append({"type": "face_appear" if state else "face_disappear",
                               "t": round(times[i], 3)})
            i = j
        else:
            i += 1
    return events


def process(stem: str):
    t0 = time.time()
    path = os.path.join(_CFG["clips"], stem + ".mp4")
    duration, w, h, codec = probe(path)
    n_expected = int(math.ceil(duration * FPS_SAMPLE - 1e-6))
    times, has_face, largest, raw = [], [], [], []
    frame_hw = None
    for t, frame in sample_clip(path, w, h, codec):
        if t >= duration:
            break
        frame_hw = frame.shape[:2]
        dets = detect(frame)
        times.append(t)
        has_face.append(bool(dets))
        largest.append(max((d["area"] for d in dets), default=0.0))
        raw.append({"t": t, "dets": dets})

    n_sec = int(math.ceil(duration - 1e-6))
    face_ps, area_ps = [], []
    t_arr = np.asarray(times)
    hf = np.asarray(has_face, dtype=float)
    la = np.asarray(largest, dtype=float)
    for s in range(n_sec):
        m = (t_arr >= s) & (t_arr < s + 1)
        if not m.any() and len(t_arr):
            # trailing partial second shorter than one sample step: borrow
            # the nearest sample if it is within 0.5 s of the bin start
            j = int(np.argmin(np.abs(t_arr - s)))
            if abs(t_arr[j] - s) <= 0.5:
                m = np.zeros_like(t_arr, dtype=bool)
                m[j] = True
        if m.any():
            face_ps.append(round(float(hf[m].mean()), 4))
            area_ps.append(round(float(la[m].mean()), 5))
        else:
            face_ps.append(None)
            area_ps.append(None)

    min_run = max(1, int(round(_CFG["min_run_s"] * FPS_SAMPLE)))
    events = debounced_events(times, has_face, min_run)
    rec = {
        "duration_s": round(duration, 3),
        "events": events,
        "per_second": {"face": face_ps, "face_area": area_ps},
    }
    meta = {"codec": codec, "frame_hw": frame_hw, "n_samples": len(times),
            "n_expected": n_expected, "secs": round(time.time() - t0, 1),
            "samples": raw}
    return stem, rec, meta


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--vetting", default=DEFAULTS["vetting"])
    ap.add_argument("--clips", default=DEFAULTS["clips"])
    ap.add_argument("--model", default=DEFAULTS["model"])
    ap.add_argument("--out", default=DEFAULTS["out"])
    ap.add_argument("--raw-out", default=DEFAULTS["raw_out"])
    ap.add_argument("--workers", type=int, default=12)
    ap.add_argument("--score-thr", type=float, default=0.8,
                    help="0.8 chosen after a visual audit: ~4/15 detections "
                         "scored 0.70-0.80 were real faces")
    ap.add_argument("--min-area", type=float, default=0.001,
                    help="ignore boxes smaller than this fraction of the frame")
    ap.add_argument("--max-side", type=int, default=960,
                    help="downscale frames so the long side is <= this")
    ap.add_argument("--min-run-s", type=float, default=0.5)
    ap.add_argument("--limit", type=int, default=0, help="debug: first N clips")
    args = ap.parse_args()

    with open(args.vetting) as fh:
        vet = json.load(fh)
    stems = sorted(e["name"] for e in vet if e.get("include"))
    if args.limit:
        stems = stems[: args.limit]
    cfg = {"model": args.model, "clips": args.clips, "score_thr": args.score_thr,
           "min_area": args.min_area, "max_side": args.max_side,
           "min_run_s": args.min_run_s}

    workers = max(1, min(args.workers, 12, len(stems)))
    t0 = time.time()
    results, raw_all = {}, {}
    with Pool(workers, initializer=_init_worker, initargs=(cfg,)) as pool:
        for stem, rec, meta in pool.imap_unordered(process, stems):
            results[stem] = rec
            raw_all[stem] = meta
            print(f"[{len(results)}/{len(stems)}] {meta['n_samples']}/"
                  f"{meta['n_expected']} samples, {len(rec['events'])} events, "
                  f"{meta['secs']}s", flush=True)

    results = dict(sorted(results.items()))
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w") as fh:
        json.dump(results, fh)
    os.makedirs(os.path.dirname(args.raw_out), exist_ok=True)
    with open(args.raw_out, "w") as fh:
        json.dump({"config": cfg, "clips": dict(sorted(raw_all.items()))}, fh)

    n_short = sum(1 for m in raw_all.values()
                  if m["n_samples"] < m["n_expected"] - 1)
    print(f"done: {len(results)} clips in {time.time() - t0:.1f}s; "
          f"{n_short} clips decoded >1 sample fewer than expected", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
