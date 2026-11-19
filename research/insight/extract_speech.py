"""Speech content-event extractor for the TRIBE insight reference set.

Reads the whisperx word timings (<stem>.tsv: text, start, duration,
sequence_id, sentence) for every included clip and writes the shared
event format to <out_dir>/speech.json:

    {"<stem>": {"duration_s": float,
                "events": [{"type": "speech_onset" | "pause_start", "t": float}],
                "per_second": {"speech": [...], "words_per_s": [...]}}}

Event definitions (all times in VIDEO seconds; no BOLD lag applied here):
  speech_onset  first word of the clip, or first word after >= GAP_S without words
  pause_start   end of a word followed by >= GAP_S without words (including a
                trailing gap to the end of the clip)
per_second (one value per whole video second, n = ceil(duration_s)):
  speech        fraction of [k, k+1) covered by the union of word intervals
  words_per_s   number of word onsets in [k, k+1)

Word intervals are capped at MAX_WORD_S: whisperx occasionally stretches one
word over a long silence/music stretch, which would hide real pauses.

A spot-check compares the TSV against speech-band (300-3400 Hz) RMS energy
from the .wav for N_SPOT clips and writes <out_dir>/speech_qa.json.

Run inside the `tribe` container:
    python extract_speech.py [--workers 12]
"""
from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import sys
from multiprocessing import Pool

import numpy as np

UGC_DIR = "/tribe/ugc"
VETTING = "/tribe/work/vetting.json"
OUT_DIR = "/tribe/insight/events"

GAP_S = 1.0
MAX_WORD_S = 1.5
N_SPOT = 5
SPOT_SEED = 7
FRAME_S = 0.05


# --------------------------------------------------------------------------- io
def included_stems() -> list[str]:
    with open(VETTING) as f:
        vet = json.load(f)
    return sorted(e["name"] for e in vet if e.get("include"))


def clip_meta(stem: str) -> dict:
    with open(VETTING) as f:
        vet = json.load(f)
    return next(e for e in vet if e["name"] == stem)


def video_duration(stem: str) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", f"{UGC_DIR}/{stem}.mp4"],
        capture_output=True, text=True, check=True).stdout
    return float(out.strip())


def read_words(stem: str) -> list[tuple[float, float]]:
    """Return [(start, end_raw)] sorted by start. Empty TSV -> []."""
    path = f"{UGC_DIR}/{stem}.tsv"
    words = []
    with open(path) as f:
        lines = f.read().splitlines()
    if not lines or not lines[0].strip():
        return []
    header = lines[0].split("\t")
    i_s, i_d = header.index("start"), header.index("duration")
    for ln in lines[1:]:
        if not ln.strip():
            continue
        parts = ln.split("\t")
        try:
            s, d = float(parts[i_s]), float(parts[i_d])
        except (ValueError, IndexError):
            continue
        if math.isnan(s) or math.isnan(d):
            continue
        words.append((s, s + max(d, 0.0)))
    words.sort()
    return words


# ------------------------------------------------------------------- extraction
def cap_words(words, duration):
    capped, n_capped = [], 0
    for s, e in words:
        if e - s > MAX_WORD_S:
            e = s + MAX_WORD_S
            n_capped += 1
        if s >= duration:
            continue
        s, e = max(0.0, s), min(duration, e)
        capped.append((s, max(e, s)))
    return capped, n_capped


def detect_events(words, duration):
    events = []
    last_end = None
    for s, e in words:
        if last_end is None:
            events.append({"type": "speech_onset", "t": round(s, 3)})
        elif s - last_end >= GAP_S:
            events.append({"type": "pause_start", "t": round(last_end, 3)})
            events.append({"type": "speech_onset", "t": round(s, 3)})
        last_end = e if last_end is None else max(last_end, e)
    if last_end is not None and duration - last_end >= GAP_S:
        events.append({"type": "pause_start", "t": round(last_end, 3)})
    events.sort(key=lambda ev: (ev["t"], ev["type"]))
    return events


def per_second(words, duration):
    n = int(math.ceil(duration - 1e-9))
    cover = np.zeros(n)
    wps = np.zeros(n)
    # union of intervals
    merged = []
    for s, e in words:
        if merged and s <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], e)
        else:
            merged.append([s, e])
    for s, e in merged:
        for k in range(int(s), min(n, int(math.ceil(e)))):
            cover[k] += max(0.0, min(e, k + 1) - max(s, k))
    for s, _ in words:
        k = int(s)
        if 0 <= k < n:
            wps[k] += 1
    return (np.clip(cover, 0, 1).round(4).tolist(), wps.astype(int).tolist())


