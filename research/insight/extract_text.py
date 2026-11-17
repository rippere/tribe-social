"""On-screen text event extractor (captions, overlays) for the insight study.

Samples every clip at 2 fps with ffmpeg, runs RapidOCR (PP-OCRv4 det + rec,
onnxruntime, CPU) on each sample, and writes the shared event format:

    {"<stem>": {"duration_s": float,
                "events": [{"type": "text_appear" | "text_change", "t": float}],
                "per_second": {"text": [...], "text_area": [...]}}}

Definitions (all times are video seconds, not BOLD-lagged):
  * a sample "has text" when at least one OCR line survives the filters
    (recognition score >= MIN_SCORE, >= MIN_CHARS alphanumeric chars,
    box height >= MIN_H_FRAC of frame height).
  * text_appear: a sample with text whose preceding absent run is
    >= APPEAR_GAP_S (0.5 s = one sample at 2 fps). The first sample of a clip
    counts as an appear if it has text (text present from frame 0).
  * text_change: two consecutive text-bearing samples whose normalised text
    similarity (difflib ratio) < CHANGE_SIM, or whose text-box masks overlap
    with IoU < CHANGE_IOU.
  * per_second["text"][k]: fraction of samples in [k, k+1) with text.
  * per_second["text_area"][k]: mean fraction of frame area covered by the
    union of surviving text boxes over samples in [k, k+1).
  Length of per_second arrays = ceil(duration_s), matching prediction length.

Raw OCR per sample is cached under <out_root>/text_raw/<stem>.json so the
event thresholds can be re-derived (--rederive) without re-running OCR.

Run inside the `tribe` container:
    python extract_text.py --workers 12
"""
from __future__ import annotations

import argparse
import difflib
import json
import math
import os
import re
import subprocess
import sys
import time
from multiprocessing import Pool
from pathlib import Path

os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")

import numpy as np  # noqa: E402

FPS = 2.0
MIN_SCORE = 0.6
MIN_CHARS = 2
MIN_H_FRAC = 0.012
APPEAR_GAP_S = 0.5
CHANGE_SIM = 0.5
CHANGE_IOU = 0.3
MASK_W = 64  # coarse mask for area / IoU

UGC_DIR = Path("/tribe/ugc")
VETTING = Path("/tribe/work/vetting.json")
OUT_ROOT = Path("/tribe/insight")

_ENGINE = None


def _engine():
    global _ENGINE
    if _ENGINE is None:
        import cv2
        import yaml
        from rapidocr_onnxruntime import RapidOCR
        import rapidocr_onnxruntime as ro

        cv2.setNumThreads(1)
        cfg = yaml.safe_load(open(Path(ro.__file__).parent / "config.yaml"))
        for sec in ("Global", "Det", "Cls", "Rec"):
            cfg[sec]["intra_op_num_threads"] = 1
            cfg[sec]["inter_op_num_threads"] = 1
        cfg_path = Path(f"/tmp/rapidocr_1thread_{os.getpid()}.yaml")
        # model paths in the default config are relative to the package root
        for sec in ("Det", "Cls", "Rec"):
            cfg[sec]["model_path"] = str(Path(ro.__file__).parent / cfg[sec]["model_path"])
        cfg_path.write_text(yaml.safe_dump(cfg))
        _ENGINE = RapidOCR(config_path=str(cfg_path))
    return _ENGINE


def probe(path: Path) -> tuple[float, int, int]:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
         "stream=width,height:format=duration", "-of", "json", str(path)],
        capture_output=True, text=True, check=True).stdout
    j = json.loads(out)
    st = j["streams"][0]
    return float(j["format"]["duration"]), int(st["width"]), int(st["height"])


