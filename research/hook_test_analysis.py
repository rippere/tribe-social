"""
hook_test_analysis.py — the pre-registered analysis for the hook test (PREREGISTRATION.md §5 to §10).

Run once, on the single results pull (§9). Every threshold here is copied from the
pre-registration, and this file's SHA-256 is part of the freeze record (§12), so any
edit after freeze is a deviation.

Inputs, one row per clip, joined on filename (baseNN_{spoken,visual,text,cold}.mp4):
    features   filename, a_* columns (Model A, content), b_* columns (Model B, TRIBE)
    outcomes   filename, impressions, plays_3s, plays_15s, and optionally
               rejected (1 = rejected by ad review, blank or 0 = not) and frequency (reported only)
    guesses    guesser, role, base, variant, rank   (optional, §7a; rank 1 = most likely
               to keep a viewer past 3 seconds)

What it computes:
    §9   exclusions   a clip under 750 impressions, a rejected variant, or impressions
                      differing by more than 20% inside a base drops the whole base
    §5   outcome      logit hook rate (3-second plays / impressions), weighted by impressions
    §6   models       A content, B brain, C = A + B, R = A + random features sized like B,
                      D = variant-type dummies (the H3 baseline). Ridge regression with an
                      unpenalised intercept, standardised inside each training fold, penalty
                      chosen by leave-one-base-out inside the training rows; the outer loop
                      is leave-one-base-out too
    §7   H1           within-base correlation of out-of-fold prediction and outcome;
                      permutation of variant labels within base, base bootstrap interval,
                      mean Kendall tau-b across bases
         H2           ΔR²(C − A) >= 0.03, conditional permutation p < 0.05 (brain features
                      permuted within base after regressing out Model A), base bootstrap
                      lower bound > 0
         H3           ΔR²(C − D) >= 0.02
         control      Model R must not clear the H2 bar
         secondary    H1 and H2 on logit hold rate (15-second plays), Benjamini-Hochberg
    §7a  guesses      exploratory; same machinery as H1
    §10  verdict      GO, NO-GO, INCONCLUSIVE or INSTRUMENT FAILURE

Readings of the pre-registration that the text leaves open, fixed here before any data:
    - H1 enters the verdict through Model B (brain only); Model C's H1 is reported beside it.
    - H1 and H2 permutation p-values are one-sided: the hypothesis is a positive association.
    - "Differ by more than 20%" means the base's largest impressions exceed its smallest by >20%.
    - The logit is empirical: log((k + 0.5) / (n - k + 0.5)), so a rate of 0 or 1 stays finite.
    - Model R's "random projections" are standard-normal features, one per Model B column,
      drawn once with a fixed seed. They carry no information, so R clearing the H2 bar can
      only mean the pipeline leaks.
    - Model A is regressed out of the brain block by cross-fitting: each base's brain features
      are predicted from Model A by a ridge fit on the other bases, and the remainder is what
      gets permuted. Run --check-features on the frozen feature file before freeze; if Model A
      already explains nearly all of the brain block, H2 has little left to test.
    - "Delivery diagnostics fail" (§10) means fewer than 10 bases survive the §9 exclusions;
      §8 shows ten bases can only rule out a large effect. That is INSTRUMENT FAILURE.
    - §10's "minimum detectable effect sits above the bar" route to INCONCLUSIVE is not
      computed; INCONCLUSIVE comes only from a mixed H1/H2 result.
    - Benjamini-Hochberg covers the two hold-rate tests. H3 has a bar but no p-value.
    - R² is measured against the impression-weighted mean of all analysed clips, so it
      includes between-base variance that H1's within-base centring removes.
    - 15-second plays above 3-second plays are reported as a warning, since they only feed
      the secondary outcome. 3-second plays above impressions stop the run: the logit is
      undefined, and the export's column definitions need checking.

Usage:
    .venv/bin/python hook_test_analysis.py --features hook_features.csv --check-features
    .venv/bin/python hook_test_analysis.py --features hook_features.csv --outcomes hook_outcomes.csv
    .venv/bin/python hook_test_analysis.py ... --guesses hook_guesses.csv --out hook_results.json

Takes roughly 40 minutes: about 36,000 cross-validated refits for the permutations and bootstrap.
Exit code 0 when the analysis completes, whatever the verdict; 2 on bad input.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

# Thousands of 68 x 68 eigenproblems: multithreaded BLAS makes each one ~20x slower. Must precede numpy.
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")

import numpy as np
import pandas as pd
from rich.console import Console
from rich.progress import track
from rich.table import Table
from scipy.stats import kendalltau

from validate_stimuli import NAME_RE, VARIANTS

console = Console()

SEED = 20260917
N_PERM = 10_000  # §7 H1; used for every permutation test
N_BOOT = 2_000
ALPHAS = np.logspace(-2, 6, 33)  # ridge penalties searched inside each training fold

MIN_IMPRESSIONS = 750  # §9
MAX_IMBALANCE = 1.20  # §9: largest over smallest impressions inside a base
MIN_BASES = 10  # §10 delivery failure below this
H2_MIN_DELTA = 0.03  # §7 H2
H3_MIN_DELTA = 0.02  # §7 H3
P_BAR = 0.05
H1_MODEL = "B"


class InputError(Exception):
    pass


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def elogit(k: np.ndarray, n: np.ndarray) -> np.ndarray:
    return np.log((k + 0.5) / (n - k + 0.5))


# ── inputs ────────────────────────────────────────────────────────────────────

def load_features(path: Path) -> tuple[pd.DataFrame, list[str], list[str]]:
    """Read the feature file, parse base and variant from each filename, and check it is complete."""
    feats = pd.read_csv(path)
    if "filename" not in feats.columns:
        raise InputError("features file is missing column: filename")
    dup = feats.filename[feats.filename.duplicated()]
    if len(dup):
        raise InputError(f"features file lists {dup.iloc[0]} more than once")
    a_cols = [c for c in feats.columns if c.startswith("a_")]
    b_cols = [c for c in feats.columns if c.startswith("b_")]
    if not a_cols or not b_cols:
        raise InputError("features file needs a_* (Model A) and b_* (Model B) columns")
    if feats[a_cols + b_cols].isna().any().any():
        raise InputError("features file has empty cells; every clip must be fully scored")

    parsed = feats.filename.str.extract(NAME_RE.pattern)
    if parsed[0].isna().any():
        bad = feats.filename[parsed[0].isna()].iloc[0]
        raise InputError(f"{bad}: name must look like base03_spoken.mp4")
    feats["base"] = parsed[0].astype(int)
    feats["variant"] = pd.Categorical(parsed[1], categories=VARIANTS, ordered=True)
    sizes = feats.groupby("base").size()
    if (sizes != len(VARIANTS)).any():
        b = sizes[sizes != len(VARIANTS)].index[0]
        raise InputError(f"base {b:02d} does not have all four variants")
    return feats.sort_values(["base", "variant"]).reset_index(drop=True), a_cols, b_cols


def load(features_path: Path, outcomes_path: Path) -> tuple[pd.DataFrame, list[str], list[str]]:
    """Join features and outcomes, check them, and keep the base-then-variant row order."""
    feats, a_cols, b_cols = load_features(features_path)
    outs = pd.read_csv(outcomes_path)
    missing = [c for c in ("filename", "impressions", "plays_3s", "plays_15s") if c not in outs.columns]
    if missing:
        raise InputError(f"outcomes file is missing column(s): {', '.join(missing)}")
    dup = outs.filename[outs.filename.duplicated()]
    if len(dup):
        raise InputError(f"outcomes file lists {dup.iloc[0]} more than once")

    raw = outs["rejected"] if "rejected" in outs.columns else pd.Series(0, index=outs.index)
    rejected = pd.to_numeric(raw, errors="coerce")
    if (raw.notna() & rejected.isna()).any() or not rejected.dropna().isin([0, 1]).all():
        raise InputError("rejected must be 1, 0 or blank")
    outs["rejected"] = rejected.fillna(0).astype(bool)

    counts = outs[["impressions", "plays_3s", "plays_15s"]].apply(pd.to_numeric, errors="coerce")
    if counts.isna().any().any() or (counts < 0).any().any() or (counts % 1 != 0).any().any():
        raise InputError("impressions and plays must be filled in as whole, non-negative numbers")
    outs[counts.columns] = counts.astype("int64")
    if (outs.plays_3s > outs.impressions).any():
        bad = outs.filename[outs.plays_3s > outs.impressions].iloc[0]
        raise InputError(f"{bad}: 3-second plays exceed impressions; check the export's column definitions")
    for name in outs.filename[outs.plays_15s > outs.plays_3s]:
        console.print(f"[yellow]{name}: 15-second plays exceed 3-second plays (secondary outcome only)[/yellow]")

    df = feats.merge(outs, on="filename", how="outer", indicator=True)
    unmatched = df[df["_merge"] != "both"]
    if len(unmatched):
        raise InputError(f"{unmatched.filename.iloc[0]} is in one file but not the other")
    df = df.drop(columns="_merge")
    return df.sort_values(["base", "variant"]).reset_index(drop=True), a_cols, b_cols


def exclusions(df: pd.DataFrame) -> dict[int, list[str]]:
    """§9: reasons each excluded base was dropped."""
    reasons: dict[int, list[str]] = {}
    for b, g in df.groupby("base"):
        r = [f"{v} delivered {n:,} impressions (floor {MIN_IMPRESSIONS:,})"
             for v, n in zip(g.variant, g.impressions) if n < MIN_IMPRESSIONS]
        r += [f"{v} rejected by ad review" for v, x in zip(g.variant, g.rejected) if x]
        lo, hi = g.impressions.min(), g.impressions.max()
        if lo > 0 and hi / lo > MAX_IMBALANCE:
            r.append(f"impressions differ by {hi / lo - 1:.0%} across variants (limit 20%)")
        if r:
            reasons[int(b)] = r
    return reasons


# ── models ────────────────────────────────────────────────────────────────────

def group_loo(U: np.ndarray, s2: np.ndarray, root: np.ndarray, y: np.ndarray,
              groups: np.ndarray) -> np.ndarray:
    """Weighted leave-one-base-out squared error for every penalty, without refitting.

    With an unpenalised intercept the hat matrix is H = 1 sw' + W^-1/2 U diag(s2 / (s2 + a)) U' W^1/2,
    and holding out base S leaves residuals (I - H_SS)^-1 e_S, exactly.
    """
    w = root ** 2
    shrink = s2[None, :] / (s2[None, :] + ALPHAS[:, None])
    H = ((U[None] * shrink[:, None, :]) @ U.T) * (root[None, None, :] / root[None, :, None])
    H += (w / w.sum())[None, None, :]
    e = y[None, :] - H @ y
    loss = np.zeros(len(ALPHAS))
    for g in np.unique(groups):
        S = np.flatnonzero(groups == g)
        M = np.eye(len(S))[None] - H[:, S[:, None], S[None, :]]
        try:
            e_out = np.linalg.solve(M, e[:, S, None])[..., 0]
        except np.linalg.LinAlgError:
            e_out = (np.linalg.pinv(M) @ e[:, S, None])[..., 0]
        loss += (w[S] * e_out ** 2).sum(axis=1)
    return loss


def ridge_predict(X_tr: np.ndarray, y_tr: np.ndarray, w_tr: np.ndarray, groups_tr: np.ndarray,
                  X_te: np.ndarray) -> np.ndarray:
    """Weighted ridge with an unpenalised intercept, standardised on the training rows.

    The penalty is chosen by leave-one-base-out inside the training rows (group_loo). Solved in the
    n x n kernel form because Model A has far more columns than there are clips.
    """
    w = w_tr / w_tr.mean()
    sw = w / w.sum()
    mu = sw @ X_tr
    sd = np.sqrt(sw @ (X_tr - mu) ** 2)
    sd[sd < 1e-10 * (1 + np.abs(mu))] = 1.0  # constant columns stay constant, not rescaled noise
    root = np.sqrt(w)
    Z = (X_tr - mu) / sd * root[:, None]
    y_mean = sw @ y_tr

    s2, U = np.linalg.eigh(Z @ Z.T)
    s2 = np.clip(s2, 0.0, None)
    alpha = ALPHAS[np.argmin(group_loo(U, s2, root, y_tr, groups_tr))]
    dual = U @ ((U.T @ ((y_tr - y_mean) * root)) / (s2 + alpha))
    return ((X_te - mu) / sd) @ (Z.T @ dual) + y_mean


def cv_predict(X: np.ndarray, y: np.ndarray, w: np.ndarray, groups: np.ndarray) -> np.ndarray:
    """Out-of-fold predictions, holding out one base (group) at a time."""
    pred = np.empty_like(y)
    for g in np.unique(groups):
        te = groups == g
        pred[te] = ridge_predict(X[~te], y[~te], w[~te], groups[~te], X[te])
    return pred


def r2(y: np.ndarray, pred: np.ndarray, w: np.ndarray) -> float:
    ybar = np.average(y, weights=w)
    return float(1 - np.sum(w * (y - pred) ** 2) / np.sum(w * (y - ybar) ** 2))


def residualize(block: np.ndarray, on: np.ndarray, groups: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Split block into its cross-fitted prediction from `on` (leave-one-base-out ridge) and the remainder."""
    ones = np.ones(len(block))
    fitted = np.column_stack([cv_predict(on, block[:, j], ones, groups) for j in range(block.shape[1])])
    return fitted, block - fitted


