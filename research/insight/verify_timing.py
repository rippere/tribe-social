"""Timing check for the visual event families, using the blind-sample key from
verify_detectors.py.

For every sampled event (cuts, faces, text) and every sampled non-event, decode
all native frames in [t - 1, t + 1] and measure:
  * the largest HSV content jump (frame-to-frame) and its time relative to t;
  * for face rows: YuNet presence on every native frame (same model, score 0.8,
    min area 0.001, long side 960 as in extract_faces.py) and the time of the
    presence flip nearest t.

Output: <key dir>/timing.json (per row, no clip ids beyond the key's own rows)
and an aggregate summary on stdout.

Run inside the `tribe` container:
    python verify_timing.py --key /tribe/insight/verify/key.json
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from multiprocessing import Pool
from pathlib import Path

import cv2
import numpy as np

UGC = Path("/tribe/ugc")
MODEL = "/tribe/insight/models/face_detection_yunet_2023mar.onnx"
PTS_RE = re.compile(r"pts_time:\s*([-0-9.]+)")
HALF = 1.0


def decode(stem, t0, dur, long_side):
    p = str(UGC / f"{stem}.mp4")
    o = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                        "stream=width,height", "-of", "csv=p=0", p],
                       capture_output=True, text=True).stdout.strip().split(",")
    w, h = int(o[0]), int(o[1])
    s = min(1.0, long_side / max(w, h))
    sw, sh = max(2, int(round(w * s / 2)) * 2), max(2, int(round(h * s / 2)) * 2)
    cmd = ["ffmpeg", "-hide_banner", "-nostats", "-copyts", "-ss", f"{max(t0, 0):.3f}",
           "-t", f"{dur:.3f}", "-i", p, "-an", "-fps_mode", "passthrough",
           "-vf", f"scale={sw}:{sh}:flags=area,showinfo", "-f", "rawvideo",
           "-pix_fmt", "bgr24", "-"]
    r = subprocess.run(cmd, capture_output=True)
    n = len(r.stdout) // (sw * sh * 3)
    fr = np.frombuffer(r.stdout[: n * sw * sh * 3], np.uint8).reshape(n, sh, sw, 3)
    pts = [float(m.group(1)) for m in PTS_RE.finditer(r.stderr.decode("utf-8", "replace"))]
    pts = np.asarray(pts[:n])
    return fr, pts


def content_jump(fr, pts, t):
    small = [cv2.cvtColor(cv2.resize(f, (128, 128), interpolation=cv2.INTER_AREA),
                          cv2.COLOR_BGR2HSV).astype(np.int16) for f in fr]
    d = []
    for i in range(1, len(small)):
        x = np.abs(small[i] - small[i - 1])
        dh = np.minimum(x[..., 0], 180 - x[..., 0])
        d.append((dh.mean() + x[..., 1].mean() + x[..., 2].mean()) / 3)
    if not d:
        return None, None, None
    d = np.asarray(d)
    i = int(np.argmax(d))
    med = float(np.median(d))
    return float(pts[i + 1] - t), float(d[i]), float(d[i] / max(med, 1.0))


def face_flip(fr, pts, t, kind):
    det = cv2.FaceDetectorYN.create(MODEL, "", (320, 320), score_threshold=0.8,
                                    nms_threshold=0.3, top_k=50)
    pres = []
    for f in fr:
        h, w = f.shape[:2]
        det.setInputSize((w, h))
        _, faces = det.detect(f)
        ok = False
        if faces is not None:
            for q in faces:
                x, y, bw, bh = (float(v) for v in q[:4])
                x0, y0, x1, y1 = max(0, x), max(0, y), min(w, x + bw), min(h, y + bh)
                if x1 > x0 and y1 > y0 and (x1 - x0) * (y1 - y0) / (w * h) >= 0.001:
                    ok = True
                    break
        pres.append(ok)
    pres = np.asarray(pres)
    flips = []
    for i in range(1, len(pres)):
        if pres[i] != pres[i - 1]:
            flips.append((float(pts[i] - t), "appear" if pres[i] else "disappear"))
    want = {"face_appear": "appear", "face_disappear": "disappear"}.get(kind)
    cand = [f for f in flips if want is None or f[1] == want]
    near = min(cand, key=lambda f: abs(f[0]), default=None)
    return {"n_flips": len(flips), "nearest": near,
            "frac_present_before": float(pres[pts < t].mean()) if (pts < t).any() else None,
            "frac_present_after": float(pres[pts >= t].mean()) if (pts >= t).any() else None}


def work(args):
    fam, r = args
    long_side = 960 if fam == "faces" else 320
    fr, pts = decode(r["stem"], r["t"] - HALF, 2 * HALF, long_side)
    out = {"row": r["row"], "kind": r["kind"], "n_frames": int(len(fr))}
    if len(fr) < 3:
        return fam, out
    dt, jump, ratio = content_jump(fr, pts, r["t"])
    out.update({"jump_dt": dt, "jump": jump, "jump_ratio": ratio})
    if fam == "faces":
        out["face"] = face_flip(fr, pts, r["t"], r["kind"])
    return fam, out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--key", default="/tribe/insight/verify/key.json")
    a = ap.parse_args()
    key = json.loads(Path(a.key).read_text())
    jobs = [(fam, r) for fam in ("cuts", "faces", "text") for r in key[fam]]
    with Pool(12) as pool:
        res = pool.map(work, jobs)
    out = {}
    for fam, o in res:
        out.setdefault(fam, []).append(o)
    Path(a.key).with_name("timing.json").write_text(json.dumps(out, indent=1))
    for fam, rows in out.items():
        for kind in sorted({r["kind"] for r in rows}):
            rr = [r for r in rows if r["kind"] == kind and r.get("jump_dt") is not None]
            dts = np.array([r["jump_dt"] for r in rr])
            rat = np.array([r["jump_ratio"] for r in rr])
            line = (f"{fam:6s} {kind:15s} n={len(rr):2d} jump_dt median={np.median(dts):+.3f} "
                    f"|dt|<=0.5: {(np.abs(dts) <= 0.5).sum()}/{len(rr)}  "
                    f"jump/median>=5: {(rat >= 5).sum()}/{len(rr)}")
            if fam == "faces":
                fl = [r["face"]["nearest"] for r in rr if r.get("face")]
                fd = np.array([f[0] for f in fl if f is not None])
                line += (f"  face_flip found {len(fd)}/{len(rr)}, |dt|<=0.5: "
                         f"{(np.abs(fd) <= 0.5).sum()}, median dt={np.median(fd) if len(fd) else float('nan'):+.3f}")
            print(line)


if __name__ == "__main__":
    main()
