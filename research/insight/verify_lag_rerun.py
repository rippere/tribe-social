"""Verification: rerun the event-locked test at alternative BOLD lags, with a centred null.

For lag L (predicted second p reflects video second p - L):
  baseline = predicted s+L-3 .. s+L-1   (video s-3..s-1)
  response = predicted s+L   .. s+L+3   (video s..s+3)
  keep s if s+L-3 >= 4 and s+L+3 <= n-1.
Null: per-clip circular shift within the valid range (same as the design). p is two-sided
around the null mean. BH over all 56 tests per lag. Also prints a cross-correlation of
per-second features vs signals at negative lags. Aggregates only.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, "/tribe/work_main")
from tribe_scoring import norms, run_and_save  # noqa: E402

EV = Path("/tribe/insight/events")
vet = json.loads(Path("/tribe/work/vetting.json").read_text())
stems = sorted(v["name"].removesuffix(".mp4") for v in vet if v.get("include"))
fams = {f: json.loads((EV / f"{f}.json").read_text()) for f in ["speech", "cuts", "faces", "text"]}
rng = np.random.default_rng(11)
N_PERM = 2000

clips = {}
for st in stems:
    pr = np.load(f"/tribe/ugc_preds/{st}_preds.npy")
    tc = norms.timecourses(pr, run_and_save._BATCH_MASKS)
    sigs = list(tc)
    Z = np.stack([np.asarray(tc[k], float) for k in sigs], 1)
    Z = (Z - Z[4:].mean(0)) / Z[4:].std(0)
    ev = [(e["type"], float(e["t"])) for f in fams.values() for e in f[st]["events"]]
    ps = {k: np.asarray(fams[f][st]["per_second"][k], float)
          for f, k in [("cuts", "motion_energy"), ("speech", "speech"), ("faces", "face")]}
    clips[st] = dict(n=pr.shape[0], Z=Z, ev=ev, ps=ps, tc=tc)

# negative-lag cross-correlation check
print("xcorr (mean within-clip r), predicted p vs video p-L")
for feat, sig in [("motion_energy", "motion"), ("speech", "auditory"), ("face", "social")]:
    row = []
    for L in range(-3, 5):
        rs = []
        for c in clips.values():
            x, y = c["ps"][feat], np.asarray(c["tc"][sig], float)
            v = np.arange(max(0, 4 - L), min(len(x), c["n"] - L))
            v = v[(v + L >= 4) & (v + L < c["n"])]
            if len(v) > 6 and x[v].std() > 0 and y[v + L].std() > 0:
                rs.append(np.corrcoef(x[v], y[v + L])[0, 1])
        row.append(f"L{L:+d}:{np.mean(rs):+.3f}")
    print(f"  {feat:>13s}->{sig:<9s}", " ".join(row))


def bh(p):
    p = np.asarray(p)
    m = len(p)
    o = np.argsort(p)
    q = np.minimum.accumulate((p[o] * m / np.arange(1, m + 1))[::-1])[::-1]
    r = np.empty(m)
    r[o] = np.minimum(q, 1)
    return r


types = sorted({t for c in clips.values() for t, _ in c["ev"]})
for L in (0, 1, 2, 4):
    rows = []
    for c in clips.values():
        n = c["n"]
        lo, hi = max(0, 7 - L), n - 4 - L          # valid s range inclusive
        sec = np.arange(lo, hi + 1)
        if len(sec) <= 0:
            c["E"], c["lo"], c["m"] = None, lo, 0
            continue
        Z = c["Z"]
        base = np.mean([Z[sec + L + k] for k in (-3, -2, -1)], 0)
        resp = np.mean([Z[sec + L + k] for k in (0, 1, 2, 3)], 0)
        c["E"], c["lo"], c["m"] = resp - base, lo, len(sec)
    for et in types:
        kept = {}
        for st, c in clips.items():
            idx = [math.floor(t) - c["lo"] for ty, t in c["ev"] if ty == et]
            idx = [i for i in idx if 0 <= i < c["m"]]
            if idx:
                kept[st] = np.array(idx)
        if len(kept) < 10:
            continue
        cm = np.stack([clips[s]["E"][i].mean(0) for s, i in kept.items()])
        obs = cm.mean(0)
        null = np.zeros((N_PERM, len(sigs)))
        for st, i in kept.items():
            c = clips[st]
            ks = rng.integers(0, c["m"], N_PERM)
            null += c["E"][(i[None, :] + ks[:, None]) % c["m"]].mean(1)
        null /= len(kept)
        mu = null.mean(0)
        p = (1 + (np.abs(null - mu) >= np.abs(obs - mu) - 1e-12).sum(0)) / (1 + N_PERM)
        boot = cm[rng.integers(0, len(kept), (3000, len(kept)))].mean(1) - mu
        lo_, hi_ = np.percentile(boot, [2.5, 97.5], 0)
        for j, s in enumerate(sigs):
            rows.append(dict(event=et, signal=s, nc=len(kept),
                             ne=int(sum(len(v) for v in kept.values())),
                             eff=obs[j], adj=obs[j] - mu[j], lo=lo_[j], hi=hi_[j], p=p[j]))
    q = bh([r["p"] for r in rows])
    for r, qq in zip(rows, q):
        r["q"] = qq
    rows.sort(key=lambda r: r["p"])
    print(f"\nLAG {L}: tests {len(rows)}, q<0.10: {sum(r['q'] < 0.10 for r in rows)}, "
          f"q<0.20: {sum(r['q'] < 0.20 for r in rows)}")
    for r in rows[:8]:
        print(f"  {r['event']:<15s}{r['signal']:<10s} n_ev {r['ne']:4d} n_cl {r['nc']:3d} "
              f"eff {r['eff']:+.3f} eff-null {r['adj']:+.3f} [{r['lo']:+.3f},{r['hi']:+.3f}] "
              f"p {r['p']:.4f} q {r['q']:.3f}")