def unexplained(block: np.ndarray, resid: np.ndarray) -> float:
    """Mean share of each column's variance left in the residual (constant columns skipped)."""
    var = block.var(axis=0)
    keep = var > 0
    return float(np.mean(resid.var(axis=0)[keep] / var[keep]))


# ── tests ─────────────────────────────────────────────────────────────────────

def within_base_r(pred: np.ndarray, y: np.ndarray, w: np.ndarray) -> np.ndarray:
    """Weighted correlation after centring both sides inside each base. Last two axes: (base, variant)."""
    wn = w / w.sum(axis=-1, keepdims=True)
    pc = pred - (wn * pred).sum(axis=-1, keepdims=True)
    yc = y - (wn * y).sum(axis=-1, keepdims=True)
    num = (w * pc * yc).sum(axis=(-2, -1))
    den = np.sqrt((w * pc ** 2).sum(axis=(-2, -1)) * (w * yc ** 2).sum(axis=(-2, -1)))
    return num / den


def h1(pred: np.ndarray, y: np.ndarray, w: np.ndarray, rng: np.random.Generator) -> dict:
    """§7 H1 on (base, variant) matrices: correlation, permutation p, bootstrap interval, mean tau-b."""
    nb, nv = pred.shape
    r = float(within_base_r(pred, y, w))
    if not np.isfinite(r):  # predictions or outcome constant within every base
        return {"r": r, "p": 1.0, "ci95": [float("nan")] * 2, "mean_tau_b": float("nan"), "clears": False}
    idx = rng.permuted(np.broadcast_to(np.arange(nv), (N_PERM, nb, nv)), axis=-1)
    null = within_base_r(np.take_along_axis(np.broadcast_to(pred, idx.shape), idx, axis=-1), y, w)
    p = float((1 + np.sum(null >= r)) / (1 + N_PERM))
    pick = rng.integers(0, nb, (N_BOOT, nb))
    boot = within_base_r(pred[pick], y[pick], w[pick])
    lo, hi = np.nanpercentile(boot, [2.5, 97.5])
    taus = [kendalltau(pred[i], y[i]).statistic for i in range(nb)]
    return {"r": r, "p": p, "ci95": [float(lo), float(hi)],
            "mean_tau_b": float(np.nanmean(taus)), "clears": p < P_BAR}


