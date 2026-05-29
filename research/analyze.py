"""
tribe-social: TRIBE v2 output → content insights
Usage:
    uv run python analyze.py --input preds.npy --label "my_reel_title"
    uv run python analyze.py --input preds.npy --label "title" --rebuild-masks

Metrics implemented:
  Baseline   — per-ROI mean, hook (0–3s), peak second, weighted composite
  Berns 2020 — onset + offset windows (strongest predictors of view duration)
  BOLD lit   — transient/sustained ratio (onset vs. steady-state activation)
  EEG neuro  — Global Field Power per second (total cortical energy; Frontiers 2017)
  Scholz 17  — vmPFC–TPJ coupling (the viral circuit for saves/shares)
  Frontiers  — Pleasantness Index (left–right IFJa hemispheric asymmetry)
  Hasson 08  — TRW constraint (vmPFC/TPJ/DMN need ~36s; hook scores flagged accordingly)
"""

import argparse
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from pathlib import Path

from roi_masks import get_roi_masks


WEIGHTS = {
    "Attention":  0.25,
    "Social":     0.30,
    "Language":   0.15,
    "Valuation":  0.20,
    "Auditory":   0.05,
    "Motion":     0.03,
    "Narrative":  0.02,
}

COLORS = {
    "Attention":  "#e74c3c",
    "Social":     "#3498db",
    "Language":   "#2ecc71",
    "Valuation":  "#f39c12",
    "Auditory":   "#9b59b6",
    "Motion":     "#1abc9c",
    "Narrative":  "#95a5a6",
}

# Temporal Receptive Window classification (Hasson et al. 2008; Lerner et al. 2011).
# Long-TRW regions need the full clip to saturate — hook-window scores are unreliable
# for clips shorter than ~36s. Per-second analysis only valid for short-TRW ROIs.
TRW = {
    "Attention":  "short",    # IFJa/IFJp ~1-2s  — valid for second-level scoring
    "Social":     "long",     # PGi/TPJ   ~36s   — clip-level aggregate only
    "Language":   "medium",   # area 44/45 ~12s
    "Valuation":  "long",     # vmPFC     ~36s   — clip-level aggregate only
    "Auditory":   "short",    # STS/A5    ~1-4s
    "Motion":     "short",    # MT/V5     ~1-2s
    "Narrative":  "long",     # PCC/DMN   ~36s   — clip-level aggregate only
}


# ── METRIC COMPUTATION ─────────────────────────────────────────────────────────

def extract_roi_timeseries(preds: np.ndarray, masks: dict) -> dict:
    """Map raw vertex activations to per-ROI time series using HCP MMP1.0 masks."""
    return {
        group: (
            preds[:, indices].mean(axis=1) if len(indices) > 0
            else np.zeros(preds.shape[0])
        )
        for group, indices in masks.items()
    }


def compute_extra_metrics(preds: np.ndarray, group_ts: dict, masks: dict) -> dict:
    """
    Literature-validated supplementary metrics from a (n_seconds, 20484) prediction array.

    Berns 2020 PNAS:   onset/offset window means (onset > clip average as predictor)
    BOLD transient lit: transient/sustained ratio (Harms & Woolsey 2014)
    Frontiers 2017:     Global Field Power — sqrt(mean(preds[t]²)) per second
    Scholz 2017 PNAS:   vmPFC–TPJ Pearson coupling (the viral sharing circuit)
    Frontiers 2017:     Pleasantness Index — left vs. right IFJ hemispheric asymmetry
    """
    n = preds.shape[0]

    # Global Field Power curve — total cortical energy per second (EEG neuromarketing analog)
    gfp = np.sqrt((preds ** 2).mean(axis=1))

    out: dict = {
        "gfp":        gfp,
        "gfp_mean":   float(gfp.mean()),
        "gfp_hook":   float(gfp[:min(3, n)].mean()),
        "gfp_offset": float(gfp[-min(5, n):].mean()),
    }

    for group, ts in group_ts.items():
        onset  = float(ts[:min(4, n)].mean())
        steady = float(ts[min(6, n):].mean()) if n > 6 else float(ts.mean())
        deriv  = np.diff(ts)

        out[f"{group}_offset"] = float(ts[-min(5, n):].mean())

        # T/S > 1 = transient spike that decays (hook capture).
        # T/S < 1 = sustained activation dominates (depth capture; preferred for vmPFC/TPJ).
        out[f"{group}_transient_sustained"] = onset / (abs(steady) + 1e-9)

        # Temporal instability: how many times does activation reverse direction?
        out[f"{group}_sign_flips"] = int((np.diff(np.sign(deriv)) != 0).sum()) if len(deriv) > 1 else 0
        out[f"{group}_max_deriv_s"] = int(deriv.argmax()) + 1 if len(deriv) > 0 else 0

    # vmPFC–TPJ coupling (Scholz 2017 viral circuit)
    if "Valuation" in group_ts and "Social" in group_ts and n >= 4:
        r = float(np.corrcoef(group_ts["Valuation"], group_ts["Social"])[0, 1])
        out["vmPFC_TPJ_coupling"] = r if np.isfinite(r) else 0.0
    else:
        out["vmPFC_TPJ_coupling"] = float("nan")

    # Pleasantness Index: left IFJ minus right IFJ hemispheric asymmetry
    if "Attention" in masks and len(masks["Attention"]) > 0:
        att = masks["Attention"]
        lh  = att[att < 10242]
        rh  = att[att >= 10242]
        if len(lh) > 0 and len(rh) > 0:
            out["pleasantness_index"] = float(preds[:, lh].mean() - preds[:, rh].mean())
        else:
            out["pleasantness_index"] = float("nan")
    else:
        out["pleasantness_index"] = float("nan")

    return out