def extract_one(stem: str):
    duration = video_duration(stem)
    raw = read_words(stem)
    words, n_capped = cap_words(raw, duration)
    speech, wps = per_second(words, duration)
    rec = {
        "duration_s": round(duration, 3),
        "events": detect_events(words, duration),
        "per_second": {"speech": speech, "words_per_s": wps},
    }
    stats = {"n_words": len(raw), "n_capped": n_capped,
             "max_word_s": max((e - s for s, e in raw), default=0.0)}
    return stem, rec, stats


# -------------------------------------------------------------------- spot-check
def load_band_db(stem: str):
    import soundfile as sf
    from scipy.signal import butter, sosfiltfilt
    x, sr = sf.read(f"{UGC_DIR}/{stem}.wav", always_2d=True)
    x = x.mean(axis=1)
    sos = butter(4, [300, 3400], btype="band", fs=sr, output="sos")
    y = sosfiltfilt(sos, x)
    hop = int(round(FRAME_S * sr))
    nfr = len(y) // hop
    fr = y[: nfr * hop].reshape(nfr, hop)
    rms = np.sqrt((fr ** 2).mean(axis=1))
    db = 20 * np.log10(rms + 1e-8)
    # envelope at 100 Hz for modulation index
    hop_env = sr // 100
    ne = len(y) // hop_env
    env = np.sqrt((y[: ne * hop_env].reshape(ne, hop_env) ** 2).mean(axis=1))
    return db, env, sr


def modulation_index(env):
    """Fraction of envelope power (DC removed) in 2-8 Hz; speech is typically high."""
    e = env - env.mean()
    if len(e) < 200:
        return float("nan")
    p = np.abs(np.fft.rfft(e)) ** 2
    f = np.fft.rfftfreq(len(e), d=0.01)
    band = p[(f >= 2) & (f <= 8)].sum()
    tot = p[(f > 0.25) & (f <= 50)].sum()
    return float(band / tot) if tot > 0 else float("nan")


def auc(pos, neg):
    """Mann-Whitney AUC: P(word frame louder than non-word frame)."""
    if len(pos) == 0 or len(neg) == 0:
        return float("nan")
    from scipy.stats import rankdata
    ranks = rankdata(np.concatenate([pos, neg]))  # average ranks for ties
    r_pos = ranks[: len(pos)].sum()
    return float((r_pos - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg)))


def spot_one(stem: str):
    duration = video_duration(stem)
    words, _ = cap_words(read_words(stem), duration)
    db, env, _ = load_band_db(stem)
    nfr = len(db)
    centers = (np.arange(nfr) + 0.5) * FRAME_S
    mask = np.zeros(nfr, bool)
    for s, e in words:
        mask[(centers >= s) & (centers < e)] = True
    p10, p90 = np.percentile(db, [10, 90])
    thr = p10 + 0.5 * (p90 - p10)
    active = db > thr
    out = {
        "n_words": len(words),
        "tsv_speech_frac": float(mask.mean()),
        "energy_active_frac": float(active.mean()),
        "dynamic_range_db_p90_p10": float(p90 - p10),
        "mod_index_2_8hz": modulation_index(env),
    }
    if words:
        agree = float((mask == active).mean())
        po, pe_ = agree, mask.mean() * active.mean() + (1 - mask.mean()) * (1 - active.mean())
        kappa = float((po - pe_) / (1 - pe_)) if pe_ < 1 else float("nan")
        a = auc(db[mask], db[~mask])
        # block bootstrap over 1-s blocks for AUC CI
        rng = np.random.default_rng(0)
        blk = int(round(1 / FRAME_S))
        nb = nfr // blk
        boots = []
        for _ in range(300):
            idx = rng.integers(0, nb, nb)
            fi = (idx[:, None] * blk + np.arange(blk)[None, :]).ravel()
            m, d = mask[fi], db[fi]
            if m.any() and (~m).any():
                boots.append(auc(d[m], d[~m]))
        lo, hi = (np.percentile(boots, [2.5, 97.5]) if boots else (np.nan, np.nan))
        # per-second correlation
        n = int(math.ceil(duration - 1e-9))
        sp, _ = per_second(words, duration)
        sec_db = [db[(centers >= k) & (centers < k + 1)].mean() if ((centers >= k) & (centers < k + 1)).any() else np.nan
                  for k in range(n)]
        sp, sec_db = np.array(sp), np.array(sec_db)
        ok = ~np.isnan(sec_db)
        r = float(np.corrcoef(sp[ok], sec_db[ok])[0, 1]) if ok.sum() > 2 and sp[ok].std() > 0 else float("nan")
        # pauses: energy inside >= GAP_S gaps vs inside words
        gaps = []
        last = None
        for s, e in words:
            if last is not None and s - last >= GAP_S:
                gaps.append((last, s))
            last = e if last is None else max(last, e)
        if last is not None and duration - last >= GAP_S:
            gaps.append((last, duration))
        gmask = np.zeros(nfr, bool)
        for s, e in gaps:
            gmask[(centers >= s) & (centers < e)] = True
        out.update({
            "frame_agreement": agree,
            "cohen_kappa": kappa,
            "auc_word_vs_nonword_db": a,
            "auc_ci95": [float(lo), float(hi)],
            "per_second_r_speech_vs_db": r,
            "n_pause_gaps": len(gaps),
            "pause_gap_minus_word_db": float(db[gmask].mean() - db[mask].mean()) if gmask.any() else float("nan"),
            "word_frames_active_frac": float(active[mask].mean()),
            "pause_frames_active_frac": float(active[gmask].mean()) if gmask.any() else float("nan"),
        })
    return out