def conditional_perm(A: np.ndarray, fitted: np.ndarray, resid: np.ndarray, y: np.ndarray,
                     w: np.ndarray, groups: np.ndarray, r2_a: float, delta: float,
                     rng: np.random.Generator, label: str) -> float:
    """§7 H2: permute the A-residualised block within base, refit, and count ΔR² at least as large."""
    rows = np.arange(len(y)).reshape(-1, len(VARIANTS))
    null = np.empty(N_PERM)
    for i in track(range(N_PERM), description=label, console=console, transient=True):
        perm = rng.permuted(rows, axis=1).ravel()
        X = np.hstack([A, fitted + resid[perm]])
        null[i] = r2(y, cv_predict(X, y, w, groups), w) - r2_a
    return float((1 + np.sum(null >= delta)) / (1 + N_PERM))


def bootstrap_r2(models: dict[str, np.ndarray], y: np.ndarray, w: np.ndarray, nb: int,
                 rng: np.random.Generator) -> dict[str, np.ndarray]:
    """Resample bases with replacement and refit; copies of one base are held out together."""
    nv = len(VARIANTS)
    out = {name: np.empty(N_BOOT) for name in models}
    for i in track(range(N_BOOT), description="bootstrap", console=console, transient=True):
        pick = rng.integers(0, nb, nb)
        while len(np.unique(pick)) < 3:  # each training fold needs two bases for its own penalty search
            pick = rng.integers(0, nb, nb)
        rows = (pick[:, None] * nv + np.arange(nv)).ravel()
        groups = np.repeat(pick, nv)
        for name, X in models.items():
            out[name][i] = r2(y[rows], cv_predict(X[rows], y[rows], w[rows], groups), w[rows])
    return out


