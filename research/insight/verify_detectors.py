"""Blind detector-validity spot check for the insight event families.

For each event type, samples kept events (same keep rule as event_effects.py:
floor(t) >= 3 and floor(t) + 7 < n_predicted_seconds), at most 2 per clip, plus
random non-event times (no event of any type in the same family within
+-NONEVENT_GAP s, same valid range). Events and non-events are shuffled together
and rendered as anonymous rows (R00, R01, ...) so the reviewer judges blind:

  visual families (cuts, faces, text): one row of frames at fixed offsets from t
  speech: a 0-4 kHz spectrogram of t-2 .. t+2 s with the speech-band RMS level,
          a line at t and dotted lines at t +- 0.5 s.

The answer key (row -> stem, type, t) and the sheets go to --out-dir on the Spark
(per-clip data never leaves the Spark/scratch). No clip identifiers are in this
file.

Run inside the `tribe` container:
    python verify_detectors.py --out-dir /tribe/insight/verify
"""
from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
from multiprocessing import Pool
from pathlib import Path

import cv2
import numpy as np

UGC = Path("/tribe/ugc")
VET = Path("/tribe/work/vetting.json")
EVD = Path("/tribe/insight/events")
SEED = 4242
N_EV = 20
N_NON = 24
MAX_PER_CLIP = 2
NONEVENT_GAP = 1.5

FAMILIES = {
    "cuts": ["cut"],
    "faces": ["face_appear", "face_disappear"],
    "text": ["text_appear", "text_change"],
    "speech": ["speech_onset", "pause_start"],
}
OFFSETS = {
    "cuts": [-1.0, -0.5, -0.02, 0.02, 0.5, 1.0],
    "faces": [-1.0, -0.5, -0.25, 0.0, 0.5, 1.0],
    "text": [-1.0, -0.5, -0.25, 0.0, 0.5, 1.0],
}
CW, CH = 200, 356
ROWS_PER_SHEET = {"cuts": 5, "faces": 5, "text": 5, "speech": 8}


def stems_included():
    v = json.loads(VET.read_text())
    return sorted(x["name"][:-4] if x["name"].endswith(".mp4") else x["name"]
                  for x in v if x.get("include"))


