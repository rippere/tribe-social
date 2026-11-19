"""Render a visual spot-check sheet for the faces extractor.

Picks --n-clips clips at random (fixed seed) from the raw sample file written
by extract_faces.py, and --per-clip sample times per clip uniformly at random.
For each pick it re-decodes the frame at the same 4 fps grid / scale, draws the
detector's boxes (green, with score) and writes one montage per clip plus a
manifest (pick index -> clip, t, detected?) to --out-dir. A human then labels
each tile "face visible?" and "boxes on real faces?" for precision/recall.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import subprocess

import cv2
import numpy as np


def grab_frame(path: str, t: float, hw: tuple[int, int]) -> np.ndarray:
    h, w = hw
    # Same fps=4 grid as the extractor; select the k-th output frame.
    k = int(round(t * 4))
    cmd = ["ffmpeg", "-v", "error", "-nostdin", "-i", path, "-an",
           "-vf", f"fps=4:round=near,scale={w}:{h}:flags=area,select=eq(n\\,{k})",
           "-frames:v", "1", "-pix_fmt", "bgr24", "-f", "rawvideo", "pipe:1"]
    buf = subprocess.run(cmd, capture_output=True, check=True).stdout
    return np.frombuffer(buf[: w * h * 3], np.uint8).reshape(h, w, 3).copy()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default="/tribe/insight/raw/faces_samples.json")
    ap.add_argument("--clips", default="/tribe/ugc")
    ap.add_argument("--out-dir", default="/tribe/insight/spotcheck/faces")
    ap.add_argument("--n-clips", type=int, default=6)
    ap.add_argument("--per-clip", type=int, default=5)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--tile", type=int, default=420)
    args = ap.parse_args()

    raw = json.load(open(args.raw))["clips"]
    rng = random.Random(args.seed)
    stems = rng.sample(sorted(raw), args.n_clips)
    os.makedirs(args.out_dir, exist_ok=True)
    manifest = []
    for ci, stem in enumerate(stems):
        meta = raw[stem]
        picks = sorted(rng.sample(meta["samples"], args.per_clip), key=lambda s: s["t"])
        tiles = []
        for pi, s in enumerate(picks):
            frame = grab_frame(os.path.join(args.clips, stem + ".mp4"), s["t"],
                               tuple(meta["frame_hw"]))
            for d in s["dets"]:
                x, y, w, h = (int(round(v)) for v in d["box"])
                cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
                cv2.putText(frame, f"{d['score']:.2f}", (x, max(12, y - 4)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
            fh, fw = frame.shape[:2]
            sc = args.tile / max(fh, fw)
            frame = cv2.resize(frame, (int(fw * sc), int(fh * sc)))
            tile = np.zeros((args.tile, args.tile, 3), np.uint8)
            oy, ox = (args.tile - frame.shape[0]) // 2, (args.tile - frame.shape[1]) // 2
            tile[oy:oy + frame.shape[0], ox:ox + frame.shape[1]] = frame
            label = f"C{ci}-{pi} det={len(s['dets'])}"
            cv2.putText(tile, label, (6, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.65,
                        (0, 0, 255), 2)
            tiles.append(tile)
            manifest.append({"id": f"C{ci}-{pi}", "clip": stem, "t": s["t"],
                             "n_dets": len(s["dets"]),
                             "scores": [d["score"] for d in s["dets"]]})
        cv2.imwrite(os.path.join(args.out_dir, f"sheet_C{ci}.jpg"),
                    np.hstack(tiles), [cv2.IMWRITE_JPEG_QUALITY, 85])
    json.dump(manifest, open(os.path.join(args.out_dir, "manifest.json"), "w"), indent=1)
    print(f"wrote {len(manifest)} picks across {len(stems)} clips to {args.out_dir}")


if __name__ == "__main__":
    main()
