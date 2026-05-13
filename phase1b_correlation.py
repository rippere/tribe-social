# %% [markdown]
# # tribe-social — Phase 1b Correlation Analysis
#
# **Project:** Validate whether TRIBE v2 cortical activation scores correlate
# with short-form video engagement metrics (shares, views, likes, comments).
#
# ## Scientific Basis
#
# **TRIBE v2** (Wubble et al. 2026, arXiv:2604.04025) predicts cortical BOLD
# on fsaverage5 (20,484 vertices) from video, audio, and text streams using a
# brain encoding model trained on Human Connectome Project data.
#
# **Berns et al. (2020, PNAS):** Neural responses during passive music listening
# predicted YouTube views and watch time at population scale — foundational
# evidence that brain encoding captures real-world engagement variance.
#
# **Scholz et al. (2017, PNAS):** vmPFC and TPJ activity predicted article
# virality and sharing, specifically implicating valuation (vmPFC) and social
# cognition (TPJ) — the same ROI categories scored here.
#
# ## Hypothesis
#
# TRIBE v2 composite scores — weighted sum of Attention (IFJa/IFJp),
# Social (PGi/PGp/IP1), Language (44/45), Valuation (vmPFC: 10v/25/s32),
# Auditory (STS/A5/TE1a), Motion (MT/MST/V4t), and Narrative/DMN (PCC complex)
# activations — will correlate positively with Instagram Reels **shares**,
# which require deliberate propagation intent and best reflect genuine neural
# engagement signals. Saves are a private metric and excluded from analysis.
#
# ## Analysis Output
# - **Figure 1** (4-panel, publishable): r heatmap · composite scatter ·
#   hook-window bars · portfolio map
# - **Figure 2** (conditional): per-ROI scatter for any ROI with |r| > 0.30
# - **Terminal summary** with go/no-go recommendation for Phase 2

# %% Cell 0 — Imports
import os
import warnings
import datetime
import numpy as np
import pandas as pd
import scipy.stats as stats
import matplotlib as mpl
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from matplotlib.patches import Patch
from matplotlib.lines import Line2D
import seaborn as sns
import statsmodels.api as sm

try:
    from adjustText import adjust_text
    HAS_ADJUSTTEXT = True
except ImportError:
    HAS_ADJUSTTEXT = False
    print('adjustText not installed — Panel D labels may overlap.')
    print('Install with: uv pip install adjustText')

# %% Cell 1 — Configuration  (edit this cell each corpus run)
# ─────────────────────────────────────────────────────────────────────────────

# File paths
SCORES_CSV     = os.environ.get('TRIBE_SCORES_CSV',     'scores.csv')
ENGAGEMENT_CSV = os.environ.get('TRIBE_ENGAGEMENT_CSV', 'engagement.csv')

# ROI weights (must sum to 1.0) — pre-Phase 1 priors; update after validation
ROI_WEIGHTS = {
    'attention':  0.25,
    'social':     0.30,
    'language':   0.15,
    'valuation':  0.20,
    'auditory':   0.05,
    'motion':     0.03,
    'narrative':  0.02,
}

# Thresholds
ALPHA               = 0.05
N_COMPARISONS       = 28          # 7 ROIs × 4 metrics (Bonferroni)
ALPHA_BONF          = ALPHA / N_COMPARISONS   # 0.00179
# Metrics: YouTube=[likes_per_view, views, likes, comments_per_view]
#          Instagram=[shares, views, likes, comments]
R_THRESHOLD         = 0.30        # per-ROI deep-dive inclusion cutoff
COMPOSITE_THRESHOLD = 0.40        # go/no-go for composite model r with primary metric
COMPOSITE_POST_GATE = 65          # composite_raw threshold for post decision (0–100)

# YOUTUBE_MODE: saves/shares unavailable on YouTube — use likes_per_view as proxy
# Set False when running against Instagram corpus (shares available via Apify)
YOUTUBE_MODE = True

CI_LEVEL       = 0.95
TOP_BOTTOM_PCT = 0.10             # top/bottom decile for Panel C hook analysis
BOOTSTRAP_N    = 1000             # bootstrap iterations when n < 30

