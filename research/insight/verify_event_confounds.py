"""Adversarial check of event_effects.py's null result (confounds lens).

Asks whether a real event effect could have been missed. Checks:
  0. replicate: recompute event_effects' observed effects from the same inputs.
  1. lag: is BOLD lag ~4 s in TRIBE's output? Within-clip correlation of detrended signal
     at predicted second t with a detrended video feature at second t - L, L = -2..10.
  2. test validity: the original p uses |null| >= |obs| with a null that is not centred
     (drift). Recompute with each clip's effect series demeaned over its valid seconds
     (this is exactly the circular-shift null mean, so the demeaned null is centred at 0).
  3. isolation: keep only events with no other-type event within +-2 s (iso_other), and
     with no other event of any type within +-2 s (iso_all).
  4. joint FIR model: Z[t] ~ sum_type sum_lag beta * count(type events at t - lag), lags
     0..9, clip intercept + linear trend projected out; contrast mean(lag 4..7) -
     mean(lag 1..3) (= original windows). Variant adds lagged continuous per-second
     features from the other event families as covariates. p: circular shift of the target
     type's events within clip, others fixed; CI: cluster bootstrap over clips.
  5. band percentile rank instead of within-clip z (norm_band_ugc64_v1, seconds < 40).
  6. leave-one-clip-out range, and dependence on clip length / category / format / arm.

Model-internal only (what TRIBE predicts), not viewer behaviour. Writes aggregate output
only (no clip ids).

Usage (inside the tribe container):
  python verify_event_confounds.py --out /tribe/insight/verify_event_confounds.json
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path

import numpy as np
from scipy import stats

sys.path.insert(0, "/tribe/insight")
import event_effects as ee  # noqa: E402

BAND = Path("/tribe/work_main/norm_band_ugc64_v1.json")
ISO_WIN = 2.0
LAGS = np.arange(0, 10)   # overridden by --lags
BASE_OFF = (1, 3)         # overridden by --base
RESP_OFF = (4, 7)         # overridden by --resp
N_PERM = 2000
N_PERM_FIR = 1000
N_BOOT = 2000
SEED = 7041
CONT = {"speech": ["words_per_s"], "cuts": ["motion_energy"], "faces": ["face_area"],
        "text": ["text_area"]}
TYPE_FAMILY = {"speech_onset": "speech", "pause_start": "speech", "cut": "cuts",
               "face_appear": "faces", "face_disappear": "faces", "text_appear": "text",
               "text_change": "text"}


def detrend(x):
    t = np.arange(len(x), dtype=float)
    A = np.stack([np.ones_like(t), t], 1)
    b, *_ = np.linalg.lstsq(A, x, rcond=None)
    return x - A @ b


def lo_hi(n):
    """valid event seconds: every window second is >= 4 (post warm-up) and < n."""
    return 4 - BASE_OFF[0], n - 1 - RESP_OFF[1]


def effect_series(Y, n):
    """(m, S) resp - base for event seconds lo..hi."""
    lo, hi = lo_hi(n)
    if hi < lo:
        return np.zeros((0, Y.shape[1]))
    sec = np.arange(lo, hi + 1)
    base = np.mean([Y[sec + k] for k in range(BASE_OFF[0], BASE_OFF[1] + 1)], 0)
    resp = np.mean([Y[sec + k] for k in range(RESP_OFF[0], RESP_OFF[1] + 1)], 0)
    return resp - base


def run_test(E, kept, rng, n_perm=N_PERM, demean=False):
    """E: stem -> (m,S); kept: stem -> idx array. Returns dict of arrays (S,)."""
    cl = sorted(kept)
    Es = {s: (E[s] - E[s].mean(0) if demean else E[s]) for s in cl}
    cm = np.stack([Es[s][kept[s]].mean(0) for s in cl])
    obs = cm.mean(0)
    C, S = cm.shape
    boot = cm[rng.integers(0, C, size=(N_BOOT, C))].mean(1)
    lo, hi = np.percentile(boot, [2.5, 97.5], 0)
    null = np.empty((n_perm, S))
    ms = {s: Es[s].shape[0] for s in cl}
    for p in range(n_perm):
        acc = np.zeros(S)
        for s in cl:
            k = rng.integers(0, ms[s])
            acc += Es[s][(kept[s] + k) % ms[s]].mean(0)
        null[p] = acc / C
    nm = null.mean(0)
    p_orig = (1 + (np.abs(null) >= np.abs(obs) - 1e-12).sum(0)) / (1 + n_perm)
    p_cent = (1 + (np.abs(null - nm) >= np.abs(obs - nm) - 1e-12).sum(0)) / (1 + n_perm)
    loco = np.stack([np.delete(cm, i, 0).mean(0) for i in range(C)]) if C > 2 else cm
    return {"obs": obs, "ci_lo": lo, "ci_hi": hi, "p_orig_style": p_orig, "p_centred": p_cent,
            "null_mean": nm, "null_sd": null.std(0), "loco_min": loco.min(0),
            "loco_max": loco.max(0), "n_clips": C,
            "n_events": int(sum(len(kept[s]) for s in cl)), "cm": cm, "clips": cl}


def bh(p):
    return ee.bh(list(p))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="/tribe/insight/verify_event_confounds.json")
    ap.add_argument("--base", default="1,3", help="baseline pred offsets a,b (inclusive)")
    ap.add_argument("--resp", default="4,7", help="response pred offsets a,b (inclusive)")
    ap.add_argument("--lags", default="0,9", help="FIR lag range a,b (inclusive)")
    ap.add_argument("--skip-fir", action="store_true")
    args = ap.parse_args()
    global BASE_OFF, RESP_OFF, LAGS
    BASE_OFF = tuple(int(x) for x in args.base.split(","))
    RESP_OFF = tuple(int(x) for x in args.resp.split(","))
    a, b = (int(x) for x in args.lags.split(","))
    LAGS = np.arange(a, b + 1)
    assert LAGS[0] <= BASE_OFF[0] and LAGS[-1] >= RESP_OFF[1]
    t0 = time.time()
    rng = np.random.default_rng(SEED)
    norms, masks = ee.load_masks()
    band = json.loads(BAND.read_text())
    NB = int(band["n_seconds"])
    vet = [v for v in json.loads(ee.VETTING.read_text()) if v.get("include")]
    meta = {ee.stem_of(v["name"]): v for v in vet}
    stems = sorted(meta)
    fam = {f: json.loads((ee.EVENTS_DIR / f"{f}.json").read_text()) for f in ee.FAMILIES}

    clips = {}
    signals = None
    for st in stems:
        preds = np.load(ee.PREDS_DIR / f"{st}_preds.npy")
        tc = norms.timecourses(preds, masks)
        signals = signals or list(tc)
        n = preds.shape[0]
        Z = np.stack([ee.zscore_post_warmup(np.asarray(tc[s], float)) for s in signals], 1)
        nb = min(n, NB)
        R = np.full((n, len(signals)), np.nan)
        for j, s in enumerate(signals):
            srt = band["signals"][s]["sorted"]
            for t in range(4, nb):
                R[t, j] = norms.percentile_rank(float(tc[s][t]), srt[t])
        ev = []
        feats = {}
        for f in ee.FAMILIES:
            rec = fam[f][st]
            ev += [(e["type"], float(e["t"])) for e in rec["events"]]
            for k, v in rec["per_second"].items():
                feats[k] = np.nan_to_num(np.asarray(v, float))   # NaN -> 0 (absent)
        clips[st] = {"n": n, "Z": Z, "R": R, "nb": nb, "ev": ev, "feats": feats,
                     "E": effect_series(Z, n), "ER": effect_series(R, nb),
                     "cat": meta[st]["true_category"], "fmt": meta[st]["format"],
                     "arm": meta[st]["true_arm"]}
    etypes = sorted({t for c in clips.values() for t, _ in c["ev"]})
    S = len(signals)
    out = {"n_clips": len(clips), "signals": signals, "etypes": etypes,
           "design": {"base_pred_offsets": BASE_OFF, "resp_pred_offsets": RESP_OFF,
                      "fir_lags": [int(LAGS[0]), int(LAGS[-1])], "iso_win_s": ISO_WIN}}

    # ---- 1. lag check --------------------------------------------------------------
    lag_pairs = [("words_per_s", "auditory"), ("words_per_s", "language"),
                 ("speech", "auditory"), ("motion_energy", "motion"), ("cuts", "motion"),
                 ("cuts", "gfp"), ("face_area", "social"), ("text_area", "language"),
                 ("motion_energy", "gfp")]
    lag_range = list(range(-2, 11))
    lag_out = {}
    for feat, sig in lag_pairs:
        j = signals.index(sig)
        rows = []
        for L in lag_range:
            zs = []
            for c in clips.values():
                x = c["feats"][feat]
                ts = [t for t in range(4, c["n"]) if 0 <= t - L < len(x)]
                if len(ts) < 8:
                    continue
                a = detrend(c["Z"][ts, j])
                b = detrend(x[[t - L for t in ts]])
                if a.std() == 0 or b.std() == 0:
                    continue
                zs.append(np.arctanh(np.clip(np.corrcoef(a, b)[0, 1], -0.999, 0.999)))
            zs = np.array(zs)
            rows.append({"lag": L, "mean_r": float(np.tanh(zs.mean())),
                         "se_z": float(zs.std(ddof=1) / math.sqrt(len(zs))), "n": len(zs)})
        peak = max(rows, key=lambda r: abs(r["mean_r"]))
        lag_out[f"{feat}->{sig}"] = {"peak_lag": peak["lag"], "peak_r": round(peak["mean_r"], 3),
                                     "by_lag": {r["lag"]: round(r["mean_r"], 3) for r in rows}}
    out["lag_check"] = lag_out
    print("lag check:", json.dumps({k: (v["peak_lag"], v["peak_r"]) for k, v in lag_out.items()}),
          flush=True)

    # ---- event index sets ------------------------------------------------------------
    def kept_for(et, mode, key="E"):
        res = {}
        for st, c in clips.items():
            m = c[key].shape[0]
            idx = []
            for ty, t in c["ev"]:
                if ty != et:
                    continue
                i = math.floor(t) - lo_hi(c["n"])[0]
                if not (0 <= i < m):
                    continue
                if mode != "all":
                    others = [u for ty2, u in c["ev"]
                              if (ty2 != et or (mode == "iso_all" and u != t))
                              and abs(u - t) <= ISO_WIN]
                    if others:
                        continue
                idx.append(i)
            if idx:
                res[st] = np.asarray(idx, int)
        return res

    def table(mode, key, demean, label):
        rows = []
        for et in etypes:
            kept = kept_for(et, mode, key)
            Ed = {s: clips[s][key] for s in kept}
            if len(kept) < ee.MIN_CLIPS:
                rows.append({"event": et, "skipped": True, "n_clips": len(kept),
                             "n_events": int(sum(len(v) for v in kept.values()))})
                continue
            r = run_test(Ed, kept, rng, demean=demean)
            for j, sig in enumerate(signals):
                rows.append({"event": et, "signal": sig, "effect": round(float(r["obs"][j]), 4),
                             "ci": [round(float(r["ci_lo"][j]), 4), round(float(r["ci_hi"][j]), 4)],
                             "p_orig_style": round(float(r["p_orig_style"][j]), 4),
                             "p_centred": round(float(r["p_centred"][j]), 4),
                             "null_mean": round(float(r["null_mean"][j]), 4),
                             "null_sd": round(float(r["null_sd"][j]), 4),
                             "loco": [round(float(r["loco_min"][j]), 4),
                                      round(float(r["loco_max"][j]), 4)],
                             "n_events": r["n_events"], "n_clips": r["n_clips"],
                             "_cm": r["cm"][:, j], "_clips": r["clips"]})
        tested = [x for x in rows if not x.get("skipped")]
        for x, q in zip(tested, bh([x["p_centred"] for x in tested])):
            x["q_centred"] = round(float(q), 4)
        best = sorted(tested, key=lambda x: x["p_centred"])[:6]
        print(f"[{label}] min q_centred={min(x['q_centred'] for x in tested):.3f} top:",
              [(x["event"], x["signal"], x["effect"], x["p_centred"], x["q_centred"], x["n_clips"])
               for x in best], flush=True)
        return rows

    tabs = {
        "replicate_raw": table("all", "E", False, "replicate raw z"),
        "demeaned_z": table("all", "E", True, "demeaned z"),
        "iso_other_demeaned_z": table("iso_other", "E", True, "iso_other demeaned z"),
        "iso_all_demeaned_z": table("iso_all", "E", True, "iso_all demeaned z"),
        "band_rank_raw": table("all", "ER", False, "band rank raw"),
        "band_rank_demeaned": table("all", "ER", True, "band rank demeaned"),
    }

    # ---- replication against stored results -------------------------------------------
    ref = json.loads(Path("/tribe/insight/event_effects_aggregate.json").read_text())
    if (BASE_OFF, RESP_OFF) != ((1, 3), (4, 7)):
        ref = {"effects": []}
    refd = {(r["event"], r["signal"]): r for r in ref["effects"]}
    diffs = [abs(x["effect"] - refd[(x["event"], x["signal"])]["effect_sd"])
             for x in tabs["replicate_raw"] if not x.get("skipped")
             and (x["event"], x["signal"]) in refd]
    out["replication_max_abs_diff"] = float(max(diffs)) if diffs else None

    # ---- 6. length / category dependence on demeaned per-clip effects -----------------
    dep = {}
    for x in sorted([x for x in tabs["demeaned_z"] if not x.get("skipped")],
                    key=lambda x: x["p_centred"])[:8]:
        cm, cl = x["_cm"], x["_clips"]
        ns = np.array([clips[s]["n"] for s in cl])
        rho, p_rho = stats.spearmanr(ns, cm)
        d = {"spearman_len": [round(float(rho), 3), round(float(p_rho), 4)]}
        for fld in ("cat", "fmt", "arm"):
            g = {}
            for v in sorted({clips[s][fld] for s in cl}):
                sel = np.array([clips[s][fld] == v for s in cl])
                g[v] = {"n": int(sel.sum()), "mean": round(float(cm[sel].mean()), 3)}
            groups = [cm[np.array([clips[s][fld] == v for s in cl])] for v in g if g[v]["n"] >= 3]
            kw = stats.kruskal(*groups) if len(groups) >= 2 else None
            d[fld] = {"groups": g, "kruskal_p": None if kw is None else round(float(kw.pvalue), 4)}
        d["frac_clips_positive"] = round(float((cm > 0).mean()), 3)
        d["top_clip_share"] = round(float(np.sort(np.abs(cm))[-3:].sum() / np.abs(cm).sum()), 3)
        dep[f'{x["event"]}:{x["signal"]}'] = d
    out["dependence_top8_demeaned"] = dep

    # ---- 4. joint FIR model ------------------------------------------------------------
    NL = len(LAGS)

    def lagblock(n, secs):
        """(n, NL) FIR block from integer event seconds (may repeat)."""
        B = np.zeros((n, NL))
        for li, L in enumerate(LAGS):
            tt = secs + L
            tt = tt[(tt >= 0) & (tt < n)]
            np.add.at(B[:, li], tt, 1.0)
        return B

    def featblock(c, f):
        x = c["feats"][f]
        n = c["n"]
        F = np.zeros((n, NL))
        for li, L in enumerate(LAGS):
            for t in range(n):
                if 0 <= t - L < len(x):
                    F[t, li] = x[t - L]
        return F

    # per-clip projector (drop warm-up rows, remove intercept + linear trend)
    for c in clips.values():
        m = c["n"] - 4
        tt = np.arange(m, dtype=float)
        A = np.stack([np.ones_like(tt), tt - tt.mean()], 1)
        c["P"] = np.eye(m) - A @ np.linalg.pinv(A)
        c["Yp"] = c["P"] @ c["Z"][4:]
        c["secs"] = {et: np.array([math.floor(t) for ty, t in c["ev"] if ty == et], int)
                     for et in etypes}
        c["evblk"] = {et: c["P"] @ lagblock(c["n"], c["secs"][et])[4:] for et in etypes}
        c["ftblk"] = {f: c["P"] @ featblock(c, f)[4:] for fs in CONT.values() for f in fs}

    def parts_for(et, extra, shifts=None):
        parts = []
        for i, c in enumerate(clips.values()):
            if shifts is None:
                T = c["evblk"][et]
            else:
                T = c["P"] @ lagblock(c["n"], (c["secs"][et] + shifts[i]) % c["n"])[4:]
            X = np.concatenate([T] + [c["evblk"][o] for o in etypes if o != et]
                               + [c["ftblk"][f] for f in extra], 1)
            parts.append((X.T @ X, X.T @ c["Yp"]))
        return parts

    def fit(parts, w=None):
        XtX = sum((1 if w is None else w[i]) * p[0] for i, p in enumerate(parts))
        XtY = sum((1 if w is None else w[i]) * p[1] for i, p in enumerate(parts))
        return np.linalg.lstsq(XtX, XtY, rcond=None)[0]

    def contrast(B):
        b = B[:NL]                                   # target block is always first
        li = {int(L): i for i, L in enumerate(LAGS)}
        r = b[[li[k] for k in range(RESP_OFF[0], RESP_OFF[1] + 1)]].mean(0)
        q = b[[li[k] for k in range(BASE_OFF[0], BASE_OFF[1] + 1)]].mean(0)
        return r - q, r

    fir = {}
    nclip = len(clips)
    for model in ([] if args.skip_fir else ["events_only", "events_plus_other_family_features"]):
        res = []
        for et in etypes:
            extra = [] if model == "events_only" else [
                f for fam_, fs in CONT.items() if fam_ != TYPE_FAMILY[et] for f in fs]
            parts = parts_for(et, extra)
            B0 = fit(parts)
            con, resp = contrast(B0)
            W = rng.multinomial(nclip, np.ones(nclip) / nclip, size=N_BOOT)
            bc = np.stack([contrast(fit(parts, w))[0] for w in W])
            ns = np.array([c["n"] for c in clips.values()])
            null = np.empty((N_PERM_FIR, S))
            for p in range(N_PERM_FIR):
                null[p] = contrast(fit(parts_for(et, extra, rng.integers(0, ns))))[0]
            nm = null.mean(0)
            pc = (1 + (np.abs(null - nm) >= np.abs(con - nm) - 1e-12).sum(0)) / (1 + N_PERM_FIR)
            ci = np.percentile(bc, [2.5, 97.5], 0)
            for j, sig in enumerate(signals):
                res.append({"event": et, "signal": sig, "contrast": round(float(con[j]), 4),
                            "resp_beta": round(float(resp[j]), 4),
                            "beta_by_lag": dict(zip([int(L) for L in LAGS],
                                                    [round(float(v), 4) for v in B0[:NL, j]])),
                            "ci": [round(float(ci[0, j]), 4), round(float(ci[1, j]), 4)],
                            "null_mean": round(float(nm[j]), 4),
                            "p_centred": round(float(pc[j]), 4)})
            print(f"  FIR {model} {et} done {time.time() - t0:.0f}s", flush=True)
        for x, q in zip(res, bh([x["p_centred"] for x in res])):
            x["q_centred"] = round(float(q), 4)
        best = sorted(res, key=lambda x: x["p_centred"])[:6]
        print(f"[FIR {model}] min q={min(x['q_centred'] for x in res):.3f} top:",
              [(x["event"], x["signal"], x["contrast"], x["ci"], x["p_centred"], x["q_centred"])
               for x in best], flush=True)
        fir[model] = res
    out["fir"] = fir

    for k, rows in tabs.items():
        for x in rows:
            x.pop("_cm", None)
            x.pop("_clips", None)
    out["tables"] = tabs
    out["runtime_s"] = round(time.time() - t0, 1)
    Path(args.out).write_text(json.dumps(out, indent=1))
    print("done", out["runtime_s"], "replication_max_abs_diff", out["replication_max_abs_diff"])


if __name__ == "__main__":
    main()