def benjamini_hochberg(p: list[float]) -> list[float]:
    p_arr = np.asarray(p, dtype=float)
    order = np.argsort(p_arr)
    q = p_arr[order] * len(p_arr) / np.arange(1, len(p_arr) + 1)
    q = np.minimum.accumulate(q[::-1])[::-1]
    out = np.empty_like(q)
    out[order] = np.minimum(q, 1.0)
    return out.tolist()


def guesses_analysis(path: Path, df: pd.DataFrame, y: np.ndarray, w: np.ndarray,
                     rng: np.random.Generator) -> dict:
    """§7a: the team's mean rank, scored with the H1 machinery, plus each guesser's own correlation."""
    g = pd.read_csv(path)
    missing = [c for c in ("guesser", "role", "base", "variant", "rank") if c not in g.columns]
    if missing:
        raise InputError(f"guesses file is missing column(s): {', '.join(missing)}")
    unknown = set(g.variant) - set(VARIANTS)
    if unknown:
        raise InputError(f"guesses file has unknown variant(s): {', '.join(sorted(map(str, unknown)))}")
    g["base"] = g.base.astype(str).str.extract(r"(\d+)")[0].astype(int)
    bases = list(dict.fromkeys(df.base))  # analysed bases, in matrix row order
    g = g[g.base.isin(bases)]
    score = -g.pivot_table(index="base", columns="variant", values="rank", aggfunc="mean")
    score = score.reindex(index=bases, columns=list(VARIANTS))
    ranked = ~score.isna().any(axis=1).to_numpy()
    if ranked.sum() < 2:
        return {"note": "fewer than two analysed bases have a full set of guesses"}
    team = h1(score.to_numpy()[ranked], y[ranked], w[ranked], rng)

    per_guesser = {}
    for who, gg in g.groupby("guesser"):
        s = -gg.pivot_table(index="base", columns="variant", values="rank", aggfunc="mean")
        s = s.reindex(index=bases, columns=list(VARIANTS))
        m = ~s.isna().any(axis=1).to_numpy()
        if m.any():
            per_guesser[str(who)] = float(within_base_r(s.to_numpy()[m], y[m], w[m]))
    return {"team": team, "bases_ranked": int(ranked.sum()), "per_guesser": per_guesser}