def pick_spot(stems, stats):
    rng = np.random.default_rng(SPOT_SEED)
    meta = {s: clip_meta(s) for s in stems}
    with_sp = [s for s in stems if stats[s]["n_words"] > 0]
    no_sp = [s for s in stems if stats[s]["n_words"] == 0]
    picks = []
    for fmt in ("ugc", "polished_spot"):
        pool = [s for s in with_sp if meta[s].get("format") == fmt]
        picks += list(rng.choice(pool, size=min(2, len(pool)), replace=False))
    if no_sp:
        picks.append(str(rng.choice(no_sp)))
    return [str(p) for p in picks][:N_SPOT]


# -------------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=12)
    ap.add_argument("--out-dir", default=OUT_DIR)
    args = ap.parse_args()
    workers = max(1, min(12, args.workers))

    stems = included_stems()
    with Pool(workers) as pool:
        results = pool.map(extract_one, stems)
    out = {s: rec for s, rec, _ in results}
    stats = {s: st for s, _, st in results}

    os.makedirs(args.out_dir, exist_ok=True)
    with open(os.path.join(args.out_dir, "speech.json"), "w") as f:
        json.dump(out, f)

    spot = pick_spot(stems, stats)
    with Pool(min(workers, len(spot))) as pool:
        spot_res = pool.map(spot_one, spot)

    n_ev = {}
    for rec in out.values():
        for ev in rec["events"]:
            n_ev[ev["type"]] = n_ev.get(ev["type"], 0) + 1
    qa = {
        "params": {"gap_s": GAP_S, "max_word_s": MAX_WORD_S, "frame_s": FRAME_S,
                   "band_hz": [300, 3400], "threshold": "p10 + 0.5*(p90-p10) of per-clip band dB"},
        "n_clips": len(out),
        "n_clips_no_words": sum(1 for s in stems if stats[s]["n_words"] == 0),
        "n_words_total": sum(st["n_words"] for st in stats.values()),
        "n_words_capped": sum(st["n_capped"] for st in stats.values()),
        "n_events_by_type": n_ev,
        "spot_check": {s: r for s, r in zip(spot, spot_res)},
        "per_clip_stats": stats,
    }
    with open(os.path.join(args.out_dir, "speech_qa.json"), "w") as f:
        json.dump(qa, f, indent=1)

    # stdout summary without clip names
    print(json.dumps({k: qa[k] for k in ("n_clips", "n_clips_no_words", "n_words_total",
                                          "n_words_capped", "n_events_by_type")}))
    for i, s in enumerate(spot):
        r = spot_res[i]
        print(f"spot[{i}] fmt={clip_meta(s).get('format')} " +
              " ".join(f"{k}={v:.3f}" if isinstance(v, float) else f"{k}={v}" for k, v in r.items()))


if __name__ == "__main__":
    sys.exit(main())
