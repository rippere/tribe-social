"""Stage 4 (prescribe): effects of the single-variable edits from make_edits.py on TRIBE v2 predictions.

Implements the analysis plan embedded in /tribe/edits/manifest.json (written before any edit was
scored; see make_edits.ANALYSIS_PLAN), at LAG 0. Everything here is model-internal: what TRIBE v2
predicts for an edited clip, not how viewers respond. n = 12 source clips per edit type, so every
result is small-sample; read CIs, not point estimates.

Inputs (inside the tribe container)
  manifest   /tribe/edits/manifest.json   edit id -> source stem, edit_type, params, control_id
  edit preds /tribe/edits_preds/<id>_preds.npy   (cap_k, trim3_k, ctrl_k)
  originals  /tribe/ugc_preds/<stem>_preds.npy
  band       /tribe/work_main/norm_band_ugc64_v1.json (per-second percentile band, 64 UGC clips)
  scorer     /tribe/work_main/tribe_scoring (norms.timecourses, run_and_save.quick_scores,
             HOOK_WINDOW = predicted s 0-3)

Units
  z   Each signal (gfp + 7 ROI means, norms.timecourses) is z-scored with the CONTROL clip's
      mean/SD over all predicted seconds, and the same parameters are applied to the edit and
      to the original, so differences are in within-clip SD units of the control.
  pct Percentile rank of the raw signal at each predicted second against the norm band
      (norms.diagnose), so differences are in percentile points.
  raw quick_scores summary fields (composite_raw, gfp_mean, gfp_hook, ROI means/hooks, ...).

Statistics: the clip is the unit. Per-clip values are averaged across clips; 95% percentile
bootstrap CI over clips; two-sided sign-flip permutation p (exact over all 2^n sign vectors for
n <= 16); BH-FDR within each stated family. Clips with missing preds (quarantined) are dropped
and counted.

Deviations from the embedded plan (also written into the output):
  1. Lag 0, not 4. TRIBE v2 output is stimulus-aligned: predicted second t = video second t.
  2. z parameters use all predicted seconds, not s >= 4 (s < 4 was a lag-4 warm-up exclusion).
  3. Caption primary window: pred s [a, a+L+3) (caption window + the following 3 s), baseline
     [max(0, a-3), a). The plan's [a, a+L+4) / [max(4, a-3), a) assumed lag 4; with a = 4 for
     7/12 clips its baseline was empty.
  4. trim3 aligned comparison over all trimmed seconds t >= 0 (plan: t >= 4, a warm-up
     exclusion); t >= 4 is still reported.
  5. The band file stores lag_s = 4; it is overridden to 0 in memory (the per-second reference
     values do not depend on the lag; only which seconds get ranked does).
  The plan's lag-4 window [a+4, a+L+4) is reported as a descriptive secondary.

Usage (inside the tribe container):
  python edit_effects.py --out /tribe/insight/edit_effects.json \
      --agg-out /tribe/insight/edit_effects_agg.json
The aggregate file has no per-clip rows. Neither file contains source clip stems.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

SEED = 20261117
N_BOOT = 10000
MIN_CLIPS = 3
TRIM_S = 3
HOOK_N = 3            # predicted seconds 0..2 (run_and_save.HOOK_WINDOW at lag 0)
PRIMARY_SIGNAL = "social"
PROFILE_S = 15        # per-second profiles reported up to this many seconds

DEVIATIONS = [
    "lag 0 instead of lag 4: TRIBE v2 output is stimulus-aligned (predicted s t = video s t)",
    "z-score parameters from the control over all predicted seconds (plan: s >= 4, a lag-4 "
    "warm-up exclusion)",
    "caption primary window pred s [a, a+L+3) with baseline [max(0,a-3), a) (plan: [a, a+L+4) "
    "and [max(4,a-3), a), lag-4 based; that baseline is empty for clips with a = 4)",
    "trim3 aligned comparison over all trimmed seconds t >= 0 (plan: t >= 4); t >= 4 also "
    "reported",
    "norm band file has lag_s = 4; overridden to 0 in memory so every predicted second is ranked",
    "plan's lag-4 window [a+4, a+L+4) kept as a descriptive secondary only",
]

SUMMARY_SUFFIXES = ("_mean", "_hook", "_offset")
SUMMARY_EXTRA = ("composite_raw", "vmPFC_TPJ_coupling", "pleasantness_index")


# ----------------------------------------------------------------------------- statistics
def bh(p) -> np.ndarray:
    p = np.asarray(p, float)
    q = np.full_like(p, np.nan)
    ok = np.isfinite(p)
    if not ok.any():
        return q
    pv = p[ok]
    m = len(pv)
    order = np.argsort(pv)
    ranked = pv[order] * m / np.arange(1, m + 1)
    ranked = np.minimum.accumulate(ranked[::-1])[::-1]
    out = np.empty(m)
    out[order] = np.minimum(ranked, 1.0)
    q[ok] = out
    return q


_SIGNS: dict[int, np.ndarray] = {}


def signflip_p(x: np.ndarray, rng) -> float:
    """Two-sided sign-flip permutation p for mean(x) != 0; exact for n <= 16."""
    n = len(x)
    if n <= 16:
        if n not in _SIGNS:
            k = np.arange(2 ** n)[:, None]
            _SIGNS[n] = 1.0 - 2.0 * ((k >> np.arange(n)) & 1)
        s = _SIGNS[n]
        null = np.abs((s * x).mean(1))
        return float((null >= abs(x.mean()) - 1e-12).mean())
    s = rng.choice([-1.0, 1.0], size=(20000, n))
    null = np.abs((s * x).mean(1))
    return float((1 + (null >= abs(x.mean()) - 1e-12).sum()) / 20001)


def summarize(vals, rng, n_boot: int) -> dict:
    """Across-clip summary of paired per-clip values (NaNs dropped)."""
    x = np.asarray([v for v in vals if v is not None and np.isfinite(v)], float)
    n = len(x)
    out = {"n": n}
    if n < MIN_CLIPS:
        out["note"] = f"fewer than {MIN_CLIPS} clips"
        return out
    sd = float(x.std(ddof=1))
    boot = x[rng.integers(0, n, (n_boot, n))].mean(1)
    out.update({
        "mean": round(float(x.mean()), 5),
        "median": round(float(np.median(x)), 5),
        "sd": round(sd, 5),
        "ci95": [round(float(np.percentile(boot, 2.5)), 5),
                 round(float(np.percentile(boot, 97.5)), 5)],
        "cohen_dz": round(float(x.mean() / sd), 3) if sd > 0 else None,
        "n_positive": int((x > 0).sum()),
        "p_signflip": round(signflip_p(x, rng), 5),
    })
    return out


def add_q(rows: dict, key: str = "p_signflip") -> dict:
    """BH over a family {name: summary}; writes q_bh into each summary in place."""
    names = list(rows)
    q = bh([rows[k].get(key, np.nan) for k in names])
    for k, qq in zip(names, q):
        if np.isfinite(qq):
            rows[k]["q_bh"] = round(float(qq), 5)
    return rows


# ----------------------------------------------------------------------------- signals
def wmean(x: np.ndarray, lo: int, hi: int) -> float:
    lo, hi = max(lo, 0), min(hi, len(x))
    if hi <= lo:
        return float("nan")
    seg = x[lo:hi]
    seg = seg[np.isfinite(seg)]
    return float(seg.mean()) if len(seg) else float("nan")


class Clip:
    """Timecourses of one prediction array, in raw, z (control parameters) and band ranks."""

    def __init__(self, preds: np.ndarray, ctx):
        self.preds = preds
        self.n = preds.shape[0]
        self.raw = ctx.norms.timecourses(preds, ctx.masks)
        ranks = ctx.norms.diagnose(self.raw, ctx.band)["ranks"]
        self.pct = {s: np.array([np.nan if v is None else v for v in r], float)
                    for s, r in ranks.items()}
        self.qs = ctx.quick_scores(preds)
        self.z: dict[str, np.ndarray] = {}

    def zscore_with(self, params: dict):
        self.z = {s: (self.raw[s] - mu) / sd for s, (mu, sd) in params.items()}


def zparams(c: Clip) -> dict:
    out = {}
    for s, v in c.raw.items():
        sd = float(v.std())
        out[s] = (float(v.mean()), sd if sd > 0 else 1.0)
    return out


def summary_fields(qs: dict) -> list[str]:
    return [k for k in qs if k.endswith(SUMMARY_SUFFIXES) or k in SUMMARY_EXTRA]


# ----------------------------------------------------------------------------- context
class Ctx:
    def __init__(self, args):
        sys.path.insert(0, args.work_main)
        from tribe_scoring import norms, run_and_save  # noqa: E402
        self.norms = norms
        self.masks = run_and_save._BATCH_MASKS
        self.quick_scores = run_and_save.quick_scores
        hw = run_and_save.HOOK_WINDOW
        if (hw.start, hw.stop) != (0, HOOK_N):
            raise SystemExit(f"scorer HOOK_WINDOW is {hw}, expected slice(0, {HOOK_N}) (lag 0); "
                             "copy main's packages/tribe_scoring/run_and_save.py into work_main")
        band = norms.load_band(Path(args.band))
        self.band_lag_file = band["lag_s"]
        band["lag_s"] = 0
        self.band = band
        self.band_name = band["name"]


def load(path: Path, ctx) -> Clip | None:
    return Clip(np.load(path), ctx) if path.exists() else None


# ----------------------------------------------------------------------------- analyses
def caption_windows(a: int, L: int) -> dict[str, tuple[int, int]]:
    return {"primary_win_plus3": (a, a + L + 3),
            "win_only": (a, a + L),
            "after3": (a + L, a + L + 3),
            "plan_lag4_win": (a + 4, a + L + 4)}


def window_D(diff: np.ndarray, a: int, lo: int, hi: int) -> float:
    """mean(diff) over [lo, hi) minus mean(diff) over the baseline [max(0, a-3), a)."""
    return wmean(diff, lo, hi) - wmean(diff, max(0, a - 3), a)


def noise_floor(units: list[dict], signals, fields, rng, n_boot) -> dict:
    """Control (re-encode only) vs original: per signal per second, and summary fields."""
    out = {"what": "control (same ffmpeg pipeline, no edit) minus original preds; re-encode noise",
           "n_clips": len(units), "per_signal": {}, "summary_fields": {}}
    for s in signals:
        dz_all, dp_all, per_clip, prof = [], [], [], [[] for _ in range(PROFILE_S)]
        for u in units:
            c, o = u["ctrl"], u["orig"]
            m = min(c.n, o.n)
            dz = c.z[s][:m] - o.z[s][:m]
            dp = c.pct[s][:m] - o.pct[s][:m]
            dz_all.extend(np.abs(dz))
            dp_all.extend(np.abs(dp[np.isfinite(dp)]))
            per_clip.append(float(np.abs(dz).mean()))
            for t in range(min(m, PROFILE_S)):
                prof[t].append(abs(dz[t]))
        dz_all, dp_all = np.asarray(dz_all), np.asarray(dp_all)
        out["per_signal"][s] = {
            "abs_dz_per_second": {"mean": round(float(dz_all.mean()), 5),
                                  "p95": round(float(np.percentile(dz_all, 95)), 5),
                                  "max": round(float(dz_all.max()), 5),
                                  "n_clip_seconds": int(len(dz_all))},
            "abs_dpct_per_second": {"mean": round(float(dp_all.mean()), 3),
                                    "p95": round(float(np.percentile(dp_all, 95)), 3),
                                    "max": round(float(dp_all.max()), 3)} if len(dp_all) else None,
            "clip_mean_abs_dz": summarize(per_clip, rng, n_boot),
            "abs_dz_profile_by_second": [round(float(np.mean(p)), 5) if p else None
                                         for p in prof],
        }
    for f in fields:
        d = [u["ctrl"].qs[f] - u["orig"].qs[f] for u in units]
        sd_between = float(np.std([u["ctrl"].qs[f] for u in units], ddof=1))
        row = summarize(d, rng, n_boot)
        row["max_abs"] = round(float(np.max(np.abs(d))), 6)
        row["between_clip_sd_ctrl"] = round(sd_between, 6)
        out["summary_fields"][f] = row
    return out


def summary_deltas(units, key, fields, rng, n_boot) -> dict:
    """Whole-clip quick_scores deltas edit - ctrl, with the ctrl - orig noise alongside."""
    out = {}
    for f in fields:
        d = [u[key].qs[f] - u["ctrl"].qs[f] for u in units]
        nz = [u["ctrl"].qs[f] - u["orig"].qs[f] for u in units]
        sd_between = float(np.std([u["ctrl"].qs[f] for u in units], ddof=1)) if len(units) > 1 else 0
        row = summarize(d, rng, n_boot)
        if "mean" in row and sd_between > 0:
            row["mean_in_between_clip_sd"] = round(row["mean"] / sd_between, 4)
        row["noise_mean_abs"] = round(float(np.mean(np.abs(nz))), 6) if nz else None
        row["excess_over_noise_abs"] = summarize(
            [abs(a) - abs(b) for a, b in zip(d, nz)], rng, n_boot)
        row["per_clip"] = [round(x, 6) for x in d]
        out[f] = row
    add_q(out)
    return out


def caption_analysis(units, signals, fields, rng, n_boot) -> dict:
    res = {"n_clips": len(units), "edit_ids": [u["id"] for u in units],
           "windows_pred_s": "a = caption start (video s = pred s at lag 0), L = caption length",
           "units": {}}
    per_clip = {}
    for unit_name in ("z", "pct"):
        tests = {}
        for s in signals:
            for wname in caption_windows(4, 4):
                D_edit, D_noise = [], []
                for u in units:
                    e, c, o = u["cap"], u["ctrl"], u["orig"]
                    a, L = u["a"], u["L"]
                    lo, hi = caption_windows(a, L)[wname]
                    ve, vc, vo = (getattr(x, unit_name)[s] for x in (e, c, o))
                    m = min(len(ve), len(vc))
                    D_edit.append(window_D(ve[:m] - vc[:m], a, lo, hi))
                    m2 = min(len(vc), len(vo))
                    D_noise.append(window_D(vc[:m2] - vo[:m2], a, lo, hi))
                key = f"{s}:{wname}"
                row = summarize(D_edit, rng, n_boot)
                row["noise_floor"] = summarize(D_noise, rng, n_boot)
                row["excess_abs_over_noise"] = summarize(
                    [abs(x) - abs(y) for x, y in zip(D_edit, D_noise)], rng, n_boot)
                row["per_clip"] = [None if not np.isfinite(x) else round(x, 5) for x in D_edit]
                tests[key] = row
                per_clip.setdefault(unit_name, {})[key] = row["per_clip"]
        primary_key = f"{PRIMARY_SIGNAL}:primary_win_plus3"
        secondary = {k: v for k, v in tests.items() if k != primary_key}
        add_q(secondary)
        other7 = {k: tests[k] for k in tests
                  if k.endswith(":primary_win_plus3") and k != primary_key}
        q7 = bh([other7[k].get("p_signflip", np.nan) for k in other7])
        for k, q in zip(other7, q7):
            if np.isfinite(q):
                tests[k]["q_bh_other7_primary_window"] = round(float(q), 5)
        res["units"][unit_name] = {"primary": {primary_key: tests[primary_key]},
                                   "tests": tests,
                                   "families": {"secondary_bh": "all signal x window except the "
                                                "primary (q_bh)", "other7": "7 non-social signals "
                                                "at the primary window (q_bh_other7_primary_window)"}}
    # caption_source split, descriptive only
    split = {}
    for src in ("transcript", "fixed"):
        idx = [i for i, u in enumerate(units) if u["caption_source"] == src]
        if not idx:
            continue
        row = {}
        for unit_name in ("z", "pct"):
            for s in signals:
                key = f"{s}:primary_win_plus3"
                vals = [res["units"][unit_name]["tests"][key]["per_clip"][i] for i in idx]
                vals = [v for v in vals if v is not None]
                row[f"{unit_name}:{key}"] = {"n": len(vals),
                                             "mean": round(float(np.mean(vals)), 5) if vals else None}
        split[src] = row
    res["caption_source_split_descriptive"] = split
    res["summary_deltas_edit_minus_ctrl"] = summary_deltas(units, "cap", fields, rng, n_boot)
    return res


def trim_analysis(units, signals, fields, rng, n_boot) -> dict:
    res = {"n_clips": len(units), "edit_ids": [u["id"] for u in units],
           "aligned": "trimmed pred s t vs control pred s t+3 (same video content); z units with "
                      "control parameters; noise = control vs original at s t+3",
           "context_dependence": {}, "hook": {}}
    for s in signals:
        rows = {k: [] for k in ("mad_all", "mad_t0_2", "mad_t3plus", "mad_t4plus", "signed_all",
                                "noise_mad_all", "noise_mad_t0_2", "excess_all", "excess_t0_2",
                                "early_minus_late")}
        prof = [[] for _ in range(PROFILE_S)]
        for u in units:
            tr, c, o = u["trim"], u["ctrl"], u["orig"]
            m = min(tr.n, c.n - TRIM_S, o.n - TRIM_S)
            dz = tr.z[s][:m] - c.z[s][TRIM_S:TRIM_S + m]
            nz = c.z[s][TRIM_S:TRIM_S + m] - o.z[s][TRIM_S:TRIM_S + m]
            ad, an = np.abs(dz), np.abs(nz)
            rows["mad_all"].append(float(ad.mean()))
            rows["mad_t0_2"].append(float(ad[:3].mean()))
            rows["mad_t3plus"].append(float(ad[3:].mean()) if m > 3 else np.nan)
            rows["mad_t4plus"].append(float(ad[4:].mean()) if m > 4 else np.nan)
            rows["signed_all"].append(float(dz.mean()))
            rows["noise_mad_all"].append(float(an.mean()))
            rows["noise_mad_t0_2"].append(float(an[:3].mean()))
            rows["excess_all"].append(float(ad.mean() - an.mean()))
            rows["excess_t0_2"].append(float(ad[:3].mean() - an[:3].mean()))
            rows["early_minus_late"].append(float(ad[:3].mean() - ad[3:].mean()) if m > 3 else np.nan)
            for t in range(min(m, PROFILE_S)):
                prof[t].append(ad[t])
        out = {k: summarize(v, rng, n_boot) for k, v in rows.items()}
        out["abs_dz_profile_by_trimmed_second"] = [round(float(np.mean(p)), 5) if p else None
                                                   for p in prof]
        out["per_clip_mad_all"] = [round(x, 5) for x in rows["mad_all"]]
        res["context_dependence"][s] = out
    add_q({s: res["context_dependence"][s]["excess_all"] for s in signals})

    # new opening hook (trimmed s 0-2) vs original hook (control s 0-2)
    for s in signals:
        d_z, d_p, n_z, same_content = [], [], [], []
        for u in units:
            tr, c, o = u["trim"], u["ctrl"], u["orig"]
            d_z.append(wmean(tr.z[s], 0, HOOK_N) - wmean(c.z[s], 0, HOOK_N))
            d_p.append(wmean(tr.pct[s], 0, HOOK_N) - wmean(c.pct[s], 0, HOOK_N))
            n_z.append(wmean(c.z[s], 0, HOOK_N) - wmean(o.z[s], 0, HOOK_N))
            same_content.append(wmean(tr.z[s], 0, HOOK_N) - wmean(c.z[s], TRIM_S, TRIM_S + HOOK_N))
        row = {"hook_delta_z": summarize(d_z, rng, n_boot),
               "hook_delta_pct": summarize(d_p, rng, n_boot),
               "noise_hook_delta_z": summarize(n_z, rng, n_boot),
               "excess_abs_over_noise_z": summarize([abs(a) - abs(b) for a, b in zip(d_z, n_z)],
                                                    rng, n_boot),
               "same_content_context_delta_z": summarize(same_content, rng, n_boot),
               "per_clip_hook_delta_z": [round(x, 5) for x in d_z],
               "per_clip_hook_delta_pct": [round(x, 3) for x in d_p]}
        res["hook"][s] = row
    add_q({s: res["hook"][s]["hook_delta_z"] for s in signals})
    add_q({f"{s}_pct": res["hook"][s]["hook_delta_pct"] for s in signals})
    res["summary_deltas_edit_minus_ctrl"] = summary_deltas(units, "trim", fields, rng, n_boot)
    return res


# ----------------------------------------------------------------------------- driver
def strip_per_clip(obj):
    if isinstance(obj, dict):
        return {k: strip_per_clip(v) for k, v in obj.items()
                if not k.startswith("per_clip") and k != "edit_ids"}
    if isinstance(obj, list):
        return [strip_per_clip(v) for v in obj]
    return obj


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", default="/tribe/edits/manifest.json")
    ap.add_argument("--edits-preds", default="/tribe/edits_preds")
    ap.add_argument("--orig-preds", default="/tribe/ugc_preds")
    ap.add_argument("--band", default="/tribe/work_main/norm_band_ugc64_v1.json")
    ap.add_argument("--work-main", default="/tribe/work_main")
    ap.add_argument("--out", required=True)
    ap.add_argument("--agg-out", required=True)
    ap.add_argument("--n-boot", type=int, default=N_BOOT)
    ap.add_argument("--require-complete", action="store_true",
                    help="exit non-zero if any manifest edit lacks preds")
    args = ap.parse_args()

    t0 = time.time()
    rng = np.random.default_rng(SEED)
    ctx = Ctx(args)
    man = json.loads(Path(args.manifest).read_text())
    edits = man["edits"]
    ep, op = Path(args.edits_preds), Path(args.orig_preds)

    missing = sorted(k for k in edits if not (ep / f"{k}_preds.npy").exists())
    if missing and args.require_complete:
        raise SystemExit(f"{len(missing)} edits lack preds: {missing}")

    ctrls = {}
    for k, e in sorted(edits.items()):
        if e["edit_type"] != "control":
            continue
        c = load(ep / f"{k}_preds.npy", ctx)
        o = load(op / f"{e['source_stem']}_preds.npy", ctx)
        if c is None or o is None:
            continue
        params = zparams(c)
        c.zscore_with(params)
        o.zscore_with(params)
        ctrls[k] = {"ctrl": c, "orig": o, "params": params}

    signals = list(next(iter(ctrls.values()))["ctrl"].raw) if ctrls else []
    cap_units, trim_units = [], []
    for k, e in sorted(edits.items()):
        if e["edit_type"] == "control" or e["control_id"] not in ctrls:
            continue
        x = load(ep / f"{k}_preds.npy", ctx)
        if x is None:
            continue
        cu = ctrls[e["control_id"]]
        x.zscore_with(cu["params"])
        if e["edit_type"] == "caption":
            a, b = e["params"]["window_video_s"]
            cap_units.append({"id": k, "cap": x, "ctrl": cu["ctrl"], "orig": cu["orig"],
                              "a": int(a), "L": int(b - a),
                              "caption_source": e["params"]["caption_source"]})
        elif e["edit_type"] == "trim_cold_open":
            trim_units.append({"id": k, "trim": x, "ctrl": cu["ctrl"], "orig": cu["orig"]})

    n_type = {t: sum(e["edit_type"] == t for e in edits.values())
              for t in ("control", "caption", "trim_cold_open")}
    out = {
        "meta": {
            "script": "research/insight/edit_effects.py",
            "scope": "model-internal TRIBE v2 predictions for edited clips; not viewer behaviour",
            "lag_s": 0, "band": ctx.band_name, "band_file_lag_s": ctx.band_lag_file,
            "seed": SEED, "n_boot": args.n_boot, "signals": signals,
            "primary": f"caption, {PRIMARY_SIGNAL}, z units, window pred s [a, a+L+3) minus "
                       "baseline [max(0,a-3), a), edit - control",
            "manifest_plan": man.get("analysis_plan"),
            "deviations_from_plan": DEVIATIONS,
            "n_in_manifest": n_type,
            "n_used": {"control_pairs": len(ctrls), "caption": len(cap_units),
                       "trim_cold_open": len(trim_units)},
            "missing_preds": missing,
            "partial": bool(missing),
            "small_n_warning": "n <= 12 clips per edit type: wide CIs, low power; "
                               "exploratory follow-up, not confirmatory",
        },
    }
    fields = summary_fields(next(iter(ctrls.values()))["ctrl"].qs) if ctrls else []
    if len(ctrls) >= MIN_CLIPS:
        out["noise_floor"] = noise_floor(list(ctrls.values()), signals, fields, rng, args.n_boot)
    if len(cap_units) >= MIN_CLIPS:
        out["caption"] = caption_analysis(cap_units, signals, fields, rng, args.n_boot)
    if len(trim_units) >= MIN_CLIPS:
        out["trim3"] = trim_analysis(trim_units, signals, fields, rng, args.n_boot)
    out["meta"]["runtime_s"] = round(time.time() - t0, 1)

    Path(args.out).write_text(json.dumps(out, indent=1))
    Path(args.agg_out).write_text(json.dumps(strip_per_clip(out), indent=1))

    m = out["meta"]
    print(f"used: ctrl {len(ctrls)}  caption {len(cap_units)}  trim3 {len(trim_units)}  "
          f"missing {len(missing)}  ({m['runtime_s']} s)")
    if "caption" in out:
        p = out["caption"]["units"]["z"]["primary"]
        for k, v in p.items():
            print(f"caption primary {k}: {v.get('mean')} CI {v.get('ci95')} p {v.get('p_signflip')}")
    print(f"wrote {args.out} and {args.agg_out}")


if __name__ == "__main__":
    main()