# Output
FIGURE_MAIN_PNG = 'figure1_correlation_panel.png'
FIGURE_MAIN_PDF = 'figure1_correlation_panel.pdf'
FIGURE_DEEP_PNG = 'figure2_roi_deepdive.png'
FIGURE_DEEP_PDF = 'figure2_roi_deepdive.pdf'
DPI = 300

# %% [markdown]
# ## Statistical Design
#
# **Two-tailed Pearson r** throughout. Although the directional hypothesis
# (higher neural scores → more saves) is motivated by Berns 2020 and Scholz 2017,
# two-tailed tests are standard for non-preregistered exploratory analyses.
#
# **Bonferroni correction** applied to the heatmap only (28 simultaneous tests).
# Single-test panels (B, C, D) report uncorrected p-values with both shown.
#
# **Z-scoring** applied to ROI means across the corpus (not per-video) to
# allow cross-ROI comparison on a common scale. Engagement metrics remain in
# natural units for interpretability; z-scored only internally for the matrix.
#
# **Log transform** for engagement metrics with skewness > 2 (common in social
# media power-law distributions). Applied consistently; noted on axis labels.
#
# **Bootstrap CI** used in Panel B regression band when corpus n < 30.
#
# **Virality score** (shares×3 + comments×2 + likes) in Panel D weights
# propagation intent over passive engagement — the creator's key lever.

# %% Cell 2 — Data Loading and Merge
# ─────────────────────────────────────────────────────────────────────────────
scores_df = pd.read_csv(SCORES_CSV)
scores_df.columns = scores_df.columns.str.strip()

eng_df = pd.read_csv(ENGAGEMENT_CSV)
eng_df.columns = eng_df.columns.str.strip()

df = scores_df.merge(eng_df, on='filename', how='inner')
N  = len(df)

print(f'Corpus: {N} videos  (scores={len(scores_df)}, engagement={len(eng_df)}, matched={N})')

roi_labels = list(ROI_WEIGHTS.keys())

if YOUTUBE_MODE:
    # YouTube Shorts: shares not exposed — derive likes_per_view as quality proxy
    for col in ['views', 'likes', 'comments']:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    df['likes_per_view']    = (df['likes']    / df['views'].replace(0, np.nan)).round(6)
    df['comments_per_view'] = (df['comments'] / df['views'].replace(0, np.nan)).round(6)
    df['shares'] = np.nan
    eng_labels = ['likes_per_view', 'views', 'likes', 'comments_per_view']
    print(f'YouTube mode: using {eng_labels} (shares unavailable)')
else:
    # Instagram corpus: shares available via Apify scraper
    for col in ['views', 'likes', 'shares', 'comments']:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    eng_labels = ['shares', 'views', 'likes', 'comments']
    print(f'Instagram mode: using {eng_labels}')

missing_rois = [f'{r}_mean' for r in roi_labels if f'{r}_mean' not in df.columns]
missing_eng  = [e for e in eng_labels if e not in df.columns]
if missing_rois:
    raise ValueError(f'Missing ROI columns: {missing_rois}')
if missing_eng:
    raise ValueError(f'Missing engagement columns: {missing_eng}')

for col in eng_labels:
    df[col] = pd.to_numeric(df[col], errors='coerce')

if N < 30:
    warnings.warn(
        f'Corpus size is {N} (< 30). Pearson r estimates are unstable. '
        'Bootstrap CI used in scatter panels. Treat results as preliminary.',
        UserWarning
    )
    USE_BOOTSTRAP = True
else:
    USE_BOOTSTRAP = False

print(f'Bootstrap CI: {"YES (n < 30)" if USE_BOOTSTRAP else "NO"}')
print('Engagement skewness:')
for col in eng_labels:
    print(f'  {col}: {df[col].skew():.2f}')

# %% Cell 3 — Normalization
# ─────────────────────────────────────────────────────────────────────────────
ROI_MEAN_COLS = [f'{r}_mean' for r in roi_labels]
ROI_HOOK_COLS = [f'{r}_hook' for r in roi_labels]

for col in ROI_MEAN_COLS + ROI_HOOK_COLS:
    df[f'{col}_z'] = stats.zscore(df[col].fillna(df[col].mean()), nan_policy='omit')

