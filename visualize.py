"""
tribe-social — Content Visualization Pipeline

Generates two outputs from scores.csv:

  1. Neural Timeline Animation (Manim)
     manim -pql visualize.py NeuralTimeline
     manim -pqh visualize.py NeuralTimeline   ← high quality for publishing

  2. Static Comparison Figure (matplotlib)
     uv run python visualize.py --compare
     uv run python visualize.py --compare --top huberman_007 --bottom huberman_006

Both are designed for 9:16 vertical (Reels/Shorts format).
"""

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from matplotlib.ticker import MaxNLocator

SCORES_CSV     = "scores.csv"
ENGAGEMENT_CSV = "engagement.csv"
OUTPUT_DIR     = Path("content_output")

# Brand palette
C_ATTENTION = "#4FC3F7"   # blue   — IFJa/IFJp attention
C_SOCIAL    = "#81C784"   # green  — TPJ social cognition
C_VALUATION = "#FFB74D"   # amber  — vmPFC valuation (save signal)
C_LANGUAGE  = "#CE93D8"   # purple — language / Broca
C_BG        = "#0D0D0D"   # near-black background
C_TEXT      = "#F0F0F0"

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

KEY_ROIS = ["attention", "valuation", "social", "language"]


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def load_scores() -> pd.DataFrame:
    df = pd.read_csv(SCORES_CSV)
    df.columns = df.columns.str.strip()
    return df


def load_npy(label: str) -> np.ndarray | None:
    """Load per-second prediction array for a video."""
    p = Path("reels") / f"{label}_preds.npy"
    if p.exists():
        return np.load(p)
    return None


def get_top_bottom(df: pd.DataFrame, metric: str = "composite_raw") -> tuple[str, str]:
    top    = df.loc[df[metric].idxmax(), "filename"].replace(".mp4", "")
    bottom = df.loc[df[metric].idxmin(), "filename"].replace(".mp4", "")
    return top, bottom


# ---------------------------------------------------------------------------
# Static Comparison Figure
# ---------------------------------------------------------------------------