# ── report ────────────────────────────────────────────────────────────────────

def verdict(h1_clears: bool, h2_clears: bool, control_clears: bool) -> tuple[str, str]:
    """§10."""
    if control_clears:
        return "INSTRUMENT FAILURE", "the negative control cleared the H2 bar, so the pipeline leaks; fix, report, re-run once"
    if h1_clears and h2_clears:
        return "GO", "replicate on a fresh set of bases before any product claim"
    if not h1_clears and not h2_clears:
        return "NO-GO", "the brain layer adds nothing here; publish it"
    return "INCONCLUSIVE", "one costed re-run at 20 bases, or stop; no claim either way"


def print_delivery(df: pd.DataFrame, excluded: dict[int, list[str]]) -> None:
    table = Table(title="Delivery (§4, §9)")
    for col in ("Base", *VARIANTS, "Imbalance", "Status"):
        table.add_column(col)
    for b, g in df.groupby("base"):
        imp = g.set_index("variant").impressions
        lo, hi = imp.min(), imp.max()
        status = "[red]excluded[/red]: " + "; ".join(excluded[b]) if b in excluded else "[green]analysed[/green]"
        table.add_row(f"{b:02d}", *[f"{imp[v]:,}" for v in VARIANTS],
                      f"{hi / lo - 1:.0%}" if lo else "n/a", status)
    console.print(table)
    if "frequency" in df.columns:
        console.print(f"Mean frequency: {df.frequency.mean():.2f}")


