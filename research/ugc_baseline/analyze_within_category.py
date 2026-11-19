"""Within-category check of the human-vs-AI arm effect (UGC baseline follow-up).

Arm is unevenly spread across categories, so a pooled human/AI difference could be a
category effect in disguise. This compares human vs AI only inside each category:
- per-category means and n
- stratified estimate: n-weighted mean of the within-category (human - ai) differences
- stratified permutation p: arm labels shuffled within category only (10,000 shuffles)
- OLS: metric ~ arm + category (+ n_seconds), arm coefficient and its permutation p

Usage: python analyze_within_category.py results/baseline_scores.csv [out.json]
"""
import csv
import json
import sys

import numpy as np

METRICS = ["composite_raw", "gfp_mean", "gfp_hook_lag"]
CATS = ["beauty", "food", "home", "tech"]
N_PERM = 10_000
rng = np.random.default_rng(20261117)


def load(path):
    rows = [r for r in csv.DictReader(open(path))
            if r["true_arm"] in ("human", "ai") and r["true_category"] in CATS]
    cat = np.array([r["true_category"] for r in rows])
    human = np.array([r["true_arm"] == "human" for r in rows])
    secs = np.array([float(r["n_seconds"]) for r in rows])
    vals = {m: np.array([float(r[m]) for r in rows]) for m in METRICS}
    return cat, human, secs, vals


def strat_diff(y, human, cat):
    """n-weighted mean of within-category human-ai differences (categories with both arms)."""
    num = den = 0.0
    for c in CATS:
        h, a = y[(cat == c) & human], y[(cat == c) & ~human]
        if len(h) and len(a):
            w = len(h) + len(a)
            num += w * (h.mean() - a.mean())
            den += w
    return num / den


def shuffle_within(human, cat):
    out = human.copy()
    for c in CATS:
        idx = np.flatnonzero(cat == c)
        out[idx] = rng.permutation(human[idx])
    return out


def ols_arm_coef(y, human, cat, secs, with_len):
    cols = [np.ones_like(y), human.astype(float)]
    cols += [(cat == c).astype(float) for c in CATS[1:]]
    if with_len:
        cols.append((secs - secs.mean()) / secs.std())
    X = np.column_stack(cols)
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    return beta[1]


def main(path, out=None):
    cat, human, secs, vals = load(path)
    report = {"n": int(len(cat)), "cells": {}, "metrics": {}}
    for c in CATS:
        report["cells"][c] = {"human": int(((cat == c) & human).sum()),
                              "ai": int(((cat == c) & ~human).sum())}
    perms = [shuffle_within(human, cat) for _ in range(N_PERM)]
    for m in METRICS:
        y = vals[m]
        per_cat = {}
        for c in CATS:
            h, a = y[(cat == c) & human], y[(cat == c) & ~human]
            per_cat[c] = {"human_mean": round(float(h.mean()), 4) if len(h) else None,
                          "ai_mean": round(float(a.mean()), 4) if len(a) else None,
                          "diff": round(float(h.mean() - a.mean()), 4) if len(h) and len(a) else None}
        obs = strat_diff(y, human, cat)
        null = np.array([strat_diff(y, p, cat) for p in perms])
        p_strat = float((np.abs(null) >= abs(obs)).mean())
        res = {"per_category": per_cat,
               "pooled_diff": round(float(y[human].mean() - y[~human].mean()), 4),
               "stratified_diff": round(float(obs), 4),
               "stratified_perm_p": round(p_strat, 4),
               "sd": round(float(y.std()), 4)}
        for with_len in (False, True):
            b = ols_arm_coef(y, human, cat, secs, with_len)
            nb = np.array([ols_arm_coef(y, p, cat, secs, with_len) for p in perms[:2000]])
            key = "ols_arm_cat_len" if with_len else "ols_arm_cat"
            res[key] = {"coef": round(float(b), 4),
                        "perm_p": round(float((np.abs(nb) >= abs(b)).mean()), 4)}
        report["metrics"][m] = res
    print(json.dumps(report, indent=1))
    if out:
        json.dump(report, open(out, "w"), indent=1)


if __name__ == "__main__":
    main(*sys.argv[1:])