for col in eng_labels:
    df[f'{col}_z'] = stats.zscore(df[col].fillna(df[col].mean()), nan_policy='omit')

# Composite from corpus-normalized ROI means
df['composite_z'] = sum(
    ROI_WEIGHTS[r] * df[f'{r}_mean_z']
    for r in roi_labels
)

# Virality score: weighted composite prioritising propagation intent
# weights: shares×3 (deliberate send) + comments×2 (active response) + likes×1
df['virality_score'] = (
    df['shares'].fillna(0) * 3
    + df['comments'].fillna(0) * 2
    + df['likes'].fillna(0)
)

# Log transform flags
LOG_ENG = {col: df[col].skew() > 2 for col in eng_labels}
print('Log-transform applied:')
for col, apply in LOG_ENG.items():
    print(f'  {col}: {"YES" if apply else "NO"} (skew={df[col].skew():.2f})')

# %% Cell 4 — Correlation Matrix
# ─────────────────────────────────────────────────────────────────────────────
r_matrix = pd.DataFrame(index=roi_labels, columns=eng_labels, dtype=float)
p_matrix = pd.DataFrame(index=roi_labels, columns=eng_labels, dtype=float)
p_bonf   = pd.DataFrame(index=roi_labels, columns=eng_labels, dtype=float)

for roi in roi_labels:
    for eng in eng_labels:
        x    = df[f'{roi}_mean_z']
        y    = df[eng]
        mask = x.notna() & y.notna()
        r, p = stats.pearsonr(x[mask], y[mask])
        r_matrix.loc[roi, eng] = r
        p_matrix.loc[roi, eng] = p
        p_bonf.loc[roi, eng]   = min(p * N_COMPARISONS, 1.0)

composite_r, composite_p = {}, {}
for eng in eng_labels:
    mask = df['composite_z'].notna() & df[eng].notna()
    r, p = stats.pearsonr(df['composite_z'][mask], df[eng][mask])
    composite_r[eng] = r
    composite_p[eng] = p

PRIMARY_METRIC = 'likes_per_view' if YOUTUBE_MODE else 'shares'
SECONDARY_METRIC = 'views' if YOUTUBE_MODE else 'shares'

print('Pearson r matrix:')
print(r_matrix.round(3).to_string())
print('\nComposite r:')
for eng in eng_labels:
    print(f'  vs {eng:<12}: r={composite_r[eng]:+.3f}  p={composite_p[eng]:.4f}')

qualifying_rois = [
    roi for roi in roi_labels
    if abs(r_matrix.loc[roi, PRIMARY_METRIC]) > R_THRESHOLD
    or abs(r_matrix.loc[roi, SECONDARY_METRIC]) > R_THRESHOLD
]
print(f'\nROIs exceeding |r| > {R_THRESHOLD} ({PRIMARY_METRIC} or {SECONDARY_METRIC}): {qualifying_rois}')

# %% Cell 5 — Hook-Window Group Statistics
# ─────────────────────────────────────────────────────────────────────────────
high_cut = df[PRIMARY_METRIC].quantile(1 - TOP_BOTTOM_PCT)
low_cut  = df[PRIMARY_METRIC].quantile(TOP_BOTTOM_PCT)
top_group = df[df[PRIMARY_METRIC] >= high_cut]
bot_group = df[df[PRIMARY_METRIC] <= low_cut]

_pm_label = PRIMARY_METRIC.replace('_', ' ').title()
if len(top_group) < 3 or len(bot_group) < 3:
    print(f'Warning: decile groups too small ({len(top_group)}/{len(bot_group)}). Using median split.')
    median    = df[PRIMARY_METRIC].median()
    top_group = df[df[PRIMARY_METRIC] > median]
    bot_group = df[df[PRIMARY_METRIC] <= median]
    GROUP_LABEL = f'Above/Below Median {_pm_label}'
else:
    GROUP_LABEL = f'Top {int(TOP_BOTTOM_PCT*100)}% vs Bottom {int(TOP_BOTTOM_PCT*100)}% by {_pm_label}'

