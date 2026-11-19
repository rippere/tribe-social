"""Group-effect analysis for the UGC baseline batch. Follows PLAN.md (fixed before scoring).

Usage (inside the Spark tribe container, which has tribev2 + the scorer package):
    python analyze_baseline.py <preds_dir> <vetting.json> <out_dir>
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, "/tribe/work")
from tribe_scoring.run_and_save import quick_scores  # noqa: E402  (same feature code as production)

HOOK_LAG = slice(4, 8)  # predicted seconds 4..7; 0..3 is BOLD warm-up
PRIMARY = ["composite_raw", "gfp_mean", "gfp_hook_lag"]
N_PERM = 10_000
rng = np.random.default_rng(20261116)


def eta_sq(y, g):
    y, g = np.asarray(y, float), np.asarray(g)
    grand = y.mean()
    ss_tot = ((y - grand) ** 2).sum()
    ss_b = sum(((g == k).sum()) * (y[g == k].mean() - grand) ** 2 for k in np.unique(g))
    return float(ss_b / ss_tot) if ss_tot > 0 else 0.0


def perm_p(y, g):
    obs = eta_sq(y, g)
    g = np.asarray(g)
    hits = sum(eta_sq(y, rng.permutation(g)) >= obs for _ in range(N_PERM))
    return obs, (hits + 1) / (N_PERM + 1)


def spearman(a, b):
    ra, rb = np.argsort(np.argsort(a)), np.argsort(np.argsort(b))
    return float(np.corrcoef(ra, rb)[0, 1])


def main(preds_dir: Path, vetting: Path, out_dir: Path):
    meta = {x["name"]: x for x in json.loads(vetting.read_text()) if x.get("include")}
    rows = []
    for npy in sorted(preds_dir.glob("*_preds.npy")):
        name = npy.name[: -len("_preds.npy")]
        if name not in meta:
            continue
        preds = np.load(npy)
        q = quick_scores(preds)
        gfp = np.sqrt((preds ** 2).mean(axis=1))
        m = meta[name]
        rows.append(dict(
            name=name, true_category=m["true_category"], true_arm=m["true_arm"], format=m["format"],
            n_seconds=int(preds.shape[0]), composite_raw=q["composite_raw"], gfp_mean=q["gfp_mean"],
            gfp_hook_lag=float(gfp[HOOK_LAG].mean()) if preds.shape[0] >= 8 else float("nan"),
            gfp_hook_0_3=q["gfp_hook"],
        ))
    out_dir.mkdir(parents=True, exist_ok=True)
    cols = list(rows[0])
    with open(out_dir / "baseline_scores.csv", "w") as f:
        f.write(",".join(cols) + "\n")
        for r in rows:
            f.write(",".join(str(r[c]) for c in cols) + "\n")

    stats = {"n_scored": len(rows), "n_included": len(meta), "metrics": {}}
    groupings = {
        "category": lambda r: r["true_category"] in {"beauty", "food", "home", "tech"},
        "arm": lambda r: r["true_arm"] in {"human", "ai"},
        "format": lambda r: r["format"] in {"ugc", "polished_spot"},
    }
    key = {"category": "true_category", "arm": "true_arm", "format": "format"}
    for metric in PRIMARY + ["gfp_hook_0_3"]:
        ms = {}
        for gname, keep in groupings.items():
            sub = [r for r in rows if keep(r) and np.isfinite(r[metric])]
            y = [r[metric] for r in sub]
            g = [r[key[gname]] for r in sub]
            e, p = perm_p(y, g)
            groups = {k: dict(n=int(sum(1 for x in g if x == k)),
                              mean=float(np.mean([v for v, x in zip(y, g) if x == k])))
                      for k in sorted(set(g))}
            ms[gname] = dict(n=len(sub), eta_sq=round(e, 4), perm_p=round(p, 4), groups=groups)
        fin = [r for r in rows if np.isfinite(r[metric])]
        ms["length_spearman"] = round(spearman([r[metric] for r in fin], [r["n_seconds"] for r in fin]), 3)
        vals = np.array([r[metric] for r in fin])
        ms["percentiles"] = {str(k): float(np.percentile(vals, k)) for k in (10, 25, 50, 75, 90)}
        stats["metrics"][metric] = ms
    (out_dir / "baseline_stats.json").write_text(json.dumps(stats, indent=1))
    print(json.dumps(stats, indent=1))


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]))
