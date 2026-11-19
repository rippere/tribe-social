"""Window/lag sanity check for event_effects.py.

Question: does the fixed window (baseline = predicted s+1..s+3, response =
predicted s+4..s+7) sit where TRIBE's predicted response to content actually
lands? Two model-internal measurements, both over the 64 included clips:

1. Lagged correlation: for each per-second content feature x (cut count, face
   fraction, text fraction, speech fraction, words/s, motion energy) and each
   signal y (z-scored within clip over predicted seconds >= 4), the Pearson r of
   x[k] with y[k + L] for L = 0..10, using only k + L >= 4. r is computed per clip,
   Fisher-averaged across clips (clips with < 8 valid pairs or constant x are
   skipped). The peak lag tells where the predicted response to x lands.

2. Event-locked curve: for each event type, mean z at predicted offsets s-2..s+10
   (event second s = floor(t)), minus the same curve under 500 within-clip
   circular shifts (drift removed). Clip-averaged; seconds < 4 excluded.

Aggregate output only (no clip ids): --out json.

Run inside the `tribe` container:
    python verify_lag.py --out /tribe/insight/verify/lag.json
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, "/tribe/work_main")
from tribe_scoring import norms, run_and_save  # noqa: E402

VET = Path("/tribe/work/vetting.json")
EVD = Path("/tribe/insight/events")
PRED = Path("/tribe/ugc_preds")
WARM = 4
LAGS = range(0, 11)
OFFS = range(-2, 11)
N_SHIFT = 500
SEED = 99

FEATS = {"cuts": ("cuts", "cuts"), "motion_energy": ("cuts", "motion_energy"),
         "face": ("faces", "face"), "text": ("text", "text"),
         "speech": ("speech", "speech"), "words_per_s": ("speech", "words_per_s")}


def z(x):
    r = x[WARM:]
    sd = r.std()
    return (x - r.mean()) / (sd if sd > 0 else 1.0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="/tribe/insight/verify/lag.json")
    a = ap.parse_args()
    rng = np.random.default_rng(SEED)
    vet = json.loads(VET.read_text())
    stems = sorted(v["name"][:-4] if v["name"].endswith(".mp4") else v["name"]
                   for v in vet if v.get("include"))
    fam = {f: json.loads((EVD / f"{f}.json").read_text()) for f in ("cuts", "faces", "text", "speech")}
    masks = run_and_save._BATCH_MASKS
    sigs = None
    Z = {}
    for st in stems:
        tc = norms.timecourses(np.load(PRED / f"{st}_preds.npy"), masks)
        sigs = sigs or list(tc)
        Z[st] = np.stack([z(np.asarray(tc[s], float)) for s in sigs], 1)

    # 1. lagged correlations
    lag = {}
    for fn, (f, key) in FEATS.items():
        lag[fn] = {}
        for j, s in enumerate(sigs):
            rows = []
            for L in LAGS:
                zs = []
                for st in stems:
                    x = np.asarray([np.nan if v is None else v for v in fam[f][st]["per_second"][key]], float)
                    y = Z[st][:, j]
                    n = min(len(x), len(y))
                    k = np.arange(n)
                    ok = (k + L >= WARM) & (k + L < n)
                    xx, yy = x[k[ok]], y[k[ok] + L]
                    m = ~np.isnan(xx)
                    xx, yy = xx[m], yy[m]
                    if len(xx) < 8 or xx.std() == 0 or yy.std() == 0:
                        continue
                    r = np.corrcoef(xx, yy)[0, 1]
                    zs.append(np.arctanh(np.clip(r, -0.999, 0.999)))
                zs = np.asarray(zs)
                se = zs.std(ddof=1) / math.sqrt(len(zs)) if len(zs) > 1 else float("nan")
                rows.append({"lag": L, "r": float(np.tanh(zs.mean())), "n_clips": int(len(zs)),
                             "z_over_se": float(zs.mean() / se) if se > 0 else None})
            best = max(rows, key=lambda r: abs(r["r"]))
            lag[fn][s] = {"peak_lag": best["lag"], "peak_r": best["r"], "by_lag": rows}

    # 2. event-locked curves minus circular-shift null
    erp = {}
    for f in ("cuts", "faces", "text", "speech"):
        types = sorted({e["type"] for st in stems for e in fam[f][st]["events"]})
        for et in types:
            per_clip_obs, per_clip_null = [], []
            for st in stems:
                Zc = Z[st]
                n = len(Zc)
                ev = [math.floor(e["t"]) for e in fam[f][st]["events"] if e["type"] == et]
                if not ev:
                    continue

                def curve(evs):
                    out = np.full((len(OFFS), len(sigs)), np.nan)
                    for i, o in enumerate(OFFS):
                        vals = [Zc[s + o] for s in evs if WARM <= s + o < n]
                        if vals:
                            out[i] = np.mean(vals, 0)
                    return out

                obs = curve(ev)
                nul = np.nanmean([curve([(s + sh) % n for s in ev])
                                  for sh in rng.integers(1, n, N_SHIFT)], 0)
                per_clip_obs.append(obs)
                per_clip_null.append(nul)
            O = np.nanmean(per_clip_obs, 0)
            N = np.nanmean(per_clip_null, 0)
            D = O - N
            erp[et] = {"n_clips": len(per_clip_obs), "offsets": list(OFFS),
                       **{s: [round(float(v), 4) for v in D[:, j]] for j, s in enumerate(sigs)}}
            # simple window means of the drift-corrected curve
            idx = {o: i for i, o in enumerate(OFFS)}
            erp[et]["window_means"] = {
                s: {"base_1_3": round(float(np.nanmean(D[[idx[1], idx[2], idx[3]], j])), 4),
                    "resp_4_7": round(float(np.nanmean(D[[idx[k] for k in (4, 5, 6, 7)], j])), 4),
                    "peak_offset": int(list(OFFS)[int(np.nanargmax(np.abs(D[:, j])))])}
                for j, s in enumerate(sigs)}

    Path(a.out).write_text(json.dumps({"signals": sigs, "lagged_corr": lag, "erp_minus_null": erp}, indent=1))
    print("peak lags (feature -> signal: lag, r):")
    for fn in lag:
        print(" ", fn, {s: (v["peak_lag"], round(v["peak_r"], 3)) for s, v in lag[fn].items()})
    print("event-locked, drift-corrected peak offsets and base/resp means:")
    for et, d in erp.items():
        print(" ", et, d["n_clips"], {s: (w["peak_offset"], w["base_1_3"], w["resp_4_7"])
                                     for s, w in d["window_means"].items()})


if __name__ == "__main__":
    main()
