"""Event-locked analysis of TRIBE v2 predicted response around content events.

Fixed design (set before looking at any results):
  * Signals: norms.timecourses(preds, run_and_save._BATCH_MASKS) -> gfp + 7 ROI means.
  * Each signal is z-scored within clip. Mean and SD come from predicted seconds >= 4
    (post warm-up); every second the windows below touch is >= 4.
  * Event at video time t -> s = floor(t). Kept if s >= 3 and s + 7 < n_pred_seconds.
    baseline = mean z over predicted seconds s+1..s+3 (video s-3..s-1, pre-event)
    response = mean z over predicted seconds s+4..s+7 (video s..s+3 after ~4 s BOLD lag)
    effect   = response - baseline (within-clip SD units).
  * Per event type x signal: average effects within clip, then across clips (clips are
    the unit). 95% CI: percentile bootstrap over clips (5000 resamples).
  * p_perm: each clip's kept event seconds are circularly shifted by one random integer
    offset inside that clip's valid range [3, n-8] (same windows, same event count and
    spacing); 2000 shuffles; same offset for all signals within a shuffle; two-sided,
    p = (1 + #{|null| >= |obs|}) / (1 + n_perm).
  * Benjamini-Hochberg q over all tests that were run. A test runs only if n_clips >= 10.
  * Confound table: for each event type A, fraction of kept A events with >= 1 event of
    type B (any time, same clip) within +-1 s (self excluded for B == A).

This is model-internal: it describes what TRIBE's predicted response does around content
events, not viewer behaviour.

Usage (inside the tribe container):
  python event_effects.py --out /tribe/insight/event_effects.json \
                          --agg-out /tribe/insight/event_effects_aggregate.json
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path

import numpy as np

WORK_MAIN = "/tribe/work_main"
VETTING = Path("/tribe/work/vetting.json")
PREDS_DIR = Path("/tribe/ugc_preds")
EVENTS_DIR = Path("/tribe/insight/events")
FAMILIES = ["speech", "cuts", "faces", "text"]

WARMUP = 4            # predicted seconds 0..3 are warm-up
MIN_S = 3             # event second must be >= 3 (baseline s+1 >= 4)
BASE = (1, 3)         # inclusive offsets
RESP = (4, 7)         # inclusive offsets
MIN_CLIPS = 10
N_BOOT = 5000
N_PERM = 2000
Q_THRESH = 0.10
COOC_WIN = 1.0
SEED = 20261117


def load_masks():
    sys.path.insert(0, WORK_MAIN)
    from tribe_scoring import norms, run_and_save  # noqa: E402
    return norms, run_and_save._BATCH_MASKS


def stem_of(name: str) -> str:
    return name[:-4] if name.endswith(".mp4") else name


def zscore_post_warmup(x: np.ndarray) -> np.ndarray:
    ref = x[WARMUP:] if len(x) > WARMUP + 1 else x
    sd = ref.std()
    return (x - ref.mean()) / (sd if sd > 0 else 1.0)


def bh(pvals: list[float]) -> list[float]:
    p = np.asarray(pvals, float)
    m = len(p)
    if m == 0:
        return []
    order = np.argsort(p)
    ranked = p[order] * m / np.arange(1, m + 1)
    q = np.minimum.accumulate(ranked[::-1])[::-1]
    out = np.empty(m)
    out[order] = np.minimum(q, 1.0)
    return out.tolist()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="/tribe/insight/event_effects.json")
    ap.add_argument("--agg-out", default="/tribe/insight/event_effects_aggregate.json")
    args = ap.parse_args()
    t0 = time.time()
    rng = np.random.default_rng(SEED)

    norms, masks = load_masks()
    vet = json.loads(VETTING.read_text())
    stems = sorted(stem_of(v["name"]) for v in vet if v.get("include"))
    fam = {f: json.loads((EVENTS_DIR / f"{f}.json").read_text()) for f in FAMILIES}

    # ---- per-clip signals and per-second effect tables --------------------------------
    clips = {}
    signals = None
    for st in stems:
        preds = np.load(PREDS_DIR / f"{st}_preds.npy")
        tc = norms.timecourses(preds, masks)
        if signals is None:
            signals = list(tc)
        n = preds.shape[0]
        Z = np.stack([zscore_post_warmup(np.asarray(tc[s], float)) for s in signals], 1)  # (n, S)
        lo, hi = MIN_S, n - 8              # valid event seconds: lo..hi inclusive
        m = hi - lo + 1
        if m <= 0:
            E = np.zeros((0, len(signals)))
        else:
            sec = np.arange(lo, hi + 1)
            base = np.mean([Z[sec + k] for k in range(BASE[0], BASE[1] + 1)], 0)
            resp = np.mean([Z[sec + k] for k in range(RESP[0], RESP[1] + 1)], 0)
            E = resp - base                 # (m, S): effect if an event were at second lo+i
        ev = []
        for f in FAMILIES:
            rec = fam[f].get(st)
            if rec is None:
                raise SystemExit(f"missing clip in {f}.json")
            ev += [(e["type"], float(e["t"])) for e in rec["events"]]
        clips[st] = {"n": n, "lo": lo, "m": max(m, 0), "E": E, "events": ev}

    etypes = sorted({t for c in clips.values() for t, _ in c["events"]})
    S = len(signals)

    # ---- kept events per type per clip -----------------------------------------------
    kept = {et: {} for et in etypes}     # et -> stem -> array of indices into E
    for st, c in clips.items():
        for et in etypes:
            idx = [math.floor(t) - c["lo"] for ty, t in c["events"] if ty == et]
            idx = [i for i in idx if 0 <= i < c["m"]]
            if idx:
                kept[et][st] = np.asarray(idx, int)

    # ---- effects, bootstrap, permutation ---------------------------------------------
    results = []
    skipped = []
    per_clip_full = {}
    for et in etypes:
        cl = sorted(kept[et])
        n_ev = int(sum(len(kept[et][s]) for s in cl))
        if len(cl) < MIN_CLIPS:
            skipped.append({"event": et, "n_clips": len(cl), "n_events": n_ev,
                            "reason": f"n_clips < {MIN_CLIPS}"})
            continue
        cm = np.stack([clips[s]["E"][kept[et][s]].mean(0) for s in cl])   # (C, S)
        obs = cm.mean(0)
        C = len(cl)
        bidx = rng.integers(0, C, size=(N_BOOT, C))
        boot = cm[bidx].mean(1)                                            # (B, S)
        ci_lo, ci_hi = np.percentile(boot, [2.5, 97.5], axis=0)
        null = np.empty((N_PERM, S))
        for p in range(N_PERM):
            acc = np.zeros(S)
            for s in cl:
                c = clips[s]
                k = rng.integers(0, c["m"])
                acc += c["E"][(kept[et][s] + k) % c["m"]].mean(0)
            null[p] = acc / C
        pp = (1 + (np.abs(null) >= np.abs(obs)[None, :] - 1e-12).sum(0)) / (1 + N_PERM)
        null_sd = null.std(0)
        for j, sig in enumerate(signals):
            results.append({
                "event": et, "signal": sig,
                "effect_sd": float(obs[j]), "ci_lo": float(ci_lo[j]), "ci_hi": float(ci_hi[j]),
                "p_perm": float(pp[j]), "null_mean": float(null[:, j].mean()),
                "null_sd": float(null_sd[j]),
                # descriptive only: effect relative to the circular-shift null mean, which is
                # non-zero when a signal drifts within clip (window asymmetry).
                "effect_minus_null": float(obs[j] - null[:, j].mean()),
                "clip_sd": float(cm[:, j].std(ddof=1)),
                "n_events": n_ev, "n_clips": C,
                "frac_clips_positive": float((cm[:, j] > 0).mean()),
            })
        per_clip_full[et] = {s: {"n_events": int(len(kept[et][s])),
                                 **{sig: float(cm[i, j]) for j, sig in enumerate(signals)}}
                             for i, s in enumerate(cl)}

    qs = bh([r["p_perm"] for r in results])
    for r, q in zip(results, qs):
        r["q_fdr"] = float(q)
    survivors = [f'{r["event"]}:{r["signal"]}' for r in results if r["q_fdr"] < Q_THRESH]

    # ---- confound table: co-occurrence within +-1 s ---------------------------------
    cooc = {}
    for a in etypes:
        row = {}
        tot = 0
        hits = {b: 0 for b in etypes}
        for st, c in clips.items():
            ta = [t for ty, t in c["events"] if ty == a
                  and 0 <= math.floor(t) - c["lo"] < c["m"]]
            for t in ta:
                tot += 1
                for b in etypes:
                    tb = [u for ty, u in c["events"] if ty == b]
                    if b == a:
                        ok = sum(abs(u - t) <= COOC_WIN for u in tb) > 1
                    else:
                        ok = any(abs(u - t) <= COOC_WIN for u in tb)
                    hits[b] += ok
        for b in etypes:
            row[b] = round(hits[b] / tot, 4) if tot else None
        cooc[a] = {"n_events": tot, "rate": row}

    meta = {
        "design": {
            "signals": signals, "zscore": "within clip, mean/SD over predicted seconds >= 4",
            "event_second": "floor(t video s)", "min_event_second": MIN_S,
            "require": "s + 7 < n_predicted_seconds",
            "baseline_pred_offsets": list(range(BASE[0], BASE[1] + 1)),
            "response_pred_offsets": list(range(RESP[0], RESP[1] + 1)),
            "aggregation": "mean within clip, then mean across clips",
            "ci": f"percentile bootstrap over clips, {N_BOOT}",
            "null": f"per-clip circular shift of kept event seconds within [3, n-8], {N_PERM} shuffles, two-sided",
            "fdr": "Benjamini-Hochberg over all tests run", "q_threshold": Q_THRESH,
            "min_clips": MIN_CLIPS, "cooc_window_s": COOC_WIN, "seed": SEED,
        },
        "n_clips_total": len(clips),
        "n_tests": len(results),
        "runtime_s": round(time.time() - t0, 1),
    }
    agg = {**meta, "effects": results, "survivors": survivors, "skipped": skipped,
           "cooccurrence_pm1s": cooc}
    full = {**agg, "per_clip_effects": per_clip_full}
    Path(args.out).write_text(json.dumps(full, indent=1))
    Path(args.agg_out).write_text(json.dumps(agg, indent=1))
    print(json.dumps({"n_tests": len(results), "survivors": survivors, "skipped": skipped,
                      "runtime_s": meta["runtime_s"]}))


if __name__ == "__main__":
    main()