def frames_2fps(path: Path, w: int, h: int):
    """Yield (t, bgr frame) at t = 0, 0.5, 1.0, ... using ffmpeg (handles AV1)."""
    # scale so the long side is at most 1280 (keeps OCR cost bounded)
    s = min(1.0, 1280.0 / max(w, h))
    ow, oh = int(round(w * s / 2) * 2), int(round(h * s / 2) * 2)
    cmd = ["ffmpeg", "-v", "error", "-threads", "1", "-i", str(path), "-vf",
           f"fps={FPS},scale={ow}:{oh}", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    n = ow * oh * 3
    i = 0
    while True:
        buf = proc.stdout.read(n)
        if len(buf) < n:
            break
        yield i / FPS, np.frombuffer(buf, np.uint8).reshape(oh, ow, 3)
        i += 1
    proc.wait()


def ocr_clip(stem: str) -> dict:
    path = UGC_DIR / f"{stem}.mp4"
    dur, w, h = probe(path)
    eng = _engine()
    samples = []
    fw = fh = None
    for t, fr in frames_2fps(path, w, h):
        fh, fw = fr.shape[:2]
        res, _ = eng(fr)
        lines = []
        for box, txt, score in res or []:
            lines.append({"box": [[round(float(x), 1), round(float(y), 1)] for x, y in box],
                          "text": txt, "score": round(float(score), 4)})
        samples.append({"t": t, "lines": lines})
    return {"stem": stem, "duration_s": dur, "frame_w": fw, "frame_h": fh,
            "fps_sampled": FPS, "samples": samples}


def _keep(line: dict, fh: int) -> bool:
    if line["score"] < MIN_SCORE:
        return False
    if len(re.sub(r"[^0-9A-Za-z]", "", line["text"])) < MIN_CHARS:
        return False
    ys = [p[1] for p in line["box"]]
    return (max(ys) - min(ys)) >= MIN_H_FRAC * fh


def _mask(lines: list, fw: int, fh: int) -> np.ndarray:
    import cv2
    mh = max(1, int(round(MASK_W * fh / fw)))
    m = np.zeros((mh, MASK_W), np.uint8)
    for ln in lines:
        pts = np.array([[x * MASK_W / fw, y * mh / fh] for x, y in ln["box"]], np.float32)
        cv2.fillPoly(m, [np.round(pts).astype(np.int32)], 1)
    return m.astype(bool)


def _norm_text(lines: list) -> str:
    srt = sorted(lines, key=lambda l: (round(min(p[1] for p in l["box"]) / 20), min(p[0] for p in l["box"])))
    s = " ".join(l["text"] for l in srt).lower()
    return re.sub(r"[^0-9a-z ]+", "", s).strip()


def derive(raw: dict) -> dict:
    fw, fh, dur = raw["frame_w"], raw["frame_h"], raw["duration_s"]
    n_sec = int(math.ceil(dur - 1e-6))
    per = []
    for s in raw["samples"]:
        kept = [l for l in s["lines"] if _keep(l, fh)]
        m = _mask(kept, fw, fh) if kept else None
        per.append({"t": s["t"], "has": bool(kept),
                    "area": float(m.mean()) if m is not None else 0.0,
                    "mask": m, "text": _norm_text(kept) if kept else ""})

    events = []
    absent_run = math.inf  # nothing before the clip starts
    prev = None
    for p in per:
        if p["has"]:
            if absent_run >= APPEAR_GAP_S - 1e-6:
                events.append({"type": "text_appear", "t": p["t"]})
            elif prev is not None and prev["has"]:
                sim = difflib.SequenceMatcher(None, prev["text"], p["text"]).ratio()
                inter = np.logical_and(prev["mask"], p["mask"]).sum()
                uni = np.logical_or(prev["mask"], p["mask"]).sum()
                iou = inter / uni if uni else 1.0
                if sim < CHANGE_SIM or iou < CHANGE_IOU:
                    events.append({"type": "text_change", "t": p["t"]})
            absent_run = 0.0
        else:
            absent_run += 1.0 / FPS  # inf (no text yet in clip) stays inf
        prev = p

    text = [0.0] * n_sec
    area = [0.0] * n_sec
    cnt = [0] * n_sec
    for p in per:
        k = int(math.floor(p["t"] + 1e-9))
        if 0 <= k < n_sec:
            text[k] += float(p["has"])
            area[k] += p["area"]
            cnt[k] += 1
    text = [round(text[k] / cnt[k], 4) if cnt[k] else None for k in range(n_sec)]
    area = [round(area[k] / cnt[k], 5) if cnt[k] else None for k in range(n_sec)]
    return {"duration_s": round(dur, 3), "events": events,
            "per_second": {"text": text, "text_area": area}}


def _work(stem: str):
    raw_dir = OUT_ROOT / "text_raw"
    out = raw_dir / f"{stem}.json"
    if out.exists():
        return stem, "cached", 0.0
    t0 = time.time()
    try:
        raw = ocr_clip(stem)
    except Exception as e:  # keep going; report at the end
        return stem, f"error: {e!r}", time.time() - t0
    tmp = out.with_suffix(".tmp")
    tmp.write_text(json.dumps(raw))
    tmp.rename(out)
    return stem, "ok", time.time() - t0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=12)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--rederive", action="store_true", help="skip OCR, rebuild events from cache")
    a = ap.parse_args()
    assert a.workers <= 12

    stems = [x["name"] for x in json.load(open(VETTING)) if x.get("include")]
    if a.limit:
        stems = stems[: a.limit]
    (OUT_ROOT / "text_raw").mkdir(parents=True, exist_ok=True)
    (OUT_ROOT / "events").mkdir(parents=True, exist_ok=True)

    if not a.rederive:
        t0 = time.time()
        with Pool(a.workers, maxtasksperchild=4) as pool:
            for i, (stem, status, dt) in enumerate(pool.imap_unordered(_work, stems), 1):
                print(f"[{i}/{len(stems)}] {status} {dt:.0f}s (elapsed {time.time()-t0:.0f}s)", flush=True)

    out, missing = {}, []
    for stem in stems:
        f = OUT_ROOT / "text_raw" / f"{stem}.json"
        if not f.exists():
            missing.append(stem)
            continue
        out[stem] = derive(json.loads(f.read_text()))
    dst = OUT_ROOT / "events" / "text.json"
    tmp = dst.with_suffix(".tmp")
    tmp.write_text(json.dumps(out))
    tmp.rename(dst)
    n_ev = {}
    for v in out.values():
        for e in v["events"]:
            n_ev[e["type"]] = n_ev.get(e["type"], 0) + 1
    print(json.dumps({"n_clips": len(out), "missing": len(missing), "n_events": n_ev}))
    if missing:
        sys.exit(1)


if __name__ == "__main__":
    main()
