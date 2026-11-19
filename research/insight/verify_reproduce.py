"""Independent reproduction of the event-locked effect design (does not import event_effects).

Design re-implemented from its written description:
  * signals = norms.timecourses(preds, run_and_save._BATCH_MASKS); z-score within clip with
    mean/SD from predicted seconds >= 4.
  * event video time t -> s = floor(t); keep if s >= 3 and s + 7 <= n - 1.
  * baseline = mean z at predicted s+1..s+3, response = mean z at s+4..s+7, effect = resp - base.
  * clip mean of event effects, then mean across clips; percentile bootstrap over clips.
  * null: per-clip circular shift of event seconds within the valid range [3, n-8].

Extra checks (verification only):
  * p_zero : two-sided around 0 (as in the stated design).
  * p_cent : two-sided around the null mean, |null - mu| >= |obs - mu|. This is the test the
             design needs when the null is off-centre (within-clip drift + asymmetric windows).
  * lag scan: effect for alternative response offsets (lag 2..6) to probe the 4 s assumption.

Prints aggregates only (no clip identifiers). Run inside the tribe container.
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
rng = np.random.default_rng(7)
N_PERM = 4000
N_BOOT = 5000


def z(x):
    x = np.asarray(x, float)
    r = x[4:]
    return (x - r.mean()) / r.std()


vet = json.loads(Path("/tribe/work/vetting.json").read_text())
stems = sorted(v["name"].removesuffix(".mp4") for v in vet if v.get("include"))
fams = {f: json.loads((EV / f"{f}.json").read_text()) for f in ["speech", "cuts", "faces", "text"]}

clips = {}
for st in stems:
    p = np.load(f"/tribe/ugc_preds/{st}_preds.npy")
    tc = norms.timecourses(p, run_and_save._BATCH_MASKS)
    sigs = list(tc)
    n = p.shape[0]
    Z = {k: z(tc[k]) for k in sigs}
    evs = []
    for f in fams.values():
        evs += [(e["type"], float(e["t"])) for e in f[st]["events"]]
    clips[st] = dict(n=n, Z=Z, ev=evs)


def eff_at(Z, s, base=(1, 3), resp=(4, 7)):
    b = np.mean([Z[s + k] for k in range(base[0], base[1] + 1)])
    r = np.mean([Z[s + k] for k in range(resp[0], resp[1] + 1)])
    return r - b


types = sorted({t for c in clips.values() for t, _ in c["ev"]})
out = []
for et in types:
    per = {}
    for st, c in clips.items():
        n = c["n"]
        ss = [math.floor(t) for ty, t in c["ev"] if ty == et]
        ss = [s for s in ss if s >= 3 and s + 7 <= n - 1]
        if ss:
            per[st] = ss
    C = len(per)
    nev = sum(len(v) for v in per.values())
    if C < 10:
        continue
    for sig in sigs:
        cm = np.array([np.mean([eff_at(clips[st]["Z"][sig], s) for s in ss]) for st, ss in per.items()])
        obs = cm.mean()
        boot = cm[rng.integers(0, C, (N_BOOT, C))].mean(1)
        lo, hi = np.percentile(boot, [2.5, 97.5])
        # precompute per-clip effect table over valid seconds
        tabs = {}
        for st in per:
            n = clips[st]["n"]
            valid = np.arange(3, n - 7)
            tabs[st] = (valid, np.array([eff_at(clips[st]["Z"][sig], s) for s in valid]))
        null = np.empty(N_PERM)
        for i in range(N_PERM):
            acc = 0.0
            for st, ss in per.items():
                valid, E = tabs[st]
                m = len(valid)
                k = rng.integers(0, m)
                idx = (np.asarray(ss) - 3 + k) % m
                acc += E[idx].mean()
            null[i] = acc / C
        mu = null.mean()
        p0 = (1 + (np.abs(null) >= abs(obs) - 1e-12).sum()) / (1 + N_PERM)
        pc = (1 + (np.abs(null - mu) >= abs(obs - mu) - 1e-12).sum()) / (1 + N_PERM)
        lags = {}
        for L in (2, 3, 5, 6):
            # baseline = 3 s before video onset at lag L, response = 4 s after at lag L
            v = []
            for st, ss in per.items():
                n = clips[st]["n"]
                e = [eff_at(clips[st]["Z"][sig], s, (L - 3, L - 1), (L, L + 3))
                     for s in ss if s + L - 3 >= 4 and s + L + 3 <= n - 1]
                if e:
                    v.append(np.mean(e))
            lags[L] = round(float(np.mean(v)), 3) if v else None
        out.append(dict(event=et, signal=sig, n_events=nev, n_clips=C, effect=round(obs, 4),
                        ci=[round(lo, 4), round(hi, 4)], null_mean=round(mu, 4),
                        null_sd=round(null.std(), 4), p_zero=round(p0, 4), p_cent=round(pc, 4),
                        lag_effects=lags))


def bh(p):
    p = np.asarray(p)
    m = len(p)
    o = np.argsort(p)
    r = p[o] * m / np.arange(1, m + 1)
    q = np.minimum.accumulate(r[::-1])[::-1]
    res = np.empty(m)
    res[o] = np.minimum(q, 1)
    return res


qz = bh([r["p_zero"] for r in out])
qc = bh([r["p_cent"] for r in out])
for r, a, b in zip(out, qz, qc):
    r["q_zero"] = round(float(a), 4)
    r["q_cent"] = round(float(b), 4)
print(json.dumps(out))