hook_stats = pd.DataFrame({
    'roi':      roi_labels,
    'top_mean': [top_group[f'{r}_hook_z'].mean() for r in roi_labels],
    'top_se':   [top_group[f'{r}_hook_z'].sem()  for r in roi_labels],
    'bot_mean': [bot_group[f'{r}_hook_z'].mean() for r in roi_labels],
    'bot_se':   [bot_group[f'{r}_hook_z'].sem()  for r in roi_labels],
})
print(f'Group sizes: high={len(top_group)}, low={len(bot_group)}')

# %% Cell 6 — Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _ols_with_ci(x_arr, y_arr, x_range):
    """OLS regression line + 95% CI band. Bootstrap when USE_BOOTSTRAP is True."""
    X = sm.add_constant(x_arr)
    model = sm.OLS(y_arr, X).fit()
    Xr = sm.add_constant(x_range)
    y_line = model.predict(Xr)

    if USE_BOOTSTRAP:
        rng  = np.random.default_rng(42)
        boot = []
        for _ in range(BOOTSTRAP_N):
            idx = rng.integers(0, len(x_arr), len(x_arr))
            m   = sm.OLS(y_arr[idx], sm.add_constant(x_arr[idx])).fit()
            boot.append(m.predict(Xr))
        ci_lo = np.percentile(boot, 2.5, axis=0)
        ci_hi = np.percentile(boot, 97.5, axis=0)
    else:
        pred  = model.get_prediction(Xr)
        ci    = pred.conf_int(alpha=1 - CI_LEVEL)
        ci_lo, ci_hi = ci[:, 0], ci[:, 1]

    return y_line, ci_lo, ci_hi


def _eng_y(eng: str):
    """Return (y_series, axis_label) with optional log transform."""
    raw = df[eng]
    if LOG_ENG[eng]:
        return np.log1p(raw), f'{eng.capitalize()} (log1p)'
    return raw, eng.capitalize()


# %% Cell 7 — Figure 1: 4-Panel Publishable Figure
# ─────────────────────────────────────────────────────────────────────────────

sns.set_theme(style='white', font_scale=1.15)
mpl.rcParams.update({
    'font.family':       'sans-serif',
    'axes.spines.top':   False,
    'axes.spines.right': False,
    'axes.linewidth':    1.2,
    'xtick.major.size':  5,
    'ytick.major.size':  5,
})

C_POS   = '#2E86AB'   # blue — positive / high performers
C_NEG   = '#E84855'   # red  — negative / low performers
C_ABOVE = '#4CAF50'   # green — above post threshold
C_BELOW = '#FF9800'   # orange — below post threshold
CMAP_H  = 'RdBu_r'

fig = plt.figure(figsize=(16, 14))
gs  = gridspec.GridSpec(2, 2, figure=fig, hspace=0.40, wspace=0.34,
                        left=0.08, right=0.97, top=0.92, bottom=0.07)
ax_A = fig.add_subplot(gs[0, 0])
ax_B = fig.add_subplot(gs[0, 1])
ax_C = fig.add_subplot(gs[1, 0])
ax_D = fig.add_subplot(gs[1, 1])

# ── Panel A: Pearson r Heatmap ────────────────────────────────────────────────
annot = pd.DataFrame('', index=roi_labels, columns=eng_labels)
for roi in roi_labels:
    for eng in eng_labels:
        rv = r_matrix.loc[roi, eng]
        pu = p_matrix.loc[roi, eng]
        pb = p_bonf.loc[roi, eng]
        s  = f'{rv:.2f}'
        if pb < ALPHA:
            s += '*'
        elif pu < ALPHA:
            s += '†'   # dagger for uncorrected significance
        annot.loc[roi, eng] = s

sns.heatmap(
    r_matrix.astype(float), ax=ax_A, cmap=CMAP_H, vmin=-1, vmax=1,
    annot=annot, fmt='', linewidths=0.5, linecolor='#E0E0E0',
    cbar_kws={'label': 'Pearson r', 'shrink': 0.82},
)
ax_A.set_xticklabels(eng_labels, rotation=30, ha='right', fontsize=10)
ax_A.set_yticklabels([r.capitalize() for r in roi_labels], rotation=0, fontsize=10)
ax_A.set_title('A   ROI × Engagement Correlation', fontweight='bold', pad=10, fontsize=12)
ax_A.text(0, -0.18, '* Bonferroni p < 0.05   † uncorrected p < 0.05',
          transform=ax_A.transAxes, fontsize=8, color='#555555')

