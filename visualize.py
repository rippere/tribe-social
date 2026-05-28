"""
tribe-social — Content Visualization Pipeline

Static scorecards  (all outputs → content_output/):
  uv run python visualize.py --scorecard ali_005
  uv run python visualize.py --all-scorecards
  uv run python visualize.py --creator-grid huberman
  uv run python visualize.py --creator-grid all

Legacy aggregate outputs:
  uv run python visualize.py --compare
  uv run python visualize.py --hook-cta

Manim animation (single video):
  manim -pql visualize.py NeuralTimeline
  TRIBE_VIDEO_LABEL=huberman_007 manim -pqh visualize.py NeuralTimeline
"""

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from matplotlib.ticker import MaxNLocator
import matplotlib.patches as mpatches

SCORES_CSV     = "scores.csv"
ENGAGEMENT_CSV = "engagement.csv"
OUTPUT_DIR     = Path("content_output")

# Brand palette
C_ATTENTION = "#4FC3F7"
C_SOCIAL    = "#81C784"
C_VALUATION = "#FFB74D"
C_LANGUAGE  = "#CE93D8"
C_BG        = "#0D0D0D"
C_TEXT      = "#F0F0F0"
C_NEG       = "#EF9A9A"
C_PANEL     = "#111111"

ROI_COLORS = {
    "attention":  C_ATTENTION,
    "social":     C_SOCIAL,
    "valuation":  C_VALUATION,
    "language":   C_LANGUAGE,
    "auditory":   "#EF9A9A",
    "motion":     "#80DEEA",
    "narrative":  "#FFCC80",
}

ROI_LABELS = {
    "attention":  "Attention (IFJa)",
    "social":     "Social Cognition (TPJ)",
    "valuation":  "Valuation / Save Signal (vmPFC)",
    "language":   "Language (Broca)",
    "auditory":   "Auditory (STS)",
    "motion":     "Motion (MT/V5)",
    "narrative":  "Narrative (DMN)",
}

ALL_ROIS  = ["attention", "social", "valuation", "language", "auditory", "motion", "narrative"]
KEY_ROIS  = ["attention", "social", "valuation", "language"]
RADAR_SHORT = {
    "attention": "Attn", "social": "Social", "valuation": "Value",
    "language": "Lang", "auditory": "Audio", "motion": "Motion", "narrative": "Narr",
}


# ---------------------------------------------------------------------------
# Data loading & normalization
# ---------------------------------------------------------------------------