def score_card(group_ts: dict, extra: dict) -> pd.DataFrame:
    rows = []
    for group, ts in group_ts.items():
        rows.append({
            "Dimension":   group,
            "Mean":        ts.mean(),
            "Peak":        ts.max(),
            "Peak_second": int(ts.argmax()),
            "Hook_0_3s":   ts[:3].mean(),
            "Offset_5s":   extra.get(f"{group}_offset", np.nan),
            "T_S_ratio":   extra.get(f"{group}_transient_sustained", np.nan),
            "SignFlips":   extra.get(f"{group}_sign_flips", 0),
            "TRW":         TRW.get(group, "?"),
            "Weight":      WEIGHTS.get(group, 0.0),
        })
    df = pd.DataFrame(rows).set_index("Dimension")
    df["Normalized"] = (df["Mean"] - df["Mean"].min()) / (df["Mean"].max() - df["Mean"].min() + 1e-9)
    df["Weighted"]   = df["Normalized"] * df["Weight"]
    df["Composite"]  = df["Weighted"].sum()
    return df


# ── PLOTTING ───────────────────────────────────────────────────────────────────

def plot_insights(preds: np.ndarray, label: str, out_dir: Path, masks: dict):
    group_ts  = extract_roi_timeseries(preds, masks)
    extra     = compute_extra_metrics(preds, group_ts, masks)
    df        = score_card(group_ts, extra)
    dims      = list(masks.keys())
    n_seconds = preds.shape[0]
    seconds   = np.arange(n_seconds)
    composite_score = df["Weighted"].sum() * 100
    coupling  = extra.get("vmPFC_TPJ_coupling", float("nan"))
    pi        = extra.get("pleasantness_index", float("nan"))

    fig = plt.figure(figsize=(16, 12))
    fig.suptitle(f"TRIBE v2 Content Analysis — {label}", fontsize=14, fontweight="bold", y=0.98)
    gs = gridspec.GridSpec(3, 3, figure=fig, hspace=0.48, wspace=0.35)

    # ── 1. Attention + GFP curve ─────────────────────────────────────────────
    ax_attn = fig.add_subplot(gs[0, :2])
    ax_attn.plot(seconds, group_ts["Attention"], color=COLORS["Attention"],
                 linewidth=2, label="Attention (IFJa+IFJp)")
    # Hook window (Berns 2020 onset)
    ax_attn.axvspan(0, min(3, n_seconds), alpha=0.15, color="yellow", label="Hook 0–3s")
    # Offset window (Berns 2020: offset often more predictive than clip average)
    if n_seconds > 5:
        ax_attn.axvspan(n_seconds - 5, n_seconds, alpha=0.12, color="steelblue", label="Offset −5s")
    # Global Field Power on twin axis
    ax_gfp = ax_attn.twinx()
    ax_gfp.plot(seconds, extra["gfp"], color="#AAAAAA", linewidth=1.2,
                linestyle="--", alpha=0.65, label="GFP")
    ax_gfp.set_ylabel("GFP", fontsize=8, color="#999999")
    ax_gfp.tick_params(axis="y", labelsize=7, colors="#999999")
    lines1, labs1 = ax_attn.get_legend_handles_labels()
    lines2, labs2 = ax_gfp.get_legend_handles_labels()
    ax_attn.legend(lines1 + lines2, labs1 + labs2, fontsize=7.5, loc="upper right")
    ax_attn.set_title("Attention + GFP Over Time  (GFP = total cortical energy/s)")
    ax_attn.set_xlabel("Second")
    ax_attn.set_ylabel("Attention Activation")

    # ── 2. Composite gauge + viral circuit ───────────────────────────────────
    ax_gauge = fig.add_subplot(gs[0, 2])
    gauge_color = "#2ecc71" if composite_score >= 65 else "#f39c12" if composite_score >= 40 else "#e74c3c"
    ax_gauge.barh(["Score"], [composite_score], color=gauge_color, height=0.4)
    ax_gauge.barh(["Score"], [100 - composite_score], left=[composite_score],
                  color="#ecf0f1", height=0.4)
    ax_gauge.set_xlim(0, 100)
    ax_gauge.set_title("Composite Engagement Score")
    ax_gauge.text(composite_score / 2, 0, f"{composite_score:.0f}", ha="center",
                  va="center", fontweight="bold", fontsize=16, color="white")
    # Viral circuit indicator
    if np.isfinite(coupling):
        c_col = "#3498db" if coupling > 0.3 else "#999999"
        ax_gauge.text(0.5, -0.22,
                      f"Viral circuit vmPFC↔TPJ: {coupling:+.2f}",
                      transform=ax_gauge.transAxes, ha="center", fontsize=8, color=c_col)
    if np.isfinite(pi):
        pi_col = "#27ae60" if pi > 0 else "#e74c3c"
        ax_gauge.text(0.5, -0.36,
                      f"Pleasantness (L−R IFJ): {pi:+.3f}",
                      transform=ax_gauge.transAxes, ha="center", fontsize=8, color=pi_col)

    # ── 3. Temporal heatmap ──────────────────────────────────────────────────
    ax_heat = fig.add_subplot(gs[1, :])
    heat_data = np.array([group_ts[g] for g in dims])
    ptp_h     = heat_data.ptp(axis=1, keepdims=True)
    norm_heat = (heat_data - heat_data.min(axis=1, keepdims=True)) / (ptp_h + 1e-9)
    im = ax_heat.imshow(norm_heat, aspect="auto", cmap="RdYlGn",
                        extent=[0, n_seconds, -0.5, len(dims) - 0.5])
    ax_heat.set_yticks(range(len(dims)))
    # Tag long-TRW ROIs in y-axis labels
    ylabels = [f"{d}  [⚠TRW]" if TRW.get(d) == "long" else d for d in dims]
    ax_heat.set_yticklabels(ylabels, fontsize=8.5)
    ax_heat.set_xlabel("Second")
    ax_heat.set_title("Neural Activation Heatmap   (⚠TRW = long temporal receptive window — clip-level aggregate only)")
    plt.colorbar(im, ax=ax_heat, label="Normalized activation", shrink=0.8)
    ax_heat.axvline(3, color="yellow", linewidth=1.5, linestyle="--", alpha=0.8)
    if n_seconds > 5:
        ax_heat.axvline(n_seconds - 5, color="steelblue", linewidth=1.2,
                        linestyle=":", alpha=0.7)

    # ── 4. Score card bar chart with T/S overlay ─────────────────────────────
    ax_bar = fig.add_subplot(gs[2, :2])
    vals       = [df.loc[d, "Normalized"] * 100 for d in dims]
    bar_colors = [COLORS[d] for d in dims]
    bars       = ax_bar.bar(dims, vals, color=bar_colors, alpha=0.85)
    ax_bar.set_ylim(0, 120)
    ax_bar.set_ylabel("Normalized Score (0–100)")
    ax_bar.set_title("Per-Dimension Score Card  (T/S = transient/sustained ratio)")
    for bar, dim, val in zip(bars, dims, vals):
        ts_r  = df.loc[dim, "T_S_ratio"]
        flips = df.loc[dim, "SignFlips"]
        trw   = TRW.get(dim, "?")
        top_label = f"{val:.0f}"
        if np.isfinite(ts_r):
            top_label += f"\nT/S {ts_r:.1f}"
        ax_bar.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1.5,
                    top_label, ha="center", va="bottom", fontsize=7.5)
        if trw == "long":
            ax_bar.text(bar.get_x() + bar.get_width() / 2, -12,
                        "⚠TRW", ha="center", va="top", fontsize=7, color="#e67e22")

    # ── 5. Revision flags ────────────────────────────────────────────────────
    ax_flags = fig.add_subplot(gs[2, 2])
    ax_flags.axis("off")

    thresholds = {"Attention": 40, "Social": 40, "Language": 35, "Valuation": 35}
    revision_map = {
        "Attention":  "Tighten hook — pattern interrupt needed in first 3s",
        "Social":     "Add 'you/your brain' framing or social scenario",
        "Language":   "Sharpen narration — vague language scores low",
        "Valuation":  "Make stakes explicit — what does this mean for them?",
    }
    flags = [
        f"⚠ {dim}: {revision_map[dim]}"
        for dim, thr in thresholds.items()
        if df.loc[dim, "Normalized"] * 100 < thr
    ]

    if np.isfinite(coupling):
        if coupling > 0.5:
            flags.append(f"✓ Viral circuit strong (r={coupling:.2f})")
        elif coupling < 0.2:
            flags.append(f"⚠ Viral circuit weak (r={coupling:.2f}) — add social stakes to CTA")

    if n_seconds < 30:
        flags.append(f"⚠ TRW: clip is {n_seconds}s — vmPFC/TPJ/DMN need ~36s to saturate")

    if not flags:
        flags = ["✓ All key dimensions above threshold", "  → Clear to post"]

    flag_text = "\n\n".join(flags)
    any_warn  = any(f.startswith("⚠") for f in flags)
    ax_flags.text(0.05, 0.97, "Revision Flags", transform=ax_flags.transAxes,
                  fontweight="bold", fontsize=10, va="top")
    ax_flags.text(0.05, 0.83, flag_text, transform=ax_flags.transAxes,
                  fontsize=8, va="top", color="#c0392b" if any_warn else "#27ae60")

    out_path = out_dir / f"{label.replace(' ', '_')}_analysis.png"
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"Saved: {out_path}")

    # ── Terminal summary ─────────────────────────────────────────────────────
    print(f"\n{'='*62}")
    print(f"  {label}")
    print(f"  Composite: {composite_score:.1f}/100  |  GFP: hook={extra['gfp_hook']:.4f} "
          f"mean={extra['gfp_mean']:.4f} offset={extra['gfp_offset']:.4f}")
    if np.isfinite(coupling):
        print(f"  Viral circuit (vmPFC↔TPJ): r={coupling:.3f}  "
              f"{'[strong]' if coupling > 0.5 else '[moderate]' if coupling > 0.2 else '[weak]'}")
    if np.isfinite(pi):
        print(f"  Pleasantness (L−R IFJ):   {pi:+.4f}")
    print(f"{'='*62}")
    print(f"  {'Dim':<12} {'Score':>5} {'Hook':>7} {'Offset':>8} {'T/S':>6} {'Flips':>6} {'TRW'}")
    print(f"  {'-'*57}")
    for dim in dims:
        score  = df.loc[dim, "Normalized"] * 100
        hook   = df.loc[dim, "Hook_0_3s"]
        offset = df.loc[dim, "Offset_5s"]
        ts_r   = df.loc[dim, "T_S_ratio"]
        flips  = int(df.loc[dim, "SignFlips"])
        trw    = TRW.get(dim, "?")
        bar    = "█" * int(score / 5) + "░" * (20 - int(score / 5))
        trw_tag = " ⚠" if trw == "long" else "  "
        print(f"  {dim:<12} {bar} {score:5.1f}  "
              f"hook:{hook:.3f}  off:{offset:.3f}  t/s:{ts_r:.1f}  flips:{flips}  [{trw}]{trw_tag}")
    print(f"{'='*62}")
    if any_warn:
        for f in flags:
            if f.startswith("⚠"):
                print(f"  {f}")
    else:
        print("  ✓ Clear to post")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input",         required=True, help="Path to preds.npy")
    parser.add_argument("--label",         default="content", help="Content label")
    parser.add_argument("--outdir",        default=".", help="Directory to save plots")
    parser.add_argument("--rebuild-masks", action="store_true",
                        help="Force neuromaps re-download for ROI masks")
    args = parser.parse_args()

    preds = np.load(args.input)
    print(f"Loaded predictions: {preds.shape}")

    masks = get_roi_masks(rebuild=args.rebuild_masks)

    out_dir = Path(args.outdir)
    out_dir.mkdir(parents=True, exist_ok=True)

    plot_insights(preds, args.label, out_dir, masks)


if __name__ == "__main__":
    main()