# ── Panel B: Composite Score vs. Primary Metric ───────────────────────────────
y_b, y_label_b = _eng_y(PRIMARY_METRIC)
x_b = df['composite_z']
mask_b = x_b.notna() & y_b.notna()
xf, yf = x_b[mask_b].values, y_b[mask_b].values

xr_b = np.linspace(xf.min(), xf.max(), 200)
y_line_b, ci_lo_b, ci_hi_b = _ols_with_ci(xf, yf, xr_b)

colors_b = [C_POS if r >= df['virality_score'].median() else '#AAAAAA'
            for r in df['virality_score'].fillna(0)]
ax_B.scatter(x_b[mask_b], y_b[mask_b], c=colors_b, s=70, alpha=0.82,
             edgecolors='white', linewidths=0.5, zorder=3)
ax_B.plot(xr_b, y_line_b, color=C_POS, linewidth=2, zorder=4)
ax_B.fill_between(xr_b, ci_lo_b, ci_hi_b, alpha=0.14, color=C_POS)

_pm = PRIMARY_METRIC if PRIMARY_METRIC in composite_r.index else list(composite_r.index)[0]
r_b = composite_r[_pm]
p_b = composite_p[_pm]
ax_B.text(0.05, 0.95, f'r = {r_b:.3f}\np = {p_b:.4f}',
          transform=ax_B.transAxes, fontsize=11, va='top',
          bbox=dict(boxstyle='round,pad=0.35', facecolor='white',
                    alpha=0.88, edgecolor='#CCCCCC'))
if USE_BOOTSTRAP:
    ax_B.text(0.97, 0.04, 'Bootstrap 95% CI (n < 30)',
              transform=ax_B.transAxes, fontsize=8, ha='right', color='#888888')

ax_B.set_xlabel('Composite Neural Score (z)', fontsize=11)
ax_B.set_ylabel(y_label_b, fontsize=11)
ax_B.set_title(f'B   Composite Score vs. {PRIMARY_METRIC.replace("_"," ").title()}', fontweight='bold', pad=10, fontsize=12)

# ── Panel C: Hook-Window Grouped Bar Chart ────────────────────────────────────
x_c   = np.arange(len(roi_labels))
width = 0.38

ax_C.bar(x_c - width / 2, hook_stats['top_mean'], width,
         yerr=hook_stats['top_se'], capsize=4,
         label='High Saves', color=C_POS, alpha=0.87, edgecolor='white',
         error_kw=dict(elinewidth=1.2, ecolor='#444'))
ax_C.bar(x_c + width / 2, hook_stats['bot_mean'], width,
         yerr=hook_stats['bot_se'], capsize=4,
         label='Low Saves', color=C_NEG, alpha=0.87, edgecolor='white',
         error_kw=dict(elinewidth=1.2, ecolor='#444'))

ax_C.set_xticks(x_c)
ax_C.set_xticklabels([r.capitalize() for r in roi_labels], rotation=35, ha='right', fontsize=9.5)
ax_C.set_ylabel('Mean Hook-Window Score (z, 0–3 s)', fontsize=11)
ax_C.axhline(0, color='black', linewidth=0.8, linestyle='--', alpha=0.45)
ax_C.legend(title=GROUP_LABEL, frameon=False, fontsize=9, title_fontsize=8)
ax_C.set_title(f'C   Hook-Window Activation by {_pm_label} Performance',
               fontweight='bold', pad=10, fontsize=12)

# ── Panel D: Portfolio Map ────────────────────────────────────────────────────
c_raw_mean = df['composite_raw'].mean()
c_raw_std  = df['composite_raw'].std()
thresh_z   = (COMPOSITE_POST_GATE - c_raw_mean) / (c_raw_std + 1e-9)

colors_d = [C_ABOVE if v >= COMPOSITE_POST_GATE else C_BELOW
            for v in df['composite_raw']]