def make_comparison_figure(top_label: str, bottom_label: str, df: pd.DataFrame):
    """
    Side-by-side bar chart comparing ROI scores for two videos.
    Dark background, 9:16 crop-friendly.
    """
    OUTPUT_DIR.mkdir(exist_ok=True)

    top_row = df[df["filename"] == f"{top_label}.mp4"].iloc[0]
    bot_row = df[df["filename"] == f"{bottom_label}.mp4"].iloc[0]

    rois   = list(ROI_COLORS.keys())
    top_v  = [top_row[f"{r}_mean"] for r in rois]
    bot_v  = [bot_row[f"{r}_mean"] for r in rois]
    colors = [ROI_COLORS[r] for r in rois]
    labels = [ROI_LABELS[r] for r in rois]

    fig, axes = plt.subplots(1, 2, figsize=(9, 16), facecolor=C_BG)
    fig.subplots_adjust(left=0.02, right=0.98, top=0.88, bottom=0.14,
                        wspace=0.06)

    for ax, values, title_label, marker in [
        (axes[0], top_v,  top_label,    "▲ Higher engagement"),
        (axes[1], bot_v,  bottom_label, "▼ Lower engagement"),
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
        ax.xaxis.label.set_color(C_TEXT)
        for label in ax.get_yticklabels():
            label.set_color(C_TEXT)

        top_score = top_row["composite_raw"] if marker.startswith("▲") else bot_row["composite_raw"]
        ax.set_title(
            f"{title_label}\nNeural Score: {top_score:.1f}",
            color=C_TEXT, fontsize=11, fontweight="bold", pad=10,
        )
        ax.text(0.98, -0.06, marker, transform=ax.transAxes,
                ha="right", va="top", fontsize=9,
                color=C_ATTENTION if "▲" in marker else "#EF9A9A")

    fig.suptitle(
        "Brain Activation: High vs Low Engagement\n"
        "TRIBE v2 Neural Scores",
        color=C_TEXT, fontsize=14, fontweight="bold", y=0.93,
    )
    fig.text(0.5, 0.02,
             "vmPFC = valuation / save signal  ·  TPJ = social / share signal",
             ha="center", fontsize=9, color=C_TEXT, alpha=0.6, style="italic")

    out = OUTPUT_DIR / f"compare_{top_label}_vs_{bottom_label}.png"
    fig.savefig(out, dpi=200, bbox_inches="tight", facecolor=C_BG)
    print(f"Saved: {out}")
    plt.close(fig)
    return out


# ---------------------------------------------------------------------------
# Hook–CTA Timeline Figure (static, no .npy needed)
# ---------------------------------------------------------------------------

def make_hook_cta_figure(df: pd.DataFrame):
    """
    Bar chart showing hook-window vs offset-window activation for key ROIs.
    Illustrates the 0-3s spike and end-of-video valuation surge.
    """
    OUTPUT_DIR.mkdir(exist_ok=True)

    # Average across all videos
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
    print(f"Saved: {out}")
    plt.close(fig)
    return out


# ---------------------------------------------------------------------------
# Manim Animation — Neural Timeline
# ---------------------------------------------------------------------------

try:
    from manim import *

    # Short labels for the legend strip
    _LEGEND_LABELS = {
        "attention": "Attention",
        "valuation": "Save Signal",
        "social":    "Social",
        "language":  "Language",
    }

    class NeuralTimeline(Scene):
        """
        Animated neural activation timeline for a single video.

        Layout (landscape 16:9):
          ┌─────────────────────────────────┐
          │  Creator · subtitle             │  ← header
          │                                 │
          │  [chart: axes + curves + shading│
          │   + dashed peak line]           │  ← chart zone
          │                                 │
          │  ● Attention  ● Save  ● Social  │  ← legend row
          └─────────────────────────────────┘
          then cross-fade to score card.

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
                row = None

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

            # ── Background ──────────────────────────────────────────────────
            self.camera.background_color = ManimColor(C_BG)

            # ── Header (two-line, left-aligned) ─────────────────────────────
            creator  = label.split("_")[0].title()
            title    = Text(creator, font="Liberation Sans", font_size=34,
                            color=ManimColor(C_TEXT), weight=BOLD)
            subtitle = Text("Brain Activity  ·  TRIBE v2 Neural Encoding",
                            font="Liberation Sans", font_size=16,
                            color=ManimColor("#777777"))
            header = VGroup(title, subtitle).arrange(DOWN, aligned_edge=LEFT, buff=0.12)
            header.to_corner(UL, buff=0.45)
            self.play(FadeIn(header, shift=DOWN * 0.15), run_time=0.5)

            # ── Axes  (leave room for header above, legend below) ───────────
            step = max(5, n_secs // 6)
            axes = Axes(
                x_range=[0, n_secs, step],
                y_range=[0, 1.05, 1.0],
                x_length=11.5,
                y_length=4.2,
                axis_config={
                    "color":       ManimColor("#444444"),
                    "include_tip": False,
                    "stroke_width": 1.5,
                    "label_constructor": Text,
                },
                x_axis_config={
                    "numbers_to_include": np.arange(0, n_secs + 1, step),
                    "font_size": 18,
                },
                y_axis_config={"numbers_to_include": []},  # no y-tick labels
            ).move_to([0, -0.25, 0])

            # Tiny "s" unit label at the right end of the x-axis
            x_unit = Text("sec", font_size=14, color=ManimColor("#555555"))
            x_unit.next_to(axes.x_axis.get_right(), RIGHT, buff=0.12)

            self.play(Create(axes), FadeIn(x_unit), run_time=0.7)

            # ── Window shading ───────────────────────────────────────────────
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
            # Labels sit inside the shaded band just above the axis ceiling
            hook_lbl = Text("HOOK", font_size=11, color=ManimColor(C_ATTENTION),
                            weight=BOLD)
            hook_lbl.move_to(axes.c2p(hook_end / 2, 0.97))
            cta_lbl  = Text("CTA", font_size=11, color=ManimColor(C_VALUATION),
                            weight=BOLD)
            cta_lbl.move_to(axes.c2p((offset_start + n_secs) / 2, 0.97))

            self.play(
                FadeIn(hook_rect), FadeIn(cta_rect),
                FadeIn(hook_lbl),  FadeIn(cta_lbl),
                run_time=0.4,
            )

            # ── ROI curves (drawn one at a time) ────────────────────────────
            for roi in KEY_ROIS:
                ts     = curves[roi]
                color  = ManimColor(ROI_COLORS[roi])
                points = [axes.c2p(i, float(ts[i])) for i in range(n_secs)]
                curve  = VMobject(color=color, stroke_width=2.8)
                curve.set_points_smoothly(points)
                self.play(Create(curve), run_time=1.1)

            # ── vmPFC peak: dashed vertical line + compact callout ───────────
            val_ts  = curves["valuation"]
            peak_s  = int(val_ts.argmax())
            px      = axes.c2p(peak_s, 0)[0]
            py_bot  = axes.c2p(0, 0)[1]
            py_top  = axes.c2p(0, float(val_ts[peak_s]))[1]
            peak_line = DashedLine(
                [px, py_bot, 0], [px, py_top, 0],
                color=ManimColor(C_VALUATION),
                stroke_width=1.8,
                dash_length=0.1,
            )
            callout = Text(f"save signal\n@ {peak_s}s",
                           font="Liberation Sans", font_size=13,
                           color=ManimColor(C_VALUATION), line_spacing=0.85)
            callout.next_to([px, py_top, 0], UP, buff=0.14)
            self.play(Create(peak_line), FadeIn(callout), run_time=0.6)

            # ── Legend — horizontal row anchored below the axes ──────────────
            items = []
            for roi in KEY_ROIS:
                pip = Dot(color=ManimColor(ROI_COLORS[roi]), radius=0.09)
                lbl = Text(_LEGEND_LABELS[roi], font_size=15,
                           color=ManimColor(C_TEXT))
                items.append(VGroup(pip, lbl).arrange(RIGHT, buff=0.14))

            legend = VGroup(*items).arrange(RIGHT, buff=0.55)
            legend.next_to(axes, DOWN, buff=0.35)
            self.play(FadeIn(legend), run_time=0.4)

            self.wait(1.5)

            # ── Score card ───────────────────────────────────────────────────
            score = float(row["composite_raw"]) if row is not None else 0.0
            if score >= 65:
                gate_color, gate_word = C_ATTENTION, "POST IT"
            elif score >= 40:
                gate_color, gate_word = C_VALUATION, "REVISE"
            else:
                gate_color, gate_word = "#EF9A9A", "RETHINK"

            score_big  = Text(f"{score:.1f}", font_size=88,
                              color=ManimColor(gate_color), weight=BOLD)
            score_denom = Text("/ 100  Neural Score", font_size=22,
                               color=ManimColor("#888888"))
            gate_badge  = Text(gate_word, font_size=32,
                               color=ManimColor(gate_color), weight=BOLD)
            card = VGroup(score_big, score_denom, gate_badge).arrange(DOWN, buff=0.28)

            self.play(*[FadeOut(m) for m in self.mobjects], run_time=0.7)
            self.play(FadeIn(card, scale=0.92), run_time=0.65)
            self.wait(2.5)

except ImportError:
    pass   # Manim not available — static outputs still work


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--compare",   action="store_true",
                        help="Generate static comparison figure")
    parser.add_argument("--hook-cta",  action="store_true",
                        help="Generate hook/CTA window bar chart")
    parser.add_argument("--top",       default=None,
                        help="Label for top video (default: highest composite_raw)")
    parser.add_argument("--bottom",    default=None,
                        help="Label for bottom video (default: lowest composite_raw)")
    args = parser.parse_args()

    if not Path(SCORES_CSV).exists():
        print(f"scores.csv not found — run TRIBE v2 batch first.")
        sys.exit(1)

    df = load_scores()
    top, bottom = get_top_bottom(df)
    if args.top:
        top = args.top
    if args.bottom:
        bottom = args.bottom

    print(f"Top video:    {top}  (score={df[df['filename']==top+'.mp4']['composite_raw'].values[0]:.2f})")
    print(f"Bottom video: {bottom}  (score={df[df['filename']==bottom+'.mp4']['composite_raw'].values[0]:.2f})")

    if args.compare or not (args.hook_cta):
        make_comparison_figure(top, bottom, df)

    if args.hook_cta:
        make_hook_cta_figure(df)

    if not args.compare and not args.hook_cta:
        make_hook_cta_figure(df)


if __name__ == "__main__":
    main()
