"""Key the green-screen mascot clips to alpha WebM and track the character.

For each Kling clip in <src>/<name>.mp4 this writes:
  <out>/<name>.webm   VP9 with alpha (yuva420p), same size and frame rate
  --track (json)      per-frame bounding box of the character, normalised to the
                      clip (0..1), so the composition can hang a speech bubble on
                      its head and know where it stands.

The key is a green-dominance matte (g - max(r, b)) with a soft ramp and a
despill clamp, the same one used to build the anchor frames, so the clips and
anchors match edge for edge.

    uv run --no-project --with numpy python scripts/key_mascot.py \
        --src $EXPLAINER_MEDIA/v2/clips --out public/media/mascot --track src/data/mascot_track.json
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

import numpy as np

LO, HI = 25.0, 85.0  # green dominance: below LO opaque, above HI clear


def probe(path: Path) -> tuple[int, int, str]:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height,r_frame_rate", "-of", "json", str(path)],
        check=True, capture_output=True, text=True,
    ).stdout
    s = json.loads(out)["streams"][0]
    return s["width"], s["height"], s["r_frame_rate"]


def key_frame(rgb: np.ndarray) -> np.ndarray:
    a = rgb.astype(np.float32)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    rb = np.maximum(r, b)
    alpha = np.clip(1 - (g - rb - LO) / (HI - LO), 0, 1)
    g = np.where(alpha < 1, np.minimum(g, rb + 8), g)  # despill the fringe only
    return np.dstack([r, g, b, alpha * 255]).clip(0, 255).astype(np.uint8)


def bbox(alpha: np.ndarray, w: int, h: int) -> dict | None:
    ys, xs = np.nonzero(alpha > 128)
    if len(xs) < 50:
        return None
    return {
        "l": round(float(xs.min()) / w, 4), "r": round(float(xs.max()) / w, 4),
        "t": round(float(ys.min()) / h, 4), "b": round(float(ys.max()) / h, 4),
        "cx": round(float(np.median(xs)) / w, 4),
    }


def process(src: Path, dst: Path) -> tuple[float, list]:
    w, h, rate = probe(src)
    dec = subprocess.Popen(
        ["ffmpeg", "-v", "error", "-i", str(src), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
        stdout=subprocess.PIPE,
    )
    enc = subprocess.Popen(
        ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{w}x{h}", "-r", rate,
         "-i", "-", "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p", "-b:v", "0", "-crf", "24",
         "-row-mt", "1", "-deadline", "good", "-cpu-used", "4", "-auto-alt-ref", "0", str(dst)],
        stdin=subprocess.PIPE,
    )
    track = []
    size = w * h * 3
    assert dec.stdout and enc.stdin
    while True:
        buf = dec.stdout.read(size)
        if len(buf) < size:
            break
        rgba = key_frame(np.frombuffer(buf, np.uint8).reshape(h, w, 3))
        track.append(bbox(rgba[..., 3], w, h))
        enc.stdin.write(rgba.tobytes())
    enc.stdin.close()
    enc.wait()
    dec.wait()
    num, den = (int(x) for x in rate.split("/"))
    return num / den, track


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--src", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--track", type=Path, required=True, help="where to write the per-frame track json")
    p.add_argument("--only", nargs="*", help="clip names to (re)process; default all")
    a = p.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    track_path = a.track
    tracks = json.loads(track_path.read_text()) if track_path.exists() else {}
    for clip in sorted(a.src.glob("*.mp4")):
        if a.only and clip.stem not in a.only:
            continue
        fps, track = process(clip, a.out / f"{clip.stem}.webm")
        tracks[clip.stem] = {"fps": fps, "frames": track}
        print(f"{clip.stem}: {len(track)} frames @ {fps:g} fps")
    track_path.write_text(json.dumps(tracks, separators=(",", ":")))


if __name__ == "__main__":
    main()