def normalize_df(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["creator"] = df["filename"].str.extract(r"^([a-z]+)_")

    # 0–100 composite score (corpus min-max)
    mn, mx = df["composite_raw"].min(), df["composite_raw"].max()
    df["score_100"] = ((df["composite_raw"] - mn) / (mx - mn + 1e-9) * 100).round(1)

    # Per-ROI corpus-normalized 0–1 for radar
    for roi in ALL_ROIS:
        col = f"{roi}_mean"
        r_mn, r_mx = df[col].min(), df[col].max()
        df[f"{roi}_norm"] = (df[col] - r_mn) / (r_mx - r_mn + 1e-9)

    # Within-creator rank (1 = best)
    df["creator_rank"] = (
        df.groupby("creator")["composite_raw"]
        .rank(ascending=False)
        .astype(int)
    )
    df["creator_n"] = df.groupby("creator")["creator"].transform("count")
    return df


def load_scores() -> pd.DataFrame:
    df = pd.read_csv(SCORES_CSV)
    df.columns = df.columns.str.strip()
    return normalize_df(df)


def load_engagement() -> pd.DataFrame | None:
    p = Path(ENGAGEMENT_CSV)
    if not p.exists():
        return None
    eng = pd.read_csv(p)
    eng.columns = eng.columns.str.strip()
    return eng


def load_npy(label: str) -> np.ndarray | None:
    p = Path("reels") / f"{label}_preds.npy"
    return np.load(p) if p.exists() else None


def get_top_bottom(df: pd.DataFrame, metric: str = "composite_raw") -> tuple[str, str]:
    top    = df.loc[df[metric].idxmax(), "filename"].replace(".mp4", "")
    bottom = df.loc[df[metric].idxmin(), "filename"].replace(".mp4", "")
    return top, bottom


def _gate(score_100: float) -> tuple[str, str]:
    if score_100 >= 65:
        return C_ATTENTION, "POST IT"
    elif score_100 >= 40:
        return C_VALUATION, "REVISE"
    return C_NEG, "RETHINK"


# ---------------------------------------------------------------------------
# Signal interpreter  (plain-English, within-creator context)
# ---------------------------------------------------------------------------

def interpret_signals(row: pd.Series, df: pd.DataFrame) -> list[str]:
    creator = row["creator"]
    c_df    = df[df["creator"] == creator]

    def c_pct(col: str) -> float:
        vals = c_df[col].values
        return float(np.mean(vals <= row[col]) * 100)

    signals: list[str] = []

    # Hook strength (attention)
    hook_ratio = row["attention_hook"] / (abs(row["attention_mean"]) + 1e-9)
    if hook_ratio > 1.15:
        signals.append(
            f"Strong hook — attention +{(hook_ratio - 1) * 100:.0f}% above average in first 3s"
        )
    elif hook_ratio < 0.85 and row["attention_mean"] > 0:
        signals.append("Weak hook — opens cold, consider front-loading visual or verbal hook")

    # Social signal
    soc_pct = c_pct("social_mean")
    if soc_pct >= 75:
        signals.append("High social cognition (TPJ) — topic activates sharing behaviour")
    elif soc_pct <= 25:
        signals.append("Low social signal — topic may not drive organic sharing")

    # Valuation / save
    val_pct = c_pct("valuation_mean")
    if val_pct >= 75:
        signals.append("Elevated save signal (vmPFC) — content perceived as high-value")
    elif val_pct <= 25:
        signals.append("Low save signal — add more actionable or value-dense content")

    # Narrative
    if c_pct("narrative_mean") >= 75:
        signals.append("Strong narrative arc (DMN) — story structure is working")

    # Score vs creator median
    median_score = float(c_df["score_100"].median())
    delta        = row["score_100"] - median_score
    if abs(delta) >= 10:
        direction = "above" if delta > 0 else "below"
        signals.append(
            f"{abs(delta):.0f} pts {direction} {creator.title()}'s median neural score"
        )

    return signals[:3]


# ---------------------------------------------------------------------------
# Per-video scorecard
# ---------------------------------------------------------------------------

def make_scorecard(label: str, df: pd.DataFrame, eng_df: pd.DataFrame | None = None) -> Path:
    OUTPUT_DIR.mkdir(exist_ok=True)
    row = df[df["filename"] == f"{label}.mp4"].iloc[0]

    creator    = row["creator"]
    score_100  = float(row["score_100"])
    rank       = int(row["creator_rank"])
    n_creator  = int(row["creator_n"])
    duration   = int(row["n_seconds"])
    gate_color, gate_word = _gate(score_100)

    fig = plt.figure(figsize=(15, 8), facecolor=C_BG)

    # ── Header ──────────────────────────────────────────────────────────────
    header_left = f"{label}   ·   {creator.title()}   ·   {duration}s"
    header_right = f"#{rank} of {n_creator}  {creator.title()} videos"

    if eng_df is not None:
        e = eng_df[eng_df["filename"] == f"{label}.mp4"]
        if not e.empty:
            views = int(e["views"].values[0])
            likes = int(e["likes"].values[0])
            lpr   = likes / max(views, 1)
            header_left += f"   ·   {views:,} views   ·   {lpr:.1%} likes/view"

    fig.text(0.03, 0.97, header_left,
             color=C_TEXT, fontsize=11, va="top", weight="bold")
    fig.text(0.97, 0.97, header_right,
             color="#888888", fontsize=10, va="top", ha="right")
    fig.text(0.5, 0.97, "TRIBE v2 Brain Encoding — Content Scorecard",
             color="#444444", fontsize=9, va="top", ha="center", style="italic")

    # ── LEFT: Brain fingerprint radar ───────────────────────────────────────
    n_rois  = len(ALL_ROIS)
    angles  = np.linspace(0, 2 * np.pi, n_rois, endpoint=False).tolist()
    angles += angles[:1]

    c_df = df[df["creator"] == creator]
    values  = [float(row[f"{r}_norm"]) for r in ALL_ROIS] + [float(row[f"{ALL_ROIS[0]}_norm"])]
    c_med   = [float(c_df[f"{r}_norm"].median()) for r in ALL_ROIS]
    c_med  += [c_med[0]]
    corp_med = [float(df[f"{r}_norm"].median()) for r in ALL_ROIS]
    corp_med += [corp_med[0]]

    ax_r = fig.add_axes([0.04, 0.10, 0.32, 0.78], projection="polar",
                        facecolor="#141414")
    ax_r.set_theta_offset(np.pi / 2)
    ax_r.set_theta_direction(-1)
    ax_r.set_xticks(angles[:-1])
    ax_r.set_xticklabels(
        [RADAR_SHORT[r] for r in ALL_ROIS],
        color=C_TEXT, fontsize=9.5,
    )
    ax_r.set_yticks([0.25, 0.5, 0.75])
    ax_r.set_yticklabels([])
    ax_r.yaxis.set_tick_params(labelleft=False)
    ax_r.set_ylim(0, 1)
    ax_r.grid(color="#2A2A2A", linewidth=0.9)
    ax_r.spines["polar"].set_color("#2A2A2A")

    # Corpus median reference (thin grey)
    ax_r.plot(angles, corp_med, color="#333333", linewidth=1, linestyle=":", zorder=1)
    # Creator median (dashed)
    ax_r.plot(angles, c_med, color="#555555", linewidth=1.2, linestyle="--", zorder=2)
    # This video (filled)
    ax_r.plot(angles, values, color=gate_color, linewidth=2, zorder=3)
    ax_r.fill(angles, values, alpha=0.22, color=gate_color)

    # Legend inside radar
    ax_r.text(0, 1.38, "Brain Fingerprint", color="#666666", fontsize=9,
              ha="center", transform=ax_r.transAxes)
    ax_r.text(0, -0.08,
              "── this video   -- creator avg   ·· corpus avg",
              color="#555555", fontsize=7.5, ha="center", transform=ax_r.transAxes)

    # ── MIDDLE: Hook / Mean / Offset bars ───────────────────────────────────
    ax_b = fig.add_axes([0.40, 0.12, 0.30, 0.74], facecolor=C_BG)

    y = np.arange(len(KEY_ROIS))
    h = 0.20

    for i, roi in enumerate(KEY_ROIS):
        hook_v = float(row[f"{roi}_hook"])
        mean_v = float(row[f"{roi}_mean"])
        off_v  = float(row[f"{roi}_offset"])
        color  = ROI_COLORS[roi]

        ax_b.barh(y[i] + h,  hook_v, h * 0.88, color=color, alpha=0.95,
                  label="Hook (0–3s)" if i == 0 else "")
        ax_b.barh(y[i],      mean_v, h * 0.88, color=color, alpha=0.50,
                  label="Mean" if i == 0 else "")
        ax_b.barh(y[i] - h,  off_v,  h * 0.88, color=color, alpha=0.28,
                  label="Offset (last 5s)" if i == 0 else "")

        # Annotate hook vs mean direction
        delta = hook_v - mean_v
        sym   = "▲" if delta > 0 else "▼"
        sym_c = C_SOCIAL if delta > 0 else C_NEG
        max_v = max(abs(hook_v), abs(mean_v), abs(off_v), 1e-9)
        ax_b.text(max_v * 1.12, y[i] + h,
                  f"{sym} {abs(delta / (abs(mean_v) + 1e-9)) * 100:.0f}%",
                  color=sym_c, fontsize=8, va="center")

    ax_b.set_yticks(y)
    ax_b.set_yticklabels(
        ["Attention", "Social", "Valuation", "Language"],
        color=C_TEXT, fontsize=10,
    )
    ax_b.tick_params(left=False, bottom=False, colors=C_TEXT)
    ax_b.spines[:].set_visible(False)
    ax_b.xaxis.set_visible(False)
    ax_b.set_title("Hook  ·  Mean  ·  Offset", color="#888888", fontsize=9, pad=8)

    legend_patches = [
        mpatches.Patch(color="#AAAAAA", alpha=0.95, label="Hook (0–3s)"),
        mpatches.Patch(color="#AAAAAA", alpha=0.50, label="Mean"),
        mpatches.Patch(color="#AAAAAA", alpha=0.28, label="Offset (last 5s)"),
    ]
    ax_b.legend(handles=legend_patches, loc="lower right",
                facecolor="#1A1A1A", labelcolor=C_TEXT,
                fontsize=8, edgecolor="none", framealpha=0.8)

    # ── RIGHT: Score panel ───────────────────────────────────────────────────
    ax_s = fig.add_axes([0.73, 0.12, 0.24, 0.74], facecolor=C_PANEL)
    ax_s.set_xlim(0, 1)
    ax_s.set_ylim(0, 1)
    ax_s.set_axis_off()

    # Big score
    ax_s.text(0.5, 0.93, f"{score_100:.0f}",
              color=gate_color, fontsize=56, ha="center", va="top",
              weight="bold", family="Liberation Sans")
    ax_s.text(0.5, 0.74, "/ 100  Neural Score",
              color="#555555", fontsize=10, ha="center", va="top")
    ax_s.text(0.5, 0.66, gate_word,
              color=gate_color, fontsize=18, ha="center", va="top", weight="bold")

    ax_s.axhline(0.60, xmin=0.05, xmax=0.95, color="#222222", linewidth=1)

    # Key metrics
    coupling  = float(row["vmPFC_TPJ_coupling"])
    peak_val  = int(row["valuation_peak_s"])
    pi_val    = float(row["pleasantness_index"])
    gfp       = float(row["gfp_mean"])
    ts_ratio  = float(row["attention_ts_ratio"])

    def metric_row(y_pos: float, label_m: str, val_str: str, good: bool):
        ax_s.text(0.10, y_pos, label_m,
                  color="#777777", fontsize=9, va="top")
        ax_s.text(0.92, y_pos, val_str,
                  color=C_SOCIAL if good else C_NEG, fontsize=10,
                  ha="right", va="top", weight="bold")

    metric_row(0.57, "Virality Circuit",    f"{coupling:.2f}",      coupling > 0.5)
    metric_row(0.47, "Save Peak",           f"@ {peak_val}s",       True)
    metric_row(0.37, "Cortical Energy",     f"{gfp:.4f}",           gfp > float(df["gfp_mean"].median()))
    metric_row(0.27, "Hook Transience",     f"{ts_ratio:.2f}×",     ts_ratio > 1.0)
    metric_row(0.17, "LH Frontal Bias",     f"{pi_val:+.4f}",       pi_val > 0)

    # ── Footer signals ───────────────────────────────────────────────────────
    signals = interpret_signals(row, df)
    for i, sig in enumerate(signals):
        prefix = "● " if i == 0 else "  "
        fig.text(0.03, 0.07 - i * 0.04, prefix + sig,
                 color="#777777" if i > 0 else "#AAAAAA",
                 fontsize=9, va="top", style="italic")

    out = OUTPUT_DIR / f"scorecard_{label}.png"
    fig.savefig(out, dpi=150, bbox_inches="tight", facecolor=C_BG)
    plt.close(fig)
    print(f"Saved: {out}")
    return out


# ---------------------------------------------------------------------------
# Creator overview grid  (all 8 videos ranked, mini ROI bars)
# ---------------------------------------------------------------------------

def make_creator_grid(creator: str, df: pd.DataFrame, eng_df: pd.DataFrame | None = None) -> Path:
    OUTPUT_DIR.mkdir(exist_ok=True)
    c_df = (
        df[df["creator"] == creator]
        .sort_values("score_100", ascending=False)
        .reset_index(drop=True)
    )

    fig, axes = plt.subplots(2, 4, figsize=(18, 9), facecolor=C_BG)
    fig.suptitle(
        f"{creator.title()} — All {len(c_df)} Videos Ranked by Neural Score",
        color=C_TEXT, fontsize=14, fontweight="bold", y=0.99,
    )

    for idx, ax in enumerate(axes.flat):
        ax.set_facecolor(C_PANEL)
        if idx >= len(c_df):
            ax.set_visible(False)
            continue

        row       = c_df.iloc[idx]
        label     = row["filename"].replace(".mp4", "")
        score_100 = float(row["score_100"])
        gate_color, gate_word = _gate(score_100)

        # ROI horizontal bars (all 7, normalized within corpus)
        rois   = ALL_ROIS
        values = [float(row[f"{r}_norm"]) for r in rois]
        colors = [ROI_COLORS[r] for r in rois]
        y      = np.arange(len(rois))

        ax.barh(y, values, color=colors, alpha=0.82, height=0.6)
        ax.set_xlim(0, 1.25)
        ax.set_yticks(y)
        ax.set_yticklabels(
            [RADAR_SHORT[r] for r in rois],
            color="#AAAAAA", fontsize=8,
        )
        ax.tick_params(left=False, bottom=False, colors=C_TEXT)
        ax.spines[:].set_visible(False)
        ax.xaxis.set_visible(False)

        # Score badge (right side)
        ax.text(1.20, len(rois) / 2, f"{score_100:.0f}",
                color=gate_color, fontsize=18, ha="center", va="center",
                weight="bold", transform=ax.transData)
        ax.text(1.20, -0.8, gate_word,
                color=gate_color, fontsize=7, ha="center", va="bottom",
                weight="bold", transform=ax.transData)

        # Title: rank + label
        rank_str = f"#{idx + 1}"
        ax.set_title(f"{rank_str}  {label}", color=C_TEXT, fontsize=10,
                     fontweight="bold", pad=6)

        # Engagement sub-text
        if eng_df is not None:
            e = eng_df[eng_df["filename"] == row["filename"]]
            if not e.empty:
                views = int(e["views"].values[0])
                likes = int(e["likes"].values[0])
                lpr   = likes / max(views, 1)
                v_str = f"{views // 1000}K" if views >= 1000 else str(views)
                ax.text(0.50, -0.18, f"{v_str} views · {lpr:.1%} L/V",
                        color="#666666", fontsize=7.5, ha="center", va="top",
                        transform=ax.transAxes)

        # Hook indicator dot (green = strong hook, red = weak)
        hook_r = row["attention_hook"] / (abs(row["attention_mean"]) + 1e-9)
        hc = C_SOCIAL if hook_r > 1.1 else (C_NEG if hook_r < 0.9 else "#888888")
        ax.text(0.97, 0.97, "●", color=hc, fontsize=9,
                ha="right", va="top", transform=ax.transAxes)

    # Legend strip at bottom
    legend_txt = (
        "Bar width = corpus-normalized ROI activation   "
        "● top-right = hook strength  (green = strong, red = weak)   "
        "Score = 0–100 corpus-relative"
    )
    fig.text(0.5, 0.005, legend_txt,
             color="#444444", fontsize=8, ha="center", va="bottom", style="italic")

    plt.subplots_adjust(left=0.04, right=0.96, top=0.93,
                        bottom=0.06, hspace=0.55, wspace=0.50)

    out = OUTPUT_DIR / f"creator_grid_{creator}.png"
    fig.savefig(out, dpi=150, bbox_inches="tight", facecolor=C_BG)
    plt.close(fig)
    print(f"Saved: {out}")
    return out


# ---------------------------------------------------------------------------
# Legacy: Static Comparison Figure
# ---------------------------------------------------------------------------

def make_comparison_figure(top_label: str, bottom_label: str, df: pd.DataFrame):
    OUTPUT_DIR.mkdir(exist_ok=True)
    top_row = df[df["filename"] == f"{top_label}.mp4"].iloc[0]
    bot_row = df[df["filename"] == f"{bottom_label}.mp4"].iloc[0]

    rois   = list(ROI_COLORS.keys())
    top_v  = [top_row[f"{r}_mean"] for r in rois]
    bot_v  = [bot_row[f"{r}_mean"] for r in rois]
    colors = [ROI_COLORS[r] for r in rois]
    labels = [ROI_LABELS[r] for r in rois]

    fig, axes = plt.subplots(1, 2, figsize=(9, 16), facecolor=C_BG)
    fig.subplots_adjust(left=0.02, right=0.98, top=0.88, bottom=0.14, wspace=0.06)

    for ax, values, lbl, marker, row in [
        (axes[0], top_v, top_label, "▲ Higher engagement", top_row),
        (axes[1], bot_v, bottom_label, "▼ Lower engagement", bot_row),
    ]:
        ax.set_facecolor(C_BG)
        bars = ax.barh(labels, values, color=colors, alpha=0.85,
                       edgecolor="none", height=0.65)
        for bar, val in zip(bars, values):
            ax.text(val + 0.0005, bar.get_y() + bar.get_height() / 2,
                    f"{val:.4f}", va="center", ha="left",
                    fontsize=8, color=C_TEXT, alpha=0.7)
        ax.set_xlim(0, max(max(top_v), max(bot_v)) * 1.25)
        ax.set_xlabel("Mean ROI Activation", color=C_TEXT, fontsize=10)
        ax.tick_params(colors=C_TEXT, labelsize=9)
        ax.spines[:].set_visible(False)
        for lab in ax.get_yticklabels():
            lab.set_color(C_TEXT)
        ax.set_title(
            f"{lbl}\nNeural Score: {row['score_100']:.0f}/100",
            color=C_TEXT, fontsize=11, fontweight="bold", pad=10,
        )
        ax.text(0.98, -0.06, marker, transform=ax.transAxes,
                ha="right", va="top", fontsize=9,
                color=C_ATTENTION if "▲" in marker else C_NEG)

    fig.suptitle("Brain Activation: High vs Low Engagement\nTRIBE v2 Neural Scores",
                 color=C_TEXT, fontsize=14, fontweight="bold", y=0.93)
    fig.text(0.5, 0.02,
             "vmPFC = valuation / save signal  ·  TPJ = social / share signal",
             ha="center", fontsize=9, color=C_TEXT, alpha=0.6, style="italic")

    out = OUTPUT_DIR / f"compare_{top_label}_vs_{bottom_label}.png"
    fig.savefig(out, dpi=200, bbox_inches="tight", facecolor=C_BG)
    plt.close(fig)
    print(f"Saved: {out}")
    return out


# ---------------------------------------------------------------------------
# Legacy: Hook–CTA Window Figure
# ---------------------------------------------------------------------------

def make_hook_cta_figure(df: pd.DataFrame):
    OUTPUT_DIR.mkdir(exist_ok=True)
    hook_vals   = {r: df[f"{r}_hook"].mean()   for r in KEY_ROIS}
    offset_vals = {r: df[f"{r}_offset"].mean() for r in KEY_ROIS}
    mean_vals   = {r: df[f"{r}_mean"].mean()   for r in KEY_ROIS}

    x = np.arange(len(KEY_ROIS))
    w = 0.28

    fig, ax = plt.subplots(figsize=(9, 5), facecolor=C_BG)
    ax.set_facecolor(C_BG)
    ax.bar(x - w, [hook_vals[r]   for r in KEY_ROIS], w,
           label="Hook (0–3s)",   color=[ROI_COLORS[r] for r in KEY_ROIS], alpha=0.95)
    ax.bar(x,     [mean_vals[r]   for r in KEY_ROIS], w,
           label="Mean",          color=[ROI_COLORS[r] for r in KEY_ROIS], alpha=0.5)
    ax.bar(x + w, [offset_vals[r] for r in KEY_ROIS], w,
           label="Offset (last 5s)", color=[ROI_COLORS[r] for r in KEY_ROIS], alpha=0.7,
           hatch="//", edgecolor=C_BG)
    ax.set_xticks(x)
    ax.set_xticklabels([ROI_LABELS[r].split(" ")[0] for r in KEY_ROIS],
                       color=C_TEXT, fontsize=11)
    ax.set_ylabel("Mean Activation", color=C_TEXT, fontsize=10)
    ax.tick_params(colors=C_TEXT)
    ax.spines[:].set_color("#333333")
    ax.legend(facecolor="#1A1A1A", labelcolor=C_TEXT, fontsize=9,
              edgecolor="none", loc="upper right")
    ax.set_title("Hook vs Offset Window Activation — Corpus Average",
                 color=C_TEXT, fontsize=13, fontweight="bold", pad=12)
    ax.yaxis.set_major_locator(MaxNLocator(5))

    out = OUTPUT_DIR / "hook_cta_window.png"
    fig.savefig(out, dpi=200, bbox_inches="tight", facecolor=C_BG)
    plt.close(fig)
    print(f"Saved: {out}")
    return out


# ---------------------------------------------------------------------------
# Manim Animation — Neural Timeline
# ---------------------------------------------------------------------------

try:
    from manim import *

    _LEGEND_LABELS = {
        "attention": "Attention",
        "valuation": "Save Signal",
        "social":    "Social",
        "language":  "Language",
    }

    class NeuralTimeline(Scene):
        """
        Animated neural activation timeline for a single video.
        Usage:
            manim -pql visualize.py NeuralTimeline
            TRIBE_VIDEO_LABEL=huberman_007 manim -pqh visualize.py NeuralTimeline
        """

        def construct(self):
            import os
            label = os.environ.get("TRIBE_VIDEO_LABEL", None)

            try:
                df = load_scores()
                if label is None:
                    label, _ = get_top_bottom(df)
                    print(f"Auto-selected top video: {label}")
                row = df[df["filename"] == f"{label}.mp4"].iloc[0]
            except Exception as e:
                print(f"Could not load scores.csv: {e}")
                label = "demo"
                row   = None

            preds  = load_npy(label)
            n_secs = int(row["n_seconds"]) if row is not None else 30

            if preds is not None:
                from run_and_save import _BATCH_MASKS
                curves = {}
                for roi in KEY_ROIS:
                    idx = _BATCH_MASKS[roi]
                    ts  = preds[:, idx].mean(axis=1)
                    mn, mx = ts.min(), ts.max()
                    curves[roi] = (ts - mn) / (mx - mn + 1e-9)
            else:
                rng = np.random.default_rng(42)
                t   = np.linspace(0, 1, n_secs)
                curves = {}
                for roi in KEY_ROIS:
                    hook   = 0.7 if row is None else float(row[f"{roi}_hook"])
                    mid    = 0.4 if row is None else float(row[f"{roi}_mean"])
                    offset = 0.6 if row is None else float(row[f"{roi}_offset"])
                    base   = np.interp(t, [0, 0.15, 0.75, 1.0],
                                       [hook, mid * 0.8, mid, offset])
                    raw    = np.clip(base + rng.normal(0, 0.03, n_secs), 0, 1)
                    mn, mx = raw.min(), raw.max()
                    curves[roi] = (raw - mn) / (mx - mn + 1e-9)

            self.camera.background_color = ManimColor(C_BG)

            creator  = label.split("_")[0].title()
            title    = Text(creator, font="Liberation Sans", font_size=34,
                            color=ManimColor(C_TEXT), weight=BOLD)
            subtitle = Text("Brain Activity  ·  TRIBE v2 Neural Encoding",
                            font="Liberation Sans", font_size=16,
                            color=ManimColor("#777777"))
            header = VGroup(title, subtitle).arrange(DOWN, aligned_edge=LEFT, buff=0.12)
            header.to_corner(UL, buff=0.45)
            self.play(FadeIn(header, shift=DOWN * 0.15), run_time=0.5)

            step = max(5, n_secs // 6)
            axes = Axes(
                x_range=[0, n_secs, step],
                y_range=[0, 1.05, 1.0],
                x_length=11.5,
                y_length=4.2,
                axis_config={
                    "color":            ManimColor("#444444"),
                    "include_tip":      False,
                    "stroke_width":     1.5,
                    "label_constructor": Text,
                },
                x_axis_config={
                    "numbers_to_include": np.arange(0, n_secs + 1, step),
                    "font_size": 18,
                },
                y_axis_config={"numbers_to_include": []},
            ).move_to([0, -0.25, 0])

            x_unit = Text("sec", font_size=14, color=ManimColor("#555555"))
            x_unit.next_to(axes.x_axis.get_right(), RIGHT, buff=0.12)
            self.play(Create(axes), FadeIn(x_unit), run_time=0.7)

            hook_end     = min(3, n_secs - 1)
            offset_start = max(n_secs - 5, hook_end + 1)

            hook_rect = axes.get_area(
                axes.plot(lambda x: 1.02, x_range=[0, hook_end]),
                x_range=[0, hook_end],
                color=ManimColor(C_ATTENTION), opacity=0.12,
            )
            cta_rect = axes.get_area(
                axes.plot(lambda x: 1.02, x_range=[offset_start, n_secs]),
                x_range=[offset_start, n_secs],
                color=ManimColor(C_VALUATION), opacity=0.12,
            )
            hook_lbl = Text("HOOK", font_size=11, color=ManimColor(C_ATTENTION), weight=BOLD)
            hook_lbl.move_to(axes.c2p(hook_end / 2, 0.97))
            cta_lbl  = Text("CTA", font_size=11, color=ManimColor(C_VALUATION), weight=BOLD)
            cta_lbl.move_to(axes.c2p((offset_start + n_secs) / 2, 0.97))
            self.play(FadeIn(hook_rect), FadeIn(cta_rect),
                      FadeIn(hook_lbl), FadeIn(cta_lbl), run_time=0.4)

            for roi in KEY_ROIS:
                ts     = curves[roi]
                color  = ManimColor(ROI_COLORS[roi])
                points = [axes.c2p(i, float(ts[i])) for i in range(n_secs)]
                curve  = VMobject(color=color, stroke_width=2.8)
                curve.set_points_smoothly(points)
                self.play(Create(curve), run_time=1.1)

            val_ts  = curves["valuation"]
            peak_s  = int(val_ts.argmax())
            px      = axes.c2p(peak_s, 0)[0]
            py_bot  = axes.c2p(0, 0)[1]
            py_top  = axes.c2p(0, float(val_ts[peak_s]))[1]
            peak_line = DashedLine(
                [px, py_bot, 0], [px, py_top, 0],
                color=ManimColor(C_VALUATION), stroke_width=1.8, dash_length=0.1,
            )
            callout = Text(f"save signal\n@ {peak_s}s",
                           font="Liberation Sans", font_size=13,
                           color=ManimColor(C_VALUATION), line_spacing=0.85)
            callout.next_to([px, py_top, 0], UP, buff=0.14)
            self.play(Create(peak_line), FadeIn(callout), run_time=0.6)

            items = []
            for roi in KEY_ROIS:
                pip = Dot(color=ManimColor(ROI_COLORS[roi]), radius=0.09)
                lbl = Text(_LEGEND_LABELS[roi], font_size=15, color=ManimColor(C_TEXT))
                items.append(VGroup(pip, lbl).arrange(RIGHT, buff=0.14))
            legend = VGroup(*items).arrange(RIGHT, buff=0.55)
            legend.next_to(axes, DOWN, buff=0.35)
            self.play(FadeIn(legend), run_time=0.4)
            self.wait(1.5)

            score_100   = float(row["score_100"]) if row is not None else 0.0
            gate_color_m, gate_word = _gate(score_100)
            score_big   = Text(f"{score_100:.0f}", font_size=88,
                               color=ManimColor(gate_color_m), weight=BOLD)
            score_denom = Text("/ 100  Neural Score", font_size=22,
                               color=ManimColor("#888888"))
            gate_badge  = Text(gate_word, font_size=32,
                               color=ManimColor(gate_color_m), weight=BOLD)
            card = VGroup(score_big, score_denom, gate_badge).arrange(DOWN, buff=0.28)

            self.play(*[FadeOut(m) for m in self.mobjects], run_time=0.7)
            self.play(FadeIn(card, scale=0.92), run_time=0.65)
            self.wait(2.5)

except ImportError:
    pass


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scorecard",      metavar="LABEL",
                        help="Full scorecard for one video  (e.g. ali_005)")
    parser.add_argument("--all-scorecards", action="store_true",
                        help="Generate a scorecard for every video in scores.csv")
    parser.add_argument("--creator-grid",   metavar="CREATOR",
                        help="Ranked grid for one creator, or 'all' for all creators")
    parser.add_argument("--compare",        action="store_true",
                        help="Legacy: high vs low composite bar chart")
    parser.add_argument("--hook-cta",       action="store_true",
                        help="Legacy: corpus-average hook/offset bar chart")
    parser.add_argument("--top",            default=None)
    parser.add_argument("--bottom",         default=None)
    args = parser.parse_args()

    if not Path(SCORES_CSV).exists():
        print("scores.csv not found — run TRIBE v2 batch first.")
        sys.exit(1)

    df     = load_scores()
    eng_df = load_engagement()

    if args.scorecard:
        make_scorecard(args.scorecard, df, eng_df)

    elif args.all_scorecards:
        labels = df["filename"].str.replace(".mp4", "", regex=False).tolist()
        print(f"Generating {len(labels)} scorecards …")
        for lbl in labels:
            make_scorecard(lbl, df, eng_df)

    elif args.creator_grid:
        creators = (
            df["creator"].unique().tolist()
            if args.creator_grid == "all"
            else [args.creator_grid]
        )
        for c in creators:
            make_creator_grid(c, df, eng_df)

    elif args.compare:
        top, bottom = get_top_bottom(df)
        if args.top:    top    = args.top
        if args.bottom: bottom = args.bottom
        make_comparison_figure(top, bottom, df)

    elif args.hook_cta:
        make_hook_cta_figure(df)

    else:
        # Default: generate everything
        print("Generating all scorecards + creator grids …")
        for lbl in df["filename"].str.replace(".mp4", "", regex=False):
            make_scorecard(lbl, df, eng_df)
        for c in df["creator"].unique():
            make_creator_grid(c, df, eng_df)


if __name__ == "__main__":
    main()