ax_D.scatter(df['composite_z'], df['virality_score'].fillna(0),
             c=colors_d, s=82, alpha=0.85, edgecolors='white', linewidths=0.5, zorder=3)
ax_D.axvline(thresh_z, color='#333333', linestyle='--', linewidth=1.2, zorder=2)

if 'label' in df.columns:
    texts_d = [
        ax_D.text(row['composite_z'], row['virality_score'] or 0, row['label'], fontsize=7.5)
        for _, row in df.iterrows()
    ]
    if HAS_ADJUSTTEXT:
        adjust_text(texts_d, ax=ax_D,
                    arrowprops=dict(arrowstyle='-', color='#BBBBBB', lw=0.5))

legend_d = [
    Patch(facecolor=C_ABOVE, label=f'Neural score ≥ {COMPOSITE_POST_GATE}'),
    Patch(facecolor=C_BELOW, label=f'Neural score < {COMPOSITE_POST_GATE}'),
    Line2D([0], [0], color='#333333', linestyle='--', label='Post threshold'),
]
ax_D.legend(handles=legend_d, frameon=False, fontsize=8.5)
ax_D.set_xlabel('Composite Neural Score (z)', fontsize=11)
ax_D.set_ylabel('Virality Score (shares×3 + comments×2 + likes)', fontsize=11)
ax_D.set_title('D   Video Portfolio Map', fontweight='bold', pad=10, fontsize=12)

# ── Figure-level labels and export ───────────────────────────────────────────
fig.suptitle(
    'TRIBE v2 Neural Engagement Scores vs. Instagram Reels Performance\n'
    'Phase 1b Correlation Analysis',
    fontsize=15, fontweight='bold', y=0.990,
)
fig.text(
    0.5, 0.005,
    'TRIBE v2: Wubble et al. (2026) arXiv:2604.04025  ·  '
    'Berns et al. (2020) PNAS  ·  Scholz et al. (2017) PNAS',
    ha='center', fontsize=8.5, color='#666666', style='italic',
)

fig.savefig(FIGURE_MAIN_PNG, dpi=DPI, bbox_inches='tight')
fig.savefig(FIGURE_MAIN_PDF, bbox_inches='tight')
print(f'Saved: {FIGURE_MAIN_PNG}, {FIGURE_MAIN_PDF}')
plt.show()

# %% Cell 8 — Figure 2: Per-ROI Deep Dive (conditional)
# ─────────────────────────────────────────────────────────────────────────────
if not qualifying_rois:
    print(f'No ROIs exceeded |r| > {R_THRESHOLD}. Figure 2 skipped.')
else:
    target_engs = ['shares'] if not YOUTUBE_MODE else ['likes_per_view']
    n_cols = len(qualifying_rois)

    fig2, axes2 = plt.subplots(
        len(target_engs), n_cols,
        figsize=(4.5 * n_cols, 8),
        squeeze=False,
    )
    fig2.subplots_adjust(hspace=0.50, wspace=0.36, top=0.90, bottom=0.10)

    for col_i, roi in enumerate(qualifying_rois):
        for row_i, eng in enumerate(target_engs):
            ax   = axes2[row_i, col_i]
            y_e, y_lbl = _eng_y(eng)
            x_e  = df[f'{roi}_mean_z']
            mask = x_e.notna() & y_e.notna()
            xm, ym = x_e[mask].values, y_e[mask].values

            ax.scatter(xm, ym, color=C_POS, s=55, alpha=0.75,
                       edgecolors='white', linewidths=0.4, zorder=3)

            if len(xm) >= 4:
                xr2 = np.linspace(xm.min(), xm.max(), 100)
                yl2, clo2, chi2 = _ols_with_ci(xm, ym, xr2)
                ax.plot(xr2, yl2, color=C_POS, linewidth=1.8, zorder=4)
                ax.fill_between(xr2, clo2, chi2, alpha=0.14, color=C_POS)

            rv2 = r_matrix.loc[roi, eng]
            pv2 = p_matrix.loc[roi, eng]
            ax.text(0.05, 0.95, f'r = {rv2:.3f}\np = {pv2:.4f}',
                    transform=ax.transAxes, fontsize=9, va='top',
                    bbox=dict(boxstyle='round,pad=0.25', facecolor='white',
                              alpha=0.82, edgecolor='#CCCCCC'))

            title_str = f'{roi.capitalize()} vs. {eng.capitalize()}'
            if abs(rv2) > R_THRESHOLD:
                title_str += '  ✓'
            ax.set_title(title_str, fontsize=10, fontweight='bold', pad=7)
            ax.set_xlabel(f'{roi.capitalize()} Score (z)', fontsize=9.5)
            ax.set_ylabel(y_lbl, fontsize=9.5)

    fig2.suptitle(
        f'Figure 2 — Per-ROI Deep Dive (|r| > {R_THRESHOLD} with Saves or Shares)',
        fontsize=13, fontweight='bold',
    )
    fig2.text(0.5, 0.01, 'TRIBE v2: Wubble et al. (2026) arXiv:2604.04025',
              ha='center', fontsize=8.5, color='#666666', style='italic')

    fig2.savefig(FIGURE_DEEP_PNG, dpi=DPI, bbox_inches='tight')
    fig2.savefig(FIGURE_DEEP_PDF, bbox_inches='tight')
    print(f'Saved: {FIGURE_DEEP_PNG}, {FIGURE_DEEP_PDF}')
    plt.show()