def grab(args):
    stem, t = args
    t = max(t, 0.0)
    cmd = ["ffmpeg", "-v", "error", "-ss", f"{t:.3f}", "-i", str(UGC / f"{stem}.mp4"),
           "-frames:v", "1", "-vf", f"scale={CW}:{CH}:force_original_aspect_ratio=decrease,"
           f"pad={CW}:{CH}:(ow-iw)/2:(oh-ih)/2", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"]
    out = subprocess.run(cmd, capture_output=True).stdout
    if len(out) < CW * CH * 3:
        return np.full((CH, CW, 3), 60, np.uint8)
    return np.frombuffer(out[: CW * CH * 3], np.uint8).reshape(CH, CW, 3).copy()


def audio(stem, t0, dur):
    cmd = ["ffmpeg", "-v", "error", "-ss", f"{max(t0, 0):.3f}", "-t", f"{dur:.3f}",
           "-i", str(UGC / f"{stem}.wav"), "-ac", "1", "-ar", "16000", "-f", "s16le", "-"]
    out = subprocess.run(cmd, capture_output=True).stdout
    x = np.frombuffer(out, np.int16).astype(np.float32) / 32768.0
    pad_front = int(round(max(0.0, -t0) * 16000))
    return np.concatenate([np.zeros(pad_front, np.float32), x])


def sample(fam, stems, preds_n, events, rng):
    types = FAMILIES[fam]
    rows = []
    for et in types:
        cand = []
        for st in stems:
            n = preds_n[st]
            for e in events[st]:
                if e["type"] == et and math.floor(e["t"]) >= 3 and math.floor(e["t"]) + 7 < n:
                    cand.append((st, e["t"]))
        rng.shuffle(cand)
        per = {}
        for st, t in cand:
            if per.get(st, 0) >= MAX_PER_CLIP:
                continue
            per[st] = per.get(st, 0) + 1
            rows.append({"stem": st, "t": float(t), "kind": et})
            if sum(1 for r in rows if r["kind"] == et) >= N_EV:
                break
    k = 0
    tries = 0
    while k < N_NON and tries < 100000:
        tries += 1
        st = stems[rng.integers(len(stems))]
        n = preds_n[st]
        if n - 7 <= 3:
            continue
        t = float(rng.uniform(3.0, n - 7.0))
        ts = [e["t"] for e in events[st] if e["type"] in types]
        if any(abs(u - t) <= NONEVENT_GAP for u in ts):
            continue
        rows.append({"stem": st, "t": round(t, 3), "kind": "none"})
        k += 1
    order = rng.permutation(len(rows))
    rows = [rows[i] for i in order]
    for i, r in enumerate(rows):
        r["row"] = f"{fam[0].upper()}{i:02d}"
    return rows


def visual_sheets(fam, rows, out, pool):
    offs = OFFSETS[fam]
    jobs = [(r["stem"], r["t"] + o) for r in rows for o in offs]
    frames = pool.map(grab, jobs)
    per = ROWS_PER_SHEET[fam]
    paths = []
    head = np.full((28, 90 + CW * len(offs), 3), 255, np.uint8)
    for j, o in enumerate(offs):
        cv2.putText(head, f"{o:+.2f}s", (90 + j * CW + 60, 20), cv2.FONT_HERSHEY_SIMPLEX,
                    0.6, (0, 0, 0), 2)
    for s in range(0, len(rows), per):
        block = [head]
        for i, r in enumerate(rows[s:s + per]):
            fr = frames[(s + i) * len(offs):(s + i + 1) * len(offs)]
            lab = np.full((CH, 90, 3), 255, np.uint8)
            cv2.putText(lab, r["row"], (8, CH // 2), cv2.FONT_HERSHEY_SIMPLEX, 0.8,
                        (0, 0, 200), 2)
            cells = []
            for f in fr:
                f = f.copy()
                cv2.rectangle(f, (0, 0), (CW - 1, CH - 1), (255, 255, 255), 1)
                cells.append(f)
            block.append(np.hstack([lab] + cells))
            block.append(np.full((6, head.shape[1], 3), 255, np.uint8))
        img = np.vstack(block)
        p = out / f"{fam}_sheet{s // per:02d}.jpg"
        cv2.imwrite(str(p), img, [cv2.IMWRITE_JPEG_QUALITY, 85])
        paths.append(str(p))
    return paths


def speech_sheets(rows, out):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    per = ROWS_PER_SHEET["speech"]
    paths = []
    for s in range(0, len(rows), per):
        chunk = rows[s:s + per]
        fig, axs = plt.subplots(len(chunk), 1, figsize=(11, 1.9 * len(chunk)))
        axs = np.atleast_1d(axs)
        for ax, r in zip(axs, chunk):
            x = audio(r["stem"], r["t"] - 2.0, 4.0)
            if len(x) < 512:
                ax.set_title(r["row"] + " (no audio)")
                continue
            ax.specgram(x, NFFT=512, Fs=16000, noverlap=384, cmap="magma",
                        xextent=(-2.0, -2.0 + len(x) / 16000))
            ax.set_ylim(0, 4000)
            # speech-band RMS (300-3400 Hz) in 50 ms frames, plotted on twin axis
            X = np.fft.rfft(x[: len(x) // 800 * 800].reshape(-1, 800), axis=1)
            f = np.fft.rfftfreq(800, 1 / 16000)
            band = (f >= 300) & (f <= 3400)
            e = 10 * np.log10((np.abs(X[:, band]) ** 2).sum(1) + 1e-9)
            tw = -2.0 + (np.arange(len(e)) + 0.5) * 0.05
            ax2 = ax.twinx()
            ax2.plot(tw, e, color="cyan", lw=1)
            ax2.set_yticks([])
            ax.axvline(0, color="lime", lw=1.5)
            ax.axvline(-0.5, color="lime", lw=0.8, ls=":")
            ax.axvline(0.5, color="lime", lw=0.8, ls=":")
            ax.set_xlim(-2, 2)
            ax.set_ylabel(r["row"], fontsize=12, color="red")
            ax.set_yticks([])
        axs[-1].set_xlabel("seconds from t")
        fig.tight_layout()
        p = out / f"speech_sheet{s // per:02d}.png"
        fig.savefig(p, dpi=80)
        plt.close(fig)
        paths.append(str(p))
    return paths


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", default="/tribe/insight/verify")
    a = ap.parse_args()
    out = Path(a.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(SEED)
    stems = stems_included()
    preds_n = {s: int(np.load(f"/tribe/ugc_preds/{s}_preds.npy", mmap_mode="r").shape[0])
               for s in stems}
    key = {}
    with Pool(12) as pool:
        for fam in FAMILIES:
            ev = json.loads((EVD / f"{'cuts' if fam == 'cuts' else fam}.json").read_text())
            events = {s: ev[s]["events"] for s in stems}
            rows = sample(fam, stems, preds_n, events, rng)
            key[fam] = rows
            if fam == "speech":
                speech_sheets(rows, out)
            else:
                visual_sheets(fam, rows, out, pool)
    (out / "key.json").write_text(json.dumps(key, indent=1))
    print({f: len(r) for f, r in key.items()})


if __name__ == "__main__":
    main()
