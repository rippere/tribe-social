"""Second power run: rank test vs continuous within-base test.

The first run showed the fixed tau >= 0.30 bar is unreachable. This compares it with
a within-base continuous test: centre both the model score and logit hook rate inside
each base, correlate across all clips, and test by permuting variant labels within base.
"""
import itertools
import numpy as np

RNG = np.random.default_rng(20260917)
P0, SD_BASE, SD_HOOK, SIMS = 0.25, 0.30, 0.25, 8000

# The registered design: 1,000 impressions per clip at an $8 CPM, so $8 per clip.
# These are the values that generate the table in section 8 of PREREGISTRATION.md —
# running this file must reproduce that table, or the pre-registration is not checkable.
N_IMP = 1_000
CPM = 8.0
COST_PER_CLIP = CPM * N_IMP / 1_000  # $8.00


def simulate(B, rho, n_imp=N_IMP, sims=SIMS, sd_hook=SD_HOOK):
    q = RNG.normal(0, sd_hook, size=(sims, B, 4))
    pred = rho * (q / sd_hook) + np.sqrt(1 - rho ** 2) * RNG.normal(0, 1, size=(sims, B, 4))
    base = RNG.normal(0, SD_BASE, size=(sims, B, 1))
    p = 1 / (1 + np.exp(-(np.log(P0 / (1 - P0)) + base + q)))
    obs = RNG.binomial(n_imp, p) / n_imp
    logit_obs = np.log(np.clip(obs, 1e-4, 1 - 1e-4) / (1 - np.clip(obs, 1e-4, 1 - 1e-4)))
    return pred, logit_obs


def within_r(pred, y):
    """Correlation after centring both inside each base."""
    a = pred - pred.mean(axis=2, keepdims=True)
    b = y - y.mean(axis=2, keepdims=True)
    num = (a * b).sum(axis=(1, 2))
    den = np.sqrt((a ** 2).sum(axis=(1, 2)) * (b ** 2).sum(axis=(1, 2)))
    return num / np.where(den == 0, np.nan, den)


def mean_tau(pred, y):
    acc = np.zeros(pred.shape[:2])
    for i, j in itertools.combinations(range(4), 2):
        acc += np.sign(pred[:, :, i] - pred[:, :, j]) * np.sign(y[:, :, i] - y[:, :, j])
    return (acc / 6.0).mean(axis=1)


def crit_values(B, sims=40000):
    """Null: model prediction unrelated to outcome."""
    pred, y = simulate(B, 0.0, sims=sims)
    return np.quantile(within_r(pred, y), 0.95), np.quantile(mean_tau(pred, y), 0.95)


print(f"Power at {N_IMP:,} impressions per clip, 5% one-sided permutation test, no fixed effect bar\n")
print(" bases |  rho  | continuous within-base test | rank test (mean tau)")
for B in (10, 15, 20, 30):
    cr_r, cr_t = crit_values(B)
    for rho in (0.3, 0.4, 0.5):
        pred, y = simulate(B, rho)
        pw_r = (within_r(pred, y) >= cr_r).mean()
        pw_t = (mean_tau(pred, y) >= cr_t).mean()
        print(f"   {B:3d}  |  {rho:.1f}  |          {pw_r:5.2f}            |        {pw_t:5.2f}")
    print(f"        (5% thresholds: within-base r = {cr_r:.3f}, mean tau = {cr_t:.3f})")

print("\nBases needed for 80% power, continuous test")
for rho in (0.25, 0.3, 0.35, 0.4, 0.5):
    need = None
    for B in range(6, 61, 2):
        cr_r, _ = crit_values(B, sims=20000)
        pred, y = simulate(B, rho, sims=4000)
        if (within_r(pred, y) >= cr_r).mean() >= 0.80:
            need = B
            break
    clips = None if need is None else need * 4
    cost = None if need is None else int(round(clips * COST_PER_CLIP))
    print(f"  rho {rho:.2f}: {need if need else '>60'} bases"
          + (f" = {clips} clips, about ${cost:,} in ad spend at ${CPM:.0f} CPM" if need else ""))

print("\nWhat mean tau to expect if the continuous test succeeds (B=15)")
for rho in (0.3, 0.4, 0.5):
    pred, y = simulate(15, rho)
    print(f"  rho {rho:.1f}: mean tau averages {mean_tau(pred, y).mean():.2f}, within-base r averages {np.nanmean(within_r(pred, y)):.2f}")


# ---------------------------------------------------------------------------
# Section 8 table of PREREGISTRATION.md, regenerated from this run.
# ---------------------------------------------------------------------------
print(f"\nPREREGISTRATION.md section 8 table (at {N_IMP:,} impressions/clip, ${CPM:.0f} CPM)")
print("| Bases | Clips | Ad spend | Power rho=0.3 | Power rho=0.4 | Power rho=0.5 |")
print("|---|---|---|---|---|---|")
for B in (10, 15, 18, 20):
    cr_r, _ = crit_values(B)
    powers = []
    for rho in (0.3, 0.4, 0.5):
        pred, y = simulate(B, rho)
        powers.append((within_r(pred, y) >= cr_r).mean())
    clips = B * 4
    cost = int(round(clips * COST_PER_CLIP))
    print(f"| {B} | {clips} | ${cost:,} | {powers[0]:.2f} | {powers[1]:.2f} | {powers[2]:.2f} |")