# %% Cell 9 — Terminal Summary and Go/No-Go
# ─────────────────────────────────────────────────────────────────────────────
today = datetime.date.today().isoformat()

def _flag(r_val, threshold):
    return 'PASS ✓' if abs(r_val) >= threshold else 'FAIL ✗'

print('=' * 62)
print('  TRIBE-SOCIAL Phase 1b — Correlation Summary')
print(f'  Corpus: {N} videos  |  Date: {today}')
print('=' * 62)

print(f'\nROI Threshold Report (|r| > {R_THRESHOLD} with {PRIMARY_METRIC}):')
for roi in roi_labels:
    r_pm = r_matrix.loc[roi, PRIMARY_METRIC] if PRIMARY_METRIC in r_matrix.columns else np.nan
    print(f'  {roi:<12}  r_{PRIMARY_METRIC}={r_pm:+.3f}  [{_flag(abs(r_pm), R_THRESHOLD)}]')

print('\nComposite Model (target: r_{} > {:.2f}):'.format(PRIMARY_METRIC, COMPOSITE_THRESHOLD))
for eng in eng_labels:
    rc, pc = composite_r[eng], composite_p[eng]
    extra  = f'  [{_flag(rc, COMPOSITE_THRESHOLD)}]' if eng == PRIMARY_METRIC else ''
    print(f'  vs {eng:<20}  r={rc:+.3f}  p={pc:.4f}{extra}')

bonf_sig = [
    (roi, eng)
    for roi in roi_labels
    for eng in eng_labels
    if p_bonf.loc[roi, eng] < ALPHA
]
print(f'\nBonferroni-significant pairs (p < {ALPHA_BONF:.5f}):')
if bonf_sig:
    for roi, eng in bonf_sig:
        print(f'  {roi} × {eng}: r={r_matrix.loc[roi, eng]:.3f}, '
              f'p_bonf={p_bonf.loc[roi, eng]:.4f}')
else:
    print('  None  (expected with n < 50; interpret r magnitudes)')

print(f'\nSmall-N flag: {"YES" if USE_BOOTSTRAP else "NO"} (n = {N})')

# Verdict
composite_go   = abs(composite_r[PRIMARY_METRIC]) >= COMPOSITE_THRESHOLD
roi_pass_count = len(qualifying_rois)

if composite_go and roi_pass_count >= 2:
    verdict = 'GO'
    action  = (
        f'Proceed to Phase 2. Create content targeting '
        f'{", ".join(qualifying_rois)} ROIs. Score each draft before posting. '
        f'Track {PRIMARY_METRIC} per post to close the feedback loop.'
    )
elif roi_pass_count >= 1 and not composite_go:
    verdict = 'CONDITIONAL'
    action  = (
        f'Signal present in [{", ".join(qualifying_rois)}] but composite threshold '
        f'not met. Expand corpus to ≥ {max(30, N + 10)} videos and re-run.'
    )
