"""Stage 4 (prescribe): single-variable ffmpeg edits + re-encode controls for TRIBE rescoring.

No effect survived adversarial verification. Per the brief, we test the strongest q < 0.25
effect (text_change -> social, +0.46 SD, CI 0.35-0.58, q = 0.14, model-internal) plus
"trim cold open". Each edit changes exactly one thing. Each source clip also gets one
CONTROL: the same ffmpeg pipeline with no change, so (control vs original preds) measures
re-encode noise and (edit vs control) measures the edit.

Edit types
  caption  Burn in a caption track (drawtext) over a stretch with no detected on-screen text.
           Chunks of <= 3 words change at word onsets, so the edit inserts 1 text_appear plus
           several text_change events. caption_source = "transcript" (the words spoken in
           that window, from the clip's existing WhisperX TSV) or "fixed" (a neutral fixed
           phrase sequence, used only when the window has no speech).
           Audio stream is copied, so only pixels in the window change.
  trim3    Remove the first 3.0 s (cold open). Audio is copied and cut at the same point.

Shared pipeline (edit and control identical apart from the edit itself)
  video: libx264, preset medium, crf 16, yuv420p, threads 4, source frame rate kept
  audio: stream copy (bit-identical samples)
  transcript: the scorer reads <video>.tsv if it exists, so each output gets a seeded TSV:
  a copy of the source TSV (control, caption), or the source TSV with words before 3 s
  dropped and times shifted by -3 s (trim3). The language stream stays fixed, and WhisperX
  cannot add noise.

Clip selection (deterministic, decided before any edit was scored)
  include == true, has preds, 15 <= duration <= 34 s (34 rather than 30 s, so that 8
  transcript-caption clips qualify).
  Caption window: the longest run (>= 3 whole seconds) of seconds with per_second text == 0,
  inside video seconds [4, floor(d) - 5), so that both the lag-0 and lag-4 response windows
  fit inside the prediction. Window length L = min(run, 5) s, starting at the run start.
  Ties go to more words.
  transcript arm: >= 3 words start inside the window. fixed arm: 0 words in the window
  (1-2 words is excluded as ambiguous). Take all transcript-eligible clips, then fill
  to 12 with fixed-eligible clips, shortest first. trim3 uses the same 12 clips, so
  each clip has one shared control.

Pre-registered analysis (run after rescoring; see manifest["analysis_plan"])
  Signals: norms.timecourses(preds, _BATCH_MASKS). z-scored with the CONTROL's mean/SD
  over predicted seconds >= 4, and the same parameters are applied to the edit.
  caption, primary: social, D = mean(edit - ctrl) over pred seconds [a, a+L+4)
    minus mean(edit - ctrl) over pred seconds [max(4, a-3), a), averaged across the 12
    clips. Bootstrap CI over clips, exact sign-flip p. Lag-specific windows are secondary:
    [a, a+L) for lag 0 and [a+4, a+L+4) for lag 4. The other 7 signals are secondary
    (BH across them).
  Noise floor: the same metric for ctrl vs original preds, at the same window.
  trim3: aligned content, edit pred t vs ctrl pred t+3 for edit t >= 4: per-signal mean
    |delta z| (context dependence), plus the hook-window metric (scorer HOOK_WINDOW) on
    edit vs ctrl.
  All model-internal (what TRIBE predicts), not viewer behaviour.

Usage (inside the tribe container, CPU only):
  python make_edits.py --out /tribe/edits [--jobs 3] [--dry-run]
Writes <out>/<id>.mp4, <out>/<id>.tsv, <out>/manifest.json. Edit ids carry no clip stems.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

VETTING = Path("/tribe/work/vetting.json")
UGC = Path("/tribe/ugc")
PREDS = Path("/tribe/ugc_preds")
EVENTS = Path("/tribe/insight/events")
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

D_MIN, D_MAX = 15.0, 34.0
LO_S, TAIL_S = 4, 5          # caption window in [4, floor(d) - 5)
MIN_RUN, MAX_L = 3, 5
N_CAPTION = 12
TRIM_S = 3.0
WORDS_PER_CHUNK = 3
FIXED_CHUNKS = ["so here's", "the thing", "you need", "to know", "right now"]
X264 = ["-c:v", "libx264", "-preset", "medium", "-crf", "16", "-pix_fmt", "yuv420p",
        "-threads", "4"]


def stem_of(name: str) -> str:
    return name[:-4] if name.endswith(".mp4") else name


def probe(path: Path) -> dict:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
         "stream=width,height,r_frame_rate:format=duration", "-of", "json", str(path)],
        check=True, capture_output=True, text=True).stdout
    j = json.loads(out)
    s = j["streams"][0]
    return {"w": int(s["width"]), "h": int(s["height"]), "fps": s["r_frame_rate"],
            "duration": float(j["format"]["duration"])}


def read_tsv(path: Path) -> list[dict]:
    with path.open() as f:
        return list(csv.DictReader(f, delimiter="\t"))


def caption_window(text_ps: list, words: list[dict], d: float):
    tx = np.array([np.nan if x is None else x for x in text_ps], float)
    hi = int(math.floor(d)) - TAIL_S
    starts = [float(w["start"]) for w in words]
    best = None
    s = LO_S
    while s < hi:
        if tx[s] == 0:
            b = s
            while b + 1 < hi and tx[b + 1] == 0:
                b += 1
            run = b - s + 1
            if run >= MIN_RUN:
                L = min(run, MAX_L)
                nw = sum(1 for t in starts if s <= t < s + L)
                key = (L, nw)
                if best is None or key > best[0]:
                    best = (key, s, L, nw)
            s = b + 1
        else:
            s += 1
    if best is None:
        return None
    _, a, L, nw = best
    return {"a": a, "L": L, "n_words": nw}


def select() -> list[dict]:
    vet = [e for e in json.loads(VETTING.read_text()) if e.get("include")]
    text = json.loads((EVENTS / "text.json").read_text())
    trans, fixed = [], []
    for e in vet:
        st = stem_of(e["name"])
        if st not in text or not (PREDS / f"{st}_preds.npy").exists():
            continue
        d = text[st]["duration_s"]
        if not (D_MIN <= d <= D_MAX):
            continue
        words = read_tsv(UGC / f"{st}.tsv")
        win = caption_window(text[st]["per_second"]["text"], words, d)
        if win is None:
            continue
        row = {"stem": st, "duration_s": d, "category": e.get("true_category"),
               "arm": e.get("true_arm"), "format": e.get("format"), **win}
        if win["n_words"] >= 3:
            trans.append({**row, "caption_source": "transcript"})
        elif win["n_words"] == 0:
            fixed.append({**row, "caption_source": "fixed"})
    trans.sort(key=lambda r: r["duration_s"])
    fixed.sort(key=lambda r: r["duration_s"])
    return (trans + fixed)[:N_CAPTION]


def caption_chunks(row: dict, words: list[dict]) -> list[tuple[float, float, str]]:
    a, b = float(row["a"]), float(row["a"] + row["L"])
    if row["caption_source"] == "fixed":
        n = row["L"]
        return [(a + i, a + i + 1, FIXED_CHUNKS[i % len(FIXED_CHUNKS)]) for i in range(n)]
    ws = [(float(w["start"]), str(w["text"]).strip()) for w in words
          if a <= float(w["start"]) < b and str(w["text"]).strip()]
    groups = [ws[i:i + WORDS_PER_CHUNK] for i in range(0, len(ws), WORDS_PER_CHUNK)]
    out = []
    for gi, g in enumerate(groups):
        t0 = a if gi == 0 else g[0][0]
        t1 = groups[gi + 1][0][0] if gi + 1 < len(groups) else b
        out.append((t0, t1, " ".join(t for _, t in g)))
    return out


def drawtext_filter(chunks, tdir: Path, cid: str, w: int, h: int) -> str:
    fs = round(min(w, h) * 0.07)
    bw = max(2, fs // 10)
    parts = []
    for k, (t0, t1, txt) in enumerate(chunks):
        tf = tdir / f"{cid}_{k}.txt"
        tf.write_text(txt)
        parts.append(
            f"drawtext=fontfile={FONT}:textfile={tf}:expansion=none:fontsize={fs}:"
            f"fontcolor=white:borderw={bw}:bordercolor=black:x=(w-text_w)/2:y=h*0.70:"
            f"enable='between(t,{t0:.3f},{t1 - 0.001:.3f})'")
    return ",".join(parts)


def ffmpeg(src: Path, dst: Path, vf: str | None = None, ss: float | None = None):
    cmd = ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y", "-i", str(src)]
    if ss is not None:
        cmd += ["-ss", f"{ss:.3f}"]
    cmd += ["-map", "0:v:0", "-map", "0:a:0?"]
    if vf:
        cmd += ["-vf", vf]
    cmd += X264 + ["-c:a", "copy", "-map_metadata", "-1", "-movflags", "+faststart", str(dst)]
    subprocess.run(cmd, check=True)


def seed_tsv(src_tsv: Path, dst_tsv: Path, shift: float = 0.0):
    rows = read_tsv(src_tsv)
    if not rows:
        shutil.copyfile(src_tsv, dst_tsv)
        return
    keep = []
    for r in rows:
        t = float(r["start"]) - shift
        if t < 0:
            continue
        r = dict(r)
        if shift:
            r["start"] = repr(t)
        keep.append(r)
    with dst_tsv.open("w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=list(rows[0].keys()), delimiter="\t")
        wr.writeheader()
        wr.writerows(keep)


def per_second_diff(a: Path, b: Path, offset_s: float = 0.0) -> list[float]:
    """Mean |pixel diff| per second (grey, 160 px wide) between a and b (b read from offset_s)."""
    import cv2
    ca, cb = cv2.VideoCapture(str(a)), cv2.VideoCapture(str(b))
    fps = ca.get(cv2.CAP_PROP_FPS) or 30.0
    if offset_s:
        cb.set(cv2.CAP_PROP_POS_MSEC, offset_s * 1000.0)
    sums: dict[int, list[float]] = {}
    i = 0
    while True:
        ok1, f1 = ca.read()
        ok2, f2 = cb.read()
        if not (ok1 and ok2):
            break
        g1 = cv2.cvtColor(cv2.resize(f1, (160, int(160 * f1.shape[0] / f1.shape[1]))),
                          cv2.COLOR_BGR2GRAY).astype(np.float32)
        g2 = cv2.cvtColor(cv2.resize(f2, (g1.shape[1], g1.shape[0])),
                          cv2.COLOR_BGR2GRAY).astype(np.float32)
        sums.setdefault(int(i / fps), []).append(float(np.abs(g1 - g2).mean()))
        i += 1
    return [round(float(np.mean(sums[k])), 3) for k in sorted(sums)]


def build(row: dict, k: int, out: Path, tdir: Path) -> list[dict]:
    st = row["stem"]
    src, src_tsv = UGC / f"{st}.mp4", UGC / f"{st}.tsv"
    p = probe(src)
    ctrl, cap, trim = f"ctrl_{k:02d}", f"cap_{k:02d}", f"trim3_{k:02d}"
    words = read_tsv(src_tsv)
    chunks = caption_chunks(row, words)

    ffmpeg(src, out / f"{ctrl}.mp4")
    seed_tsv(src_tsv, out / f"{ctrl}.tsv")
    ffmpeg(src, out / f"{cap}.mp4", vf=drawtext_filter(chunks, tdir, cap, p["w"], p["h"]))
    seed_tsv(src_tsv, out / f"{cap}.tsv")
    ffmpeg(src, out / f"{trim}.mp4", ss=TRIM_S)
    seed_tsv(src_tsv, out / f"{trim}.tsv", shift=TRIM_S)

    cap_diff = per_second_diff(out / f"{cap}.mp4", out / f"{ctrl}.mp4")
    trim_diff = per_second_diff(out / f"{trim}.mp4", out / f"{ctrl}.mp4", offset_s=TRIM_S)
    common = {"source_stem": st, "control_id": ctrl, "source_duration_s": p["duration"],
              "source_wh": [p["w"], p["h"]], "fps": p["fps"], "category": row["category"],
              "true_arm": row["arm"], "format": row["format"]}
    return [
        {"id": ctrl, "edit_type": "control", "params": {"pipeline": "x264 crf16 + audio copy"},
         **common, "duration_s": probe(out / f"{ctrl}.mp4")["duration"]},
        {"id": cap, "edit_type": "caption",
         "params": {"window_video_s": [row["a"], row["a"] + row["L"]],
                    "caption_source": row["caption_source"], "n_words_in_window": row["n_words"],
                    "n_chunks": len(chunks), "n_text_change": max(0, len(chunks) - 1),
                    "chunk_times": [[round(a, 3), round(b, 3)] for a, b, _ in chunks],
                    "font": Path(FONT).name, "y_frac": 0.70},
         **common, "duration_s": probe(out / f"{cap}.mp4")["duration"],
         "check_px_diff_vs_ctrl_per_s": cap_diff},
        {"id": trim, "edit_type": "trim_cold_open", "params": {"trim_s": TRIM_S},
         **common, "duration_s": probe(out / f"{trim}.mp4")["duration"],
         "check_px_diff_vs_ctrl_shifted_per_s": trim_diff},
    ]


ANALYSIS_PLAN = {
    "signals": "norms.timecourses(preds, run_and_save._BATCH_MASKS)",
    "z": "z-score both edit and control with CONTROL mean/SD over pred s >= 4",
    "caption_primary": "social: mean(edit-ctrl) over pred s [a, a+L+4) minus mean(edit-ctrl) "
                       "over pred s [max(4,a-3), a); mean over 12 clips; bootstrap CI over "
                       "clips; exact sign-flip p",
    "caption_secondary": "lag-0 window [a,a+L), lag-4 window [a+4,a+L+4); other 7 signals, "
                         "BH within secondary; transcript vs fixed caption_source split "
                         "(descriptive only)",
    "noise_floor": "same metric for ctrl vs original /tribe/ugc_preds at the same windows",
    "trim_primary": "edit pred t vs ctrl pred t+3 for edit t >= 4: per-signal mean |dz|, "
                    "and scorer hook-window metric edit vs ctrl",
    "scope": "model-internal TRIBE predictions, not viewer behaviour; n=12 clips per edit",
    "basis": "text_change->social effect_sd 0.46 [0.35,0.58], q_fdr 0.14 (not verified); "
             "verifier notes: lag may be ~0 not 4, so windows span both",
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="/tribe/edits")
    ap.add_argument("--jobs", type=int, default=3)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    rows = select()
    for k, r in enumerate(rows, 1):
        print(k, r["caption_source"], f"d={r['duration_s']:.1f}",
              f"win=[{r['a']},{r['a'] + r['L']})", f"words={r['n_words']}")
    if args.dry_run:
        return
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    tdir = out / "_captions"
    tdir.mkdir(exist_ok=True)
    with ThreadPoolExecutor(args.jobs) as ex:
        results = list(ex.map(lambda kr: build(kr[1], kr[0], out, tdir),
                              enumerate(rows, 1)))
    entries = {e["id"]: e for res in results for e in res}
    total_s = sum(e["duration_s"] for e in entries.values())
    manifest = {"design": __doc__.split("Usage")[0].strip(), "analysis_plan": ANALYSIS_PLAN,
                "n_sources": len(rows), "n_edits": sum(e["edit_type"] != "control"
                                                      for e in entries.values()),
                "n_files": len(entries), "total_video_s": round(total_s, 1),
                "est_scoring_hours_at_12s_per_s": round(total_s * 12 / 3600, 2),
                "edits": entries}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1))
    print(f"wrote {len(entries)} files, {total_s:.0f} s of video, "
          f"est {manifest['est_scoring_hours_at_12s_per_s']} h")


if __name__ == "__main__":
    main()
