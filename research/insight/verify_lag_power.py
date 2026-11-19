"""Verification: (1) is the 4 s BOLD lag right?  (2) how many events do the edge rules drop?
(3) what effect size could the design have detected?  Aggregates only, no clip identifiers.

(1) Within clip, correlate a video-time per-second feature x[v] with a predicted signal z[p]
    at lag L (p = v + L, p >= 4), pooled as the mean of per-clip Pearson r over clips.
    The peak lag is the model's effective lag for that feature/signal pair.
(3) Minimum detectable |effect - null_mean| at BH rank 1 over 56 tests (alpha 0.10/56 two-sided),
    using the null SD from the reproduction output.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np
from scipy.stats import norm

sys.path.insert(0, "/tribe/work_main")
from tribe_scoring import norms, run_and_save  # noqa: E402

EV = Path("/tribe/insight/events")
vet = json.loads(Path("/tribe/work/vetting.json").read_text())
stems = sorted(v["name"].removesuffix(".mp4") for v in vet if v.get("include"))
fams = {f: json.loads((EV / f"{f}.json").read_text()) for f in ["speech", "cuts", "faces", "text"]}

pairs = [("cuts", "motion_energy", "motion"), ("cuts", "motion_energy", "gfp"),
         ("cuts", "cuts", "motion"), ("speech", "speech", "language"),
         ("speech", "speech", "auditory"), ("speech", "words_per_s", "language"),
         ("faces", "face", "social"), ("text", "text", "language")]
LAGS = range(0, 9)
acc = {p: {L: [] for L in LAGS} for p in pairs}
len_mismatch = 0
for st in stems:
    pr = np.load(f"/tribe/ugc_preds/{st}_preds.npy")
    tc = norms.timecourses(pr, run_and_save._BATCH_MASKS)
    n = pr.shape[0]
    for fam, feat, sig in pairs:
        x = np.asarray(fams[fam][st]["per_second"][feat], float)
        if abs(len(x) - n) > 1:
            len_mismatch += 1
        y = np.asarray(tc[sig], float)
        for L in LAGS:
            v = np.arange(max(0, 4 - L), min(len(x), n - L))
            if len(v) < 6:
                continue
            a, b = x[v], y[v + L]
            if a.std() == 0 or b.std() == 0:
                continue
            acc[(fam, feat, sig)][L].append(np.corrcoef(a, b)[0, 1])

print("per_second length mismatches (>1 s):", len_mismatch)
for p in pairs:
    row = {L: (round(float(np.mean(acc[p][L])), 3), len(acc[p][L])) for L in LAGS if acc[p][L]}
    peak = max(row, key=lambda L: abs(row[L][0]))
    print(f"{p[1]:>14s} -> {p[2]:<9s} peak lag {peak}: " +
          " ".join(f"L{L}:{row[L][0]:+.3f}" for L in row))

# (2) event loss by the s >= 3 and s + 7 < n rules
print("\nevent loss by edge rules")
for fam in fams.values():
    pass
types = {}
for st in stems:
    n = np.load(f"/tribe/ugc_preds/{st}_preds.npy", mmap_mode="r").shape[0]
    for f in fams.values():
        for e in f[st]["events"]:
            s = math.floor(e["t"])
            d = types.setdefault(e["type"], [0, 0, 0])
            d[0] += 1
            d[1] += s < 3
            d[2] += s + 7 >= n
for t, (tot, early, late) in sorted(types.items()):
    print(f"{t:<15s} total {tot:4d}  dropped s<3: {early:3d} ({early/tot:.0%})  dropped tail: {late:3d} ({late/tot:.0%})")

# (3) MDE from null SD
rep = Path("/tribe/insight/verify_reproduce_out.json")
if rep.exists():
    out = json.loads(rep.read_text())
    zc = norm.ppf(1 - 0.10 / len(out) / 2)
    mdes = sorted((round(zc * r["null_sd"], 3), r["event"], r["signal"]) for r in out)
    print(f"\nz crit for BH rank-1 at q<0.10 over {len(out)} tests: {zc:.2f}")
    print("MDE |effect - null_mean| (SD units): min", mdes[0], "median", mdes[len(mdes)//2], "max", mdes[-1])
    by_ev = {}
    for m, e, s in mdes:
        by_ev.setdefault(e, []).append(m)
    for e, v in sorted(by_ev.items()):
        print(f"  {e:<15s} MDE range {min(v):.2f}-{max(v):.2f}")