def print_results(res: dict) -> None:
    table = Table(title="Pre-registered tests (§7)")
    for col in ("Test", "Estimate", "Interval", "p", "Bar", "Clears"):
        table.add_column(col)
    yes = lambda ok: "[green]yes[/green]" if ok else "[red]no[/red]"
    for m in ("B", "C"):
        t = res["h1"][m]
        role = "verdict" if m == H1_MODEL else "reported"
        table.add_row(f"H1, Model {m} ({role})", f"r = {t['r']:.3f}, tau-b = {t['mean_tau_b']:.3f}",
                      f"[{t['ci95'][0]:.3f}, {t['ci95'][1]:.3f}]", f"{t['p']:.4f}", "p < 0.05", yes(t["clears"]))
    for key, name in (("h2", "H2, ΔR²(C − A)"), ("control", "Control, ΔR²(R − A)")):
        t = res[key]
        table.add_row(name, f"{t['delta']:.4f}", f"[{t['ci95'][0]:.4f}, {t['ci95'][1]:.4f}]",
                      f"{t['p']:.4f}", "≥ 0.03, p < 0.05, LB > 0",
                      yes(t["clears"]) if key == "h2" else ("[red]yes, leak[/red]" if t["clears"] else "[green]no[/green]"))
    t = res["h3"]
    table.add_row("H3, ΔR²(C − D)", f"{t['delta']:.4f}", "", "", "≥ 0.02", yes(t["clears"]))
    for key, name in (("h1_hold", "Secondary H1, hold rate"), ("h2_hold", "Secondary H2, hold rate")):
        t = res["secondary"][key]
        est = f"r = {t['r']:.3f}" if "r" in t else f"{t['delta']:.4f}"
        table.add_row(name, est, "", f"{t['p']:.4f} (q {t['q']:.4f})", "BH q < 0.05", yes(t["q"] < P_BAR))
    console.print(table)

    r2s = res["r2"]
    console.print("Cross-validated R², logit hook rate: " + ", ".join(f"{k} {v:.4f}" for k, v in r2s.items()))
    console.print(f"Brain-feature variance Model A leaves unexplained: {res['brain_unexplained']:.1%}")
    g = res.get("guesses")
    if g and "team" in g:
        t = g["team"]
        console.print(f"\n§7a human guesses (exploratory), {g['bases_ranked']} bases: team r = {t['r']:.3f} "
                      f"[{t['ci95'][0]:.3f}, {t['ci95'][1]:.3f}], p = {t['p']:.4f}; individual r: "
                      + ", ".join(f"{k} {v:.2f}" for k, v in sorted(g["per_guesser"].items())))
    elif g:
        console.print(f"\n§7a human guesses: {g['note']}")