else:
    verdict = 'NO-GO'
    action  = (
        f'Corpus too small or signal below threshold. '
        f'Collect ≥ 30 total videos (current: {N}) and re-run Phase 1b.'
    )

print(f'\n{"─" * 62}')
print(f'  RECOMMENDATION: {verdict}')
print(f'\n  Rationale:')
_r_pm = composite_r[PRIMARY_METRIC] if PRIMARY_METRIC in composite_r.index else float('nan')
print(f'    Composite r_{PRIMARY_METRIC} = {_r_pm:.3f}  '
      f'(threshold {COMPOSITE_THRESHOLD}) → {"met" if composite_go else "not met"}')
print(f'    {roi_pass_count}/{len(roi_labels)} ROIs exceed |r| > {R_THRESHOLD}')
if bonf_sig:
    print(f'    {len(bonf_sig)} Bonferroni-significant pair(s): {bonf_sig}')
print(f'\n  Phase 2 Action:')
print(f'    {action}')
print('=' * 62)

# %% Cell 10 — Write results to Alfred vault inbox
# ─────────────────────────────────────────────────────────────────────────────
_VAULT_INBOX = '/mnt/external/obsidian-vault/inbox'
_vault_path  = f'{_VAULT_INBOX}/tribe-social-phase1b-{today}.md'

_eng_cols = [c for c in [PRIMARY_METRIC, 'views', 'likes'] if c in r_matrix.columns]
_roi_table = '\n'.join(
    '| ' + roi + ' | ' +
    ' | '.join(f'{r_matrix.loc[roi, c]:+.3f}' for c in _eng_cols) +
    f' | {"✓" if roi in qualifying_rois else "—"} |'
    for roi in roi_labels
)

_bonf_lines = (
    '\n'.join(f'- {roi} × {eng}: r={r_matrix.loc[roi,eng]:.3f}, p_bonf={p_bonf.loc[roi,eng]:.4f}'
              for roi, eng in bonf_sig)
    if bonf_sig else '- None'
)

_vault_doc = f"""<!-- alfred:source tribe_social_phase1b -->
# tribe-social Phase 1b — Correlation Results
**Date:** {today}  |  **Corpus:** {N} videos  |  **Bootstrap CI:** {'yes' if USE_BOOTSTRAP else 'no'}

## ROI × Engagement Correlations (Pearson r)

| ROI | {' | '.join('r_' + c for c in _eng_cols)} | |r|>{R_THRESHOLD} |
|{'|'.join(['---'] * (len(_eng_cols) + 2))}|
{_roi_table}

## Composite Model

| Metric | r | p | Threshold met |
|---|---|---|---|
{''.join(f"| vs {eng:<20} | {composite_r[eng]:+.3f} | {composite_p[eng]:.4f} | {'yes' if abs(composite_r[eng]) >= COMPOSITE_THRESHOLD else 'no' if eng == PRIMARY_METRIC else '—'} |{chr(10)}" for eng in eng_labels if eng in composite_r.index)}

## Bonferroni-Significant Pairs (p < {ALPHA_BONF:.5f})

{_bonf_lines}

## Verdict: {verdict}

{action}

## Qualifying ROIs (for content targeting)

{', '.join(qualifying_rois) if qualifying_rois else 'None exceeded threshold'}

## Output Figures

- `{FIGURE_MAIN_PDF}` — 4-panel publishable figure (heatmap · scatter · hook bars · portfolio map)
- `{FIGURE_DEEP_PDF}` — Per-ROI deep dive ({"generated" if qualifying_rois else "skipped — no ROIs exceeded threshold"})

## Weights Used (update after this validation)

{chr(10).join(f'- {k}: {v}' for k, v in ROI_WEIGHTS.items())}
"""

import os
if os.path.isdir(_VAULT_INBOX):
    with open(_vault_path, 'w') as _f:
        _f.write(_vault_doc)
    print(f'\nVault report → {_vault_path}')
else:
    print(f'\nVault inbox not found at {_VAULT_INBOX} — skipping export.')
