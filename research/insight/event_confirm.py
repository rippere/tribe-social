"""Pre-registered event-locked test of TRIBE v2 responses: discovery and confirmation.

Design (fixed in research/insight/PREREG-EVENTS.md before any holdout clip was sourced):
  * Signals: norms.timecourses(preds, run_and_save._BATCH_MASKS) -> gfp + 7 ROI means.
    Each signal is z-scored within clip over ALL predicted seconds (no warm-up exclusion),
    so it is also clip-demeaned.
  * Lag 0 (TRIBE v2 predictions are already stimulus-aligned). Event at video time t ->
    s = floor(t). Kept if s >= 3 and s + 3 <= n - 1 (n = predicted seconds).
      baseline = mean z over predicted s-3..s-1
      response = mean z over predicted s..s+3
      effect   = response - baseline (within-clip SD units)
  * Per event type x signal: mean within clip, then mean across clips (clip = unit).
    A test runs only if >= MIN_CLIPS clips have a kept event of that type.
  * Null: each clip's kept event seconds are circularly shifted by one random integer
    offset within that clip's valid range [3, n-4] (same count and spacing); the same
    offset is used for all signals within a shuffle; N_PERM shuffles. The null is CENTRED:
    mu = mean of the null; centred effect = obs - mu.
      two-sided p = (1 + #{|null - mu| >= |obs - mu|}) / (1 + N_PERM)
      one-sided p = (1 + #{d*(null - mu) >= d*(obs - mu)}) / (1 + N_PERM), d = discovery sign
  * 95% CI: percentile bootstrap over clips (N_BOOT), reported for the raw effect and the
    centred effect (bootstrap mean - mu).
  * Benjamini-Hochberg q.

Modes (run inside the `tribe` container on the Spark):
  --discover   64 discovery clips. BH over all tests; hypotheses = tests with q < 0.10,
               direction = sign of the centred effect. Writes the hypothesis file.
  --confirm    holdout clips. Tests the hypothesis set one-sided in the discovery direction,
               BH over the set; success = q < 0.05 AND same sign of centred effect. Also
               reports every test descriptively (two-sided, BH over all).
  --extract F  run extractor family F (cuts|faces|text|speech) on the holdout with the
               discovery extractors' exact code and parameters, only the paths changed.
               speech needs the whisperx .tsv/.wav that scoring writes next to each clip.

Aggregate outputs carry no clip identifiers; per-clip outputs (--full-out) stay on the Spark.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import multiprocessing
import shutil
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
WORK_MAIN = "/tribe/work_main"
FAMILIES = ["speech", "cuts", "faces", "text"]

LAG = 0
BASE = (-3, -1)        # inclusive offsets from s
RESP = (0, 3)          # inclusive offsets from s
MIN_S = 3              # s - 3 >= 0
TAIL = 3               # s + 3 <= n - 1
MIN_CLIPS = 10
N_BOOT = 5000
N_PERM = 5000
Q_DISCOVER = 0.10
Q_CONFIRM = 0.05
SEED = 20261118
POSITIVE_CONTROLS = ["speech_onset:auditory", "pause_start:auditory"]

DISCOVERY = {
    "preds": "/tribe/ugc_preds",
    "vetting": "/tribe/work/vetting.json",
    "events": "/tribe/insight/events",
}
HOLDOUT = {
    "clips": "/tribe/ugc_holdout",
    "preds": "/tribe/ugc_holdout_preds",
    "vetting": "/tribe/ugc_holdout/vetting.json",
    "events": "/tribe/insight/events_holdout",
    "work": "/tribe/insight/holdout_work",
}


# ------------------------------------------------------------------------ helpers
def bh(pvals) -> np.ndarray:
    p = np.asarray(pvals, float)
    m = len(p)
    if m == 0:
        return p
    order = np.argsort(p)
    q = np.minimum.accumulate((p[order] * m / np.arange(1, m + 1))[::-1])[::-1]
    out = np.empty(m)
    out[order] = np.minimum(q, 1.0)
    return out


def stem_of(name: str) -> str:
    return name[:-4] if name.endswith(".mp4") else name


def yt_id(stem: str) -> str:
    # stems are <category>_<arm>_<id>; ids may contain "_"
    return stem.split("_", 2)[2]


def zscore(x: np.ndarray) -> np.ndarray:
    sd = x.std()
    return (x - x.mean()) / (sd if sd > 0 else 1.0)


def load_clips(preds_dir: Path, vetting: Path, events_dir: Path):
    sys.path.insert(0, WORK_MAIN)
    from tribe_scoring import norms, run_and_save  # noqa: E402

    vet = json.loads(vetting.read_text())
    stems = sorted(stem_of(v["name"]) for v in vet if v.get("include"))
    fam = {f: json.loads((events_dir / f"{f}.json").read_text()) for f in FAMILIES}
    clips, missing, signals = {}, [], None
    for st in stems:
        pf = preds_dir / f"{st}_preds.npy"
        if not pf.exists() or any(st not in fam[f] for f in FAMILIES):
            missing.append(st)
            continue
        preds = np.load(pf)
        tc = norms.timecourses(preds, run_and_save._BATCH_MASKS)
        if signals is None:
            signals = list(tc)
        n = preds.shape[0]
        Z = np.stack([zscore(np.asarray(tc[s], float)) for s in signals], 1)   # (n, S)
        lo, hi = MIN_S, n - 1 - TAIL
        m = max(hi - lo + 1, 0)
        if m:
            sec = np.arange(lo, hi + 1) + LAG
            base = np.mean([Z[sec + k] for k in range(BASE[0], BASE[1] + 1)], 0)
            resp = np.mean([Z[sec + k] for k in range(RESP[0], RESP[1] + 1)], 0)
            E = resp - base
        else:
            E = np.zeros((0, len(signals)))
        ev = [(e["type"], float(e["t"])) for f in FAMILIES for e in fam[f][st]["events"]]
        clips[st] = {"n": n, "lo": lo, "m": m, "E": E, "events": ev}
    return clips, signals, stems, missing


def run_tests(clips, signals, rng, etypes=None):
    """All event-type x signal tests. Returns rows (aggregate) and per-clip effects."""
    if etypes is None:
        etypes = sorted({t for c in clips.values() for t, _ in c["events"]})
    S = len(signals)
    rows, skipped, per_clip, n_events_all = [], [], {}, {}
    for et in etypes:
        kept = {}
        n_all = 0
        for st, c in clips.items():
            idx = [math.floor(t) - c["lo"] for ty, t in c["events"] if ty == et]
            n_all += len(idx)
            idx = [i for i in idx if 0 <= i < c["m"]]
            if idx:
                kept[st] = np.asarray(idx, int)
        n_events_all[et] = n_all
        cl = sorted(kept)
        n_ev = int(sum(len(kept[s]) for s in cl))
        if len(cl) < MIN_CLIPS:
            skipped.append({"event": et, "n_clips": len(cl), "n_events": n_ev,
                            "reason": f"n_clips < {MIN_CLIPS}"})
            continue
        C = len(cl)
        cm = np.stack([clips[s]["E"][kept[s]].mean(0) for s in cl])           # (C, S)
        obs = cm.mean(0)
        null = np.zeros((N_PERM, S))
        for s in cl:
            c = clips[s]
            ks = rng.integers(0, c["m"], N_PERM)
            null += c["E"][(kept[s][None, :] + ks[:, None]) % c["m"]].mean(1)
        null /= C
        mu = null.mean(0)
        boot = cm[rng.integers(0, C, (N_BOOT, C))].mean(1)                     # (B, S)
        lo_r, hi_r = np.percentile(boot, [2.5, 97.5], 0)
        lo_c, hi_c = np.percentile(boot - mu, [2.5, 97.5], 0)
        p2 = (1 + (np.abs(null - mu) >= np.abs(obs - mu) - 1e-12).sum(0)) / (1 + N_PERM)
        for j, sig in enumerate(signals):
            rows.append({
                "test": f"{et}:{sig}", "event": et, "signal": sig,
                "n_clips": C, "n_events": n_ev,
                "effect_sd": float(obs[j]), "ci_lo": float(lo_r[j]), "ci_hi": float(hi_r[j]),
                "null_mean": float(mu[j]), "null_sd": float(null[:, j].std()),
                "effect_centred": float(obs[j] - mu[j]),
                "ci_centred_lo": float(lo_c[j]), "ci_centred_hi": float(hi_c[j]),
                "p_two_sided": float(p2[j]),
                "frac_clips_positive_centred": float((cm[:, j] - mu[j] > 0).mean()),
                "_null_centred": null[:, j] - mu[j],
            })
        per_clip[et] = {s: {"n_events": int(len(kept[s])),
                            **{sig: float(cm[i, j]) for j, sig in enumerate(signals)}}
                        for i, s in enumerate(cl)}
    q = bh([r["p_two_sided"] for r in rows])
    for r, qq in zip(rows, q):
        r["q_two_sided_all"] = float(qq)
    return rows, skipped, per_clip, n_events_all


def strip(rows):
    return [{k: v for k, v in r.items() if not k.startswith("_")} for r in rows]


def design_meta():
    return {
        "lag_s": LAG, "baseline_offsets": list(range(BASE[0], BASE[1] + 1)),
        "response_offsets": list(range(RESP[0], RESP[1] + 1)),
        "keep": "s = floor(t); s >= 3 and s + 3 <= n - 1",
        "zscore": "within clip over all predicted seconds (no warm-up exclusion)",
        "aggregation": "mean within clip, then across clips",
        "ci": f"percentile bootstrap over clips, {N_BOOT}",
        "null": f"per-clip circular shift of kept event seconds within [3, n-4], {N_PERM} "
                "shuffles, same offset across signals; centred on null mean",
        "min_clips": MIN_CLIPS, "seed": SEED,
    }


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


# ------------------------------------------------------------------------ modes
def discover(a):
    t0 = time.time()
    rng = np.random.default_rng(SEED)
    clips, signals, stems, missing = load_clips(Path(a.preds or DISCOVERY["preds"]),
                                                Path(a.vetting or DISCOVERY["vetting"]),
                                                Path(a.events or DISCOVERY["events"]))
    if missing:
        raise SystemExit(f"{len(missing)} discovery clips missing preds/events")
    rows, skipped, per_clip, n_ev_all = run_tests(clips, signals, rng)
    hyps = [{"test": r["test"], "event": r["event"], "signal": r["signal"],
             "direction": int(np.sign(r["effect_centred"])),
             "discovery_effect_centred": round(r["effect_centred"], 4),
             "discovery_ci_centred": [round(r["ci_centred_lo"], 4), round(r["ci_centred_hi"], 4)],
             "discovery_effect_sd": round(r["effect_sd"], 4),
             "discovery_p_two_sided": r["p_two_sided"],
             "discovery_q": round(r["q_two_sided_all"], 4),
             "discovery_n_clips": r["n_clips"], "discovery_n_events": r["n_events"]}
            for r in rows if r["q_two_sided_all"] < Q_DISCOVER]
    agg = {"mode": "discover", "design": design_meta(), "signals": signals,
           "n_clips": len(clips), "n_tests": len(rows), "q_threshold": Q_DISCOVER,
           "n_events_by_type_all": n_ev_all, "skipped": skipped,
           "effects": strip(rows), "hypotheses": hyps,
           "runtime_s": round(time.time() - t0, 1)}
    hyp_file = {"source": "event_confirm.py --discover on the 64 discovery clips",
                "design": design_meta(), "signals": signals, "n_tests_discovery": len(rows),
                "q_discover": Q_DISCOVER, "q_confirm": Q_CONFIRM,
                "positive_controls": POSITIVE_CONTROLS, "hypotheses": hyps}
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(agg, indent=1))
    Path(a.hyp_out).write_text(json.dumps(hyp_file, indent=1))
    if a.full_out:
        Path(a.full_out).write_text(json.dumps({**agg, "per_clip_effects": per_clip}))
    print(json.dumps({"n_clips": len(clips), "n_tests": len(rows), "n_hypotheses": len(hyps),
                      "hypotheses": [(h["test"], h["discovery_effect_centred"], h["discovery_q"])
                                     for h in hyps], "runtime_s": agg["runtime_s"]}, indent=1))


def confirm(a):
    t0 = time.time()
    rng = np.random.default_rng(SEED)
    hyp_path = Path(a.hypotheses)
    H = json.loads(hyp_path.read_text())
    hyps = H["hypotheses"]
    clips, signals, stems, missing = load_clips(Path(a.preds or HOLDOUT["preds"]),
                                                Path(a.vetting or HOLDOUT["vetting"]),
                                                Path(a.events or HOLDOUT["events"]))
    if signals != H["signals"]:
        raise SystemExit("signal set differs from the pre-registered one")
    # holdout must not share a video with the discovery set
    disc = json.loads(Path(DISCOVERY["vetting"]).read_text())
    disc_ids = {yt_id(stem_of(v["name"])) for v in disc}
    overlap = sorted({yt_id(s) for s in clips} & disc_ids)
    if overlap:
        raise SystemExit(f"{len(overlap)} holdout clips overlap the discovery set")
    rows, skipped, per_clip, n_ev_all = run_tests(clips, signals, rng)
    by = {r["test"]: r for r in rows}

    conf = []
    for h in hyps:
        r = by.get(h["test"])
        if r is None:
            conf.append({**h, "ran": False, "reason": "test did not run (n_clips < "
                         f"{MIN_CLIPS})", "p_one_sided": 1.0})
            continue
        d = h["direction"]
        obs_c = r["effect_centred"]
        p1 = (1 + (d * r["_null_centred"] >= d * obs_c - 1e-12).sum()) / (1 + N_PERM)
        conf.append({**h, "ran": True, "holdout_effect_centred": obs_c,
                     "holdout_ci_centred": [r["ci_centred_lo"], r["ci_centred_hi"]],
                     "holdout_effect_sd": r["effect_sd"],
                     "holdout_n_clips": r["n_clips"], "holdout_n_events": r["n_events"],
                     "same_sign": bool(np.sign(obs_c) == d), "p_one_sided": float(p1)})
    q = bh([c["p_one_sided"] for c in conf])
    for c, qq in zip(conf, q):
        c["q_confirm"] = float(qq)
        c["replicated"] = bool(c.get("ran") and qq < Q_CONFIRM and c["same_sign"])
    ctrl = {t: next((c["replicated"] for c in conf if c["test"] == t), None)
            for t in POSITIVE_CONTROLS}
    vet = json.loads(Path(a.vetting or HOLDOUT["vetting"]).read_text())
    out = {"mode": "confirm", "design": design_meta(), "signals": signals,
           "hypotheses_sha256": sha256(hyp_path),
           "n_vetted": len(vet), "n_included": len(stems), "n_scored_used": len(clips),
           "n_included_missing_preds_or_events": len(missing),
           "q_confirm": Q_CONFIRM, "n_hypotheses": len(hyps),
           "n_replicated": int(sum(c["replicated"] for c in conf)),
           "positive_controls_replicated": ctrl,
           "confirmatory": conf, "n_events_by_type_all": n_ev_all, "skipped": skipped,
           "descriptive_all_tests": strip(rows), "runtime_s": round(time.time() - t0, 1)}
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(out, indent=1))
    if a.full_out:
        Path(a.full_out).write_text(json.dumps({**out, "per_clip_effects": per_clip}))
    print(json.dumps({k: out[k] for k in ("n_included", "n_scored_used", "n_hypotheses",
                                          "n_replicated", "positive_controls_replicated")}))
    for c in conf:
        print(f'{c["test"]:<28s} disc {c["discovery_effect_centred"]:+.3f} '
              f'hold {c.get("holdout_effect_centred", float("nan")):+.3f} '
              f'p1 {c["p_one_sided"]:.4f} q {c["q_confirm"]:.4f} rep={c["replicated"]}')


def _load_module(name: str):
    spec = importlib.util.spec_from_file_location(name, HERE / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod          # Pool pickles worker functions by module name
    spec.loader.exec_module(mod)
    return mod


def extract(a):
    """Run one discovery extractor on the holdout: same code and parameters, paths only."""
    multiprocessing.set_start_method("fork", force=True)   # workers inherit patched globals
    clips, vet = a.clips or HOLDOUT["clips"], a.vetting or HOLDOUT["vetting"]
    ev_dir = Path(a.events or HOLDOUT["events"])
    work = Path(HOLDOUT["work"])
    ev_dir.mkdir(parents=True, exist_ok=True)
    work.mkdir(parents=True, exist_ok=True)
    f = a.extract
    w = str(a.workers)
    if f == "cuts":
        m = _load_module("extract_cuts")
        m.UGC_DIR, m.VETTING = clips, vet
        m.OUT_JSON, m.CACHE_DIR = str(ev_dir / "cuts.json"), str(work / "cuts_cache")
        sys.argv = ["extract_cuts", "--workers", w]
        m.main()
    elif f == "faces":
        m = _load_module("extract_faces")
        sys.argv = ["extract_faces", "--vetting", vet, "--clips", clips,
                    "--out", str(ev_dir / "faces.json"),
                    "--raw-out", str(work / "faces_samples.json"), "--workers", w]
        rc = m.main()
        if rc:
            raise SystemExit(rc)
    elif f == "text":
        m = _load_module("extract_text")
        m.UGC_DIR, m.VETTING, m.OUT_ROOT = Path(clips), Path(vet), work / "text"
        sys.argv = ["extract_text", "--workers", w]
        try:
            m.main()
        finally:
            src = work / "text" / "events" / "text.json"
            if src.exists():
                shutil.copy(src, ev_dir / "text.json")
    elif f == "speech":
        m = _load_module("extract_speech")
        m.UGC_DIR, m.VETTING = clips, vet
        sys.argv = ["extract_speech", "--workers", w, "--out-dir", str(ev_dir)]
        m.main()
    else:
        raise SystemExit(f"unknown family {f}")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--discover", action="store_true")
    g.add_argument("--confirm", action="store_true")
    g.add_argument("--extract", choices=FAMILIES)
    ap.add_argument("--preds")
    ap.add_argument("--vetting")
    ap.add_argument("--events")
    ap.add_argument("--clips")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--hypotheses", default="/tribe/insight/confirm/hypotheses.json")
    ap.add_argument("--hyp-out", default="/tribe/insight/confirm/hypotheses.json")
    ap.add_argument("--out", default=None)
    ap.add_argument("--full-out", default=None)
    a = ap.parse_args()
    if a.discover:
        a.out = a.out or "/tribe/insight/confirm/discovery_aggregate.json"
        discover(a)
    elif a.confirm:
        a.out = a.out or "/tribe/insight/confirm_results.json"
        confirm(a)
    else:
        extract(a)


if __name__ == "__main__":
    main()