def check_features(path: Path) -> int:
    """Pre-freeze: how much of the brain block survives regressing out Model A. Needs no outcomes."""
    try:
        df, a_cols, b_cols = load_features(path)
    except (InputError, OSError, pd.errors.ParserError) as exc:
        console.print(f"[red]{exc}[/red]")
        return 2
    if df.base.nunique() < 3:
        console.print("[red]need at least three bases to cross-fit[/red]")
        return 2
    B = df[b_cols].to_numpy(float)
    _, resid = residualize(B, df[a_cols].to_numpy(float), df.base.to_numpy())
    console.print(f"{df.base.nunique()} bases, {len(a_cols)} Model A columns, {len(b_cols)} Model B columns")
    console.print(f"Brain-feature variance Model A leaves unexplained (cross-fitted): {unexplained(B, resid):.1%}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--features", type=Path, required=True, help="frozen feature file, one row per clip")
    parser.add_argument("--outcomes", type=Path, help="the single results pull, one row per clip")
    parser.add_argument("--guesses", type=Path, help="human-guess CSV (§7a), optional")
    parser.add_argument("--out", type=Path, help="write every number to this JSON file")
    parser.add_argument("--check-features", action="store_true",
                        help="before freeze: report how much of Model B is left after regressing out Model A, then stop")
    args = parser.parse_args(argv)

    if args.check_features:
        return check_features(args.features)
    if args.outcomes is None:
        parser.error("--outcomes is required unless --check-features is given")

    try:
        df, a_cols, b_cols = load(args.features, args.outcomes)
    except (InputError, OSError, pd.errors.ParserError) as exc:
        console.print(f"[red]{exc}[/red]")
        return 2

    inputs = {"script": Path(__file__).resolve(), "features": args.features,
              "outcomes": args.outcomes, "guesses": args.guesses}
    hashes = {k: sha256(p) for k, p in inputs.items() if p is not None}
    for k, h in hashes.items():
        console.print(f"[dim]{k:9s} sha256 {h}[/dim]")

    excluded = exclusions(df)
    print_delivery(df, excluded)
    res: dict = {"hashes": hashes, "excluded": {f"{b:02d}": r for b, r in excluded.items()}}
    df = df[~df.base.isin(excluded)].reset_index(drop=True)
    nb, nv = df.base.nunique(), len(VARIANTS)
    res["bases_analysed"] = int(nb)
    if nb < MIN_BASES:
        res["verdict"] = "INSTRUMENT FAILURE"
        res["verdict_reason"] = f"delivery left {nb} analysable bases, below the minimum of {MIN_BASES}"
    else:
        rng = np.random.default_rng(SEED)
        w = df.impressions.to_numpy(float)
        y = elogit(df.plays_3s.to_numpy(float), w)
        y_hold = elogit(df.plays_15s.to_numpy(float), w)
        groups = df.base.to_numpy()
        A, B = df[a_cols].to_numpy(float), df[b_cols].to_numpy(float)
        noise = rng.standard_normal(B.shape)
        models = {"A": A, "B": B, "C": np.hstack([A, B]), "R": np.hstack([A, noise]),
                  "D": pd.get_dummies(df.variant).to_numpy(float)}

        oof = {k: cv_predict(X, y, w, groups) for k, X in models.items()}
        res["r2"] = {k: r2(y, p, w) for k, p in oof.items()}
        mat = lambda v: v.reshape(nb, nv)
        res["h1"] = {m: h1(mat(oof[m]), mat(y), mat(w), rng) for m in ("B", "C")}

        boot = bootstrap_r2({k: models[k] for k in ("A", "C", "R")}, y, w, nb, rng)
        fit_b, res_b = residualize(B, A, groups)
        fit_n, res_n = residualize(noise, A, groups)
        res["brain_unexplained"] = unexplained(B, res_b)
        for key, name, extra in (("h2", "C", (fit_b, res_b)), ("control", "R", (fit_n, res_n))):
            delta = res["r2"][name] - res["r2"]["A"]
            p = conditional_perm(A, *extra, y, w, groups, res["r2"]["A"], delta, rng, f"H2 permutations, Model {name}")
            lo, hi = np.percentile(boot[name] - boot["A"], [2.5, 97.5])
            res[key] = {"delta": delta, "p": p, "ci95": [float(lo), float(hi)],
                        "clears": bool(delta >= H2_MIN_DELTA and p < P_BAR and lo > 0)}
        res["h3"] = {"delta": res["r2"]["C"] - res["r2"]["D"]}
        res["h3"]["clears"] = res["h3"]["delta"] >= H3_MIN_DELTA

        oof_hold = {k: cv_predict(models[k], y_hold, w, groups) for k in ("A", "B", "C")}
        h1_hold = h1(mat(oof_hold[H1_MODEL]), mat(y_hold), mat(w), rng)
        r2_a_hold = r2(y_hold, oof_hold["A"], w)
        delta_hold = r2(y_hold, oof_hold["C"], w) - r2_a_hold
        p_hold = conditional_perm(A, fit_b, res_b, y_hold, w, groups, r2_a_hold, delta_hold, rng,
                                  "H2 permutations, hold rate")
        q = benjamini_hochberg([h1_hold["p"], p_hold])
        res["secondary"] = {"h1_hold": {"r": h1_hold["r"], "p": h1_hold["p"], "q": q[0]},
                            "h2_hold": {"delta": delta_hold, "p": p_hold, "q": q[1]}}

        if args.guesses:
            try:
                res["guesses"] = guesses_analysis(args.guesses, df, mat(y), mat(w), rng)
            except (InputError, OSError, pd.errors.ParserError) as exc:
                console.print(f"[red]{exc}[/red]")
                return 2

        res["verdict"], res["verdict_reason"] = verdict(
            res["h1"][H1_MODEL]["clears"], res["h2"]["clears"], res["control"]["clears"])
        print_results(res)

    console.print(f"\n[bold]Verdict: {res['verdict']}[/bold] — {res['verdict_reason']}")
    if args.out:
        args.out.write_text(json.dumps(res, indent=2, default=lambda o: o.item() if hasattr(o, "item") else str(o)))
        console.print(f"Results written to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
