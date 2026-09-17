"""Power simulation for the hook-rate pre-registration (research/PREREGISTRATION.md).

Design: B base videos x 4 hook variants, each clip shown to N impressions.
Primary test H1: per base, Kendall tau-b between the model's predicted order of the
4 variants and their measured hook-rate order; mean tau across bases, tested against
a within-base label-permutation null.

The model's true skill is `rho`: the correlation between its prediction and the real
hook quality of a variant, AFTER the content baseline has taken its share. So rho is
incremental skill, not total skill.
"""
import itertools
import numpy as np

RNG = np.random.default_rng(20260917)
P0 = 0.25          # baseline hook rate
SD_BASE = 0.30     # spread between base videos, logit units
SD_HOOK = 0.25     # spread between the 4 hooks inside a base, logit units (~5 points at 25%)
TAU_BAR = 0.30     # pre-registered minimum mean tau
SIMS = 20000


def tau4(order_a, order_b):
    """Kendall tau for 4 items, no ties."""
    c = 0
    for i, j in itertools.combinations(range(4), 2):
        c += np.sign(order_a[i] - order_a[j]) * np.sign(order_b[i] - order_b[j])
    return c / 6.0


# Exact permutation null for one base: 24 orderings of 4 items.
BASE_TAUS = np.array([tau4(np.array([0, 1, 2, 3]), np.array(p)) for p in itertools.permutations(range(4))])


def null_critical(B, alpha=0.05, draws=200000):
    """5% critical value for mean tau across B bases, under within-base label permutation."""
    draw = RNG.choice(BASE_TAUS, size=(draws, B)).mean(axis=1)
    return np.quantile(draw, 1 - alpha)


def power(B, rho, n_impressions, sd_hook=SD_HOOK, sims=SIMS, crit=None):
    if crit is None:
        crit = null_critical(B)
    bar = max(crit, TAU_BAR)
    q = RNG.normal(0, sd_hook, size=(sims, B, 4))                      # true hook quality
    noise = RNG.normal(0, 1, size=(sims, B, 4))
    pred = rho * (q / sd_hook) + np.sqrt(1 - rho ** 2) * noise          # model prediction
    base = RNG.normal(0, SD_BASE, size=(sims, B, 1))
    p = 1 / (1 + np.exp(-(np.log(P0 / (1 - P0)) + base + q)))           # true hook rate
    obs = RNG.binomial(n_impressions, p) / n_impressions                # measured hook rate
    taus = np.empty((sims, B))
    for i, j in itertools.combinations(range(4), 2):
        pass
    # vectorised tau: sum of sign agreements over the 6 pairs
    acc = np.zeros((sims, B))
    for i, j in itertools.combinations(range(4), 2):
        acc += np.sign(pred[:, :, i] - pred[:, :, j]) * np.sign(obs[:, :, i] - obs[:, :, j])
    taus = acc / 6.0
    mean_tau = taus.mean(axis=1)
    return (mean_tau >= bar).mean(), mean_tau.mean(), bar


print("Design: 4 variants per base, hook spread sd = %.2f logit (~%.1f points at a %d%% hook rate)"
      % (SD_HOOK, 100 * (1 / (1 + np.exp(-(np.log(P0 / (1 - P0)) + SD_HOOK))) - P0), int(P0 * 100)))
print("\n1) Permutation null and the bar that actually binds")
crits = {}
for B in (8, 10, 12, 16, 20):
    crits[B] = null_critical(B)
    print(f"   bases={B:2d}: 5% critical mean tau = {crits[B]:.3f} | pre-registered bar 0.30 | binding bar = {max(crits[B], TAU_BAR):.3f}")

print("\n2) Power at 2,000 impressions per clip (need mean tau >= binding bar)")
print("   model skill rho |  " + "  ".join(f"B={b:<4d}" for b in (8, 10, 15, 20)))
for rho in (0.2, 0.3, 0.4, 0.5, 0.6, 0.7):
    row = []
    for B in (8, 10, 15, 20):
        pw, mt, _ = power(B, rho, 2000, crit=crits.get(B, null_critical(B)))
        row.append(f"{pw:5.2f} ")
    print(f"        {rho:.1f}        |  " + "  ".join(row))

print("\n3) Does impression volume matter? (B=10)")
for n in (1000, 2000, 4000):
    line = [f"{power(10, rho, n, crit=crits[10])[0]:.2f}" for rho in (0.3, 0.5, 0.7)]
    print(f"   {n:5d} impressions/clip: power at rho 0.3 / 0.5 / 0.7 = {' / '.join(line)}")

print("\n4) Does it matter how much the hook really moves hook rate? (B=10, 2,000 impressions)")
for sd in (0.15, 0.25, 0.40):
    line = [f"{power(10, rho, 2000, sd_hook=sd, crit=crits[10])[0]:.2f}" for rho in (0.3, 0.5, 0.7)]
    pts = 100 * (1 / (1 + np.exp(-(np.log(P0 / (1 - P0)) + sd))) - P0)
    print(f"   hook spread {sd:.2f} logit (~{pts:.1f} pts): power at rho 0.3 / 0.5 / 0.7 = {' / '.join(line)}")

print("\n5) Smallest model skill with 80% power")
for B in (8, 10, 15, 20):
    lo = next((r for r in np.arange(0.20, 1.0, 0.02)
               if power(B, float(r), 2000, sims=6000, crit=crits.get(B, null_critical(B)))[0] >= 0.80), None)
    dr2 = None if lo is None else lo ** 2 * 0.95
    print(f"   bases={B:2d}: rho >= {lo:.2f}" + (f"  (implies incremental R2 of roughly {dr2:.2f} within base)" if lo else "  (not reachable)"))
