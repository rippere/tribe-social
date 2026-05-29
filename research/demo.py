"""
TRIBE Social Lab — Neural Content Intelligence Dashboard
Run: uv run streamlit run demo.py
"""

import os
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from scipy import stats

from demo_data import generate_corpus, generate_temporal

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="TRIBE Social Lab",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Constants ─────────────────────────────────────────────────────────────────
ROI_COLS = ["vmPFC_mean", "TPJ_mean", "IFJa_mean", "IFJp_mean", "area_45_mean", "MT_V5_mean"]
ROI_LABELS = {
    "vmPFC_mean":   "vmPFC (Valuation)",
    "TPJ_mean":     "TPJ (Social Cog.)",
    "IFJa_mean":    "IFJa (Attention)",
    "IFJp_mean":    "IFJp (Attention)",
    "area_45_mean": "Area 45 (Language)",
    "MT_V5_mean":   "MT/V5 (Motion)",
}
ROI_SHORT = {
    "vmPFC_mean":   "vmPFC",
    "TPJ_mean":     "TPJ",
    "IFJa_mean":    "IFJa",
    "IFJp_mean":    "IFJp",
    "area_45_mean": "Area 45",
    "MT_V5_mean":   "MT/V5",
}
REVISION_TIPS = {
    "vmPFC_mean":   "Make the stakes explicit — what does this mean *for them*, financially or behaviorally?",
    "TPJ_mean":     "Add interpersonal framing — 'your brain', 'you', social scenario or short story.",
    "IFJa_mean":    "Tighten the hook — first 3 seconds need a pattern interrupt: bold claim, question, or contrast.",
    "IFJp_mean":    "Add cognitive novelty — unexpected fact, counterintuitive claim, or visual surprise.",
    "area_45_mean": "Sharpen narration — precise, dense language scores higher than vague phrasing.",
    "MT_V5_mean":   "Add visual movement — cuts, text animation, gestures, or relevant b-roll.",
}
HOOK_TEMPLATES = {
    "vmPFC_mean":   [
        "\"Most people don't know this will cost them $___\"",
        "\"The decision you made at 22 is still costing you money\"",
        "\"Here's what $100K/yr actually looks like after tax\"",
    ],
    "TPJ_mean":     [
        "\"Your brain does something weird when you watch this\"",
        "\"This is what happens in someone's head when they trust you\"",
        "\"The social mistake that tanks 80% of first impressions\"",
    ],
    "IFJa_mean":    [
        "\"Stop — read this before you scroll past\"",
        "\"I tested 47 hooks. This one outperformed every other by 3x\"",
        "\"Nobody talks about this. I don't know why.\"",
    ],
    "IFJp_mean":    [
        "\"The counterintuitive thing about [topic] that experts miss\"",
        "\"What if everything you know about [topic] is backwards?\"",
        "\"[Surprising fact] — and no one's connecting the dots\"",
    ],
    "area_45_mean": [
        "\"In 60 seconds: the precise mental model that changed how I work\"",
        "\"One sentence that reframes everything about [topic]\"",
        "\"The exact framework I use: [clear, named concept]\"",
    ],
    "MT_V5_mean":   [
        "Show-don't-tell: open with B-roll or fast visual before speaking",
        "Add text overlay animations synced to speech rhythm",
        "Use jump cuts every 2–3 seconds to maintain motion energy",
    ],
}
POST_GREEN   = "#16a34a"
REVISE_AMBER = "#d97706"
RETHINK_RED  = "#dc2626"
ACCENT       = "#6366f1"

SCORES_PATH     = os.path.join(os.path.dirname(__file__), "scores.csv")
ENGAGEMENT_PATH = os.path.join(os.path.dirname(__file__), "engagement.csv")
CONTENT_DIR     = os.path.join(os.path.dirname(__file__), "content_output")
FIGURE_PATH     = os.path.join(os.path.dirname(__file__), "figure1_correlation_panel.png")


# ── Real corpus loader ────────────────────────────────────────────────────────
@st.cache_data
def load_real_corpus() -> pd.DataFrame:
    """Load scores.csv + engagement.csv and normalise to the demo schema."""
    scores = pd.read_csv(SCORES_PATH)
    eng    = pd.read_csv(ENGAGEMENT_PATH)

    # Column rename: TRIBE v2 output → display names
    col_map = {
        "valuation_mean":  "vmPFC_mean",
        "social_mean":     "TPJ_mean",
        "attention_mean":  "IFJa_mean",   # IFJp gets a copy below
        "language_mean":   "area_45_mean",
        "motion_mean":     "MT_V5_mean",
    }
    scores = scores.rename(columns=col_map)

    # IFJp_mean — no dedicated column; use 90% of IFJa as proxy
    scores["IFJp_mean"] = scores["IFJa_mean"] * 0.90

    # Normalise all ROI columns and composite_raw → 0–1 / 0–100
    for col in ["vmPFC_mean", "TPJ_mean", "IFJa_mean", "IFJp_mean", "area_45_mean", "MT_V5_mean"]:
        cmin, cmax = scores[col].min(), scores[col].max()
        scores[col] = ((scores[col] - cmin) / (cmax - cmin)).round(4)

    cmin, cmax = scores["composite_raw"].min(), scores["composite_raw"].max()
    scores["composite_score"] = (
        (scores["composite_raw"] - cmin) / (cmax - cmin) * 100
    ).round(1)

    # Identity columns
    scores["video_id"] = scores["filename"].str.replace(".mp4", "", regex=False)
    scores["creator"]  = scores["filename"].str.split("_").str[0]

    # Merge engagement
    merged = scores.merge(eng, on="filename", how="left")

    # Proxy metric: likes per 1 000 views (saves not available)
    merged["likes_per_1k"] = (
        merged["likes"] / merged["views"].replace(0, np.nan) * 1000
    ).round(1)

    # Fill missing shares with 0 so existing code doesn't crash
    merged["shares"]  = merged.get("shares",  pd.Series(0, index=merged.index)).fillna(0).astype(int)
    merged["saves"]   = 0   # not a public metric on YouTube

    # Keep only columns the dashboard needs
    keep = [
        "video_id", "creator", "filename",
        "views", "likes", "shares", "saves", "comments", "likes_per_1k",
    ] + ROI_COLS + ["composite_score"]
    return merged[[c for c in keep if c in merged.columns]]


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🧠 TRIBE Social Lab")
    st.caption("Neural content intelligence for social video")
    st.divider()

    data_source = st.radio(
        "Data source",
        ["Demo data (synthetic)", "Real corpus (scores.csv)", "Upload scores.csv"],
    )

    if data_source == "Real corpus (scores.csv)":
        df = load_real_corpus()
        is_real = True
        st.success(f"{len(df)} scored videos loaded from disk.")
    elif data_source == "Upload scores.csv":
        uploaded = st.file_uploader("scores.csv", type="csv")
        df = pd.read_csv(uploaded) if uploaded else generate_corpus()
        is_real = False
        if not uploaded:
            st.info("Using demo data until a file is uploaded.")
    else:
        n_videos = st.slider("Corpus size", 20, 150, 50)
        df = generate_corpus(n=n_videos)
        is_real = False

    st.divider()
    st.caption(f"**{len(df)}** videos loaded")
    st.caption("Post ≥ 65 · Revise 40–65 · Rethink < 40")

    st.divider()
    with st.expander("What is TRIBE v2?"):
        st.markdown(
            """
**TRIBE v2** (Temporal Representation of Involved Brain Encodings) is a whole-brain
neural encoding model trained by Meta Research on fMRI data from participants
watching video content.

It maps each second of video onto activation in six key regions:

| Region | Role |
|--------|------|
| **vmPFC** | Value / reward signal |
| **TPJ** | Social cognition & mentalising |
| **IFJa/IFJp** | Executive attention |
| **Area 45** | Language processing |
| **MT/V5** | Visual motion |

Higher activation → stronger *neural engagement* → higher predicted shareability.

**Key literature**
- Berns & Skipper 2020: onset/offset windows predict view counts
- Scholz et al. 2017: vmPFC + TPJ signal predicts virality at scale
- Wubble et al. 2024: TRIBE v2 commercial validation
- Hasson et al. 2008: temporal receptive windows ≈ 36 s for vmPFC/TPJ
"""
        )


# ── Tabs ──────────────────────────────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs(["📊 Corpus Analysis", "🔬 Engagement Correlations", "🎯 Score New Video"])


# ─────────────────────────────────────────────────────────────────────────────
# TAB 1 — Corpus Analysis
# ─────────────────────────────────────────────────────────────────────────────
with tab1:
    st.subheader("Corpus Overview")

    engagement_proxy = "likes_per_1k" if is_real else "saves"
    engagement_label = "Median likes / 1K views" if is_real else "Median saves"
    engagement_val   = (
        round(float(df["likes_per_1k"].median()), 1)
        if is_real
        else int(df["saves"].median())
    )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Videos", len(df))
    c2.metric("Avg neural score", f"{df['composite_score'].mean():.1f} / 100")
    c3.metric("Post-worthy (≥ 65)", int((df["composite_score"] >= 65).sum()))
    c4.metric(engagement_label, engagement_val)

    st.divider()
    col_left, col_right = st.columns([1.1, 0.9])

    with col_left:
        st.markdown("**Composite Score Distribution**")
        fig = px.histogram(
            df, x="composite_score", nbins=25,
            color_discrete_sequence=[ACCENT],
            labels={"composite_score": "Composite Neural Score"},
        )
        fig.add_vline(x=65, line_dash="dash", line_color=POST_GREEN,
                      annotation_text="Post", annotation_position="top right")
        fig.add_vline(x=40, line_dash="dash", line_color=RETHINK_RED,
                      annotation_text="Rethink", annotation_position="top right")
        fig.update_layout(margin=dict(t=10, b=10), height=300, showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    with col_right:
        st.markdown("**Top 10 by Neural Score**")
        show_col  = "likes" if is_real else "saves"
        show_col2 = "views" if is_real else "shares"
        top10 = (
            df.nlargest(10, "composite_score")
            [["video_id", "creator", "composite_score", show_col, show_col2]]
            .rename(columns={
                "video_id":       "Video",
                "creator":        "Creator",
                "composite_score":"Score",
                show_col:         show_col.title(),
                show_col2:        show_col2.title(),
            })
            .reset_index(drop=True)
        )
        top10["Score"] = top10["Score"].round(1)
        st.dataframe(top10, use_container_width=True, hide_index=True)

    st.markdown("**Mean Activation per Brain Region (across corpus)**")
    roi_means = df[ROI_COLS].mean().rename(ROI_LABELS)
    fig2 = px.bar(
        x=roi_means.values, y=roi_means.index, orientation="h",
        color=roi_means.values,
        color_continuous_scale="Viridis",
        labels={"x": "Mean Activation (0–1)", "y": ""},
    )
    fig2.update_layout(margin=dict(t=10, b=10), height=260, coloraxis_showscale=False)
    st.plotly_chart(fig2, use_container_width=True)

    # Scorecard gallery (real corpus only)
    if is_real and os.path.isdir(CONTENT_DIR):
        png_files = sorted(
            f for f in os.listdir(CONTENT_DIR)
            if f.startswith("scorecard_") and f.endswith(".png")
        )
        if png_files:
            with st.expander(f"🖼  Scorecard Gallery ({len(png_files)} cards)"):
                creators = sorted(set(f.split("_")[1] for f in png_files))
                sel = st.selectbox("Filter by creator", ["All"] + creators, key="gallery_creator")
                filtered = png_files if sel == "All" else [f for f in png_files if f.split("_")[1] == sel]
                cols = st.columns(3)
                for i, fname in enumerate(filtered):
                    cols[i % 3].image(
                        os.path.join(CONTENT_DIR, fname),
                        caption=fname.replace("scorecard_", "").replace(".png", ""),
                        use_column_width=True,
                    )


# ─────────────────────────────────────────────────────────────────────────────
# TAB 2 — Engagement Correlations
# ─────────────────────────────────────────────────────────────────────────────
with tab2:
    st.subheader("Neural Score ↔ Engagement Correlations")

    if is_real:
        target_options = ["likes_per_1k", "likes", "views", "comments"]
        target_default = "likes_per_1k"
    else:
        target_options = ["saves", "shares", "likes", "comments"]
        target_default = "saves"

    target = st.selectbox("Engagement target", target_options, index=0)
    target_label = "Likes / 1K Views" if target == "likes_per_1k" else target.title()

    col_left, col_right = st.columns(2)

    with col_left:
        st.markdown(f"**Composite Score vs. {target_label}**")
        r_comp, p_comp = stats.pearsonr(df["composite_score"], df[target])
        fig3 = px.scatter(
            df, x="composite_score", y=target, color="creator",
            trendline="ols",
            labels={"composite_score": "Composite Neural Score", target: target_label},
        )
        fig3.update_layout(margin=dict(t=10), height=350)
        st.plotly_chart(fig3, use_container_width=True)

        st.markdown(f"**r = {r_comp:.3f}, p = {p_comp:.4f}**")
        if r_comp > 0.4:
            st.success(f"Strong signal (r > 0.4). Composite predicts {target_label}. ✅")
        elif r_comp > 0.3:
            st.warning(f"Moderate signal (r > 0.3). Collect more data before proceeding.")
        else:
            st.error(f"Weak signal (r < 0.3). Hypothesis not supported for {target_label}.")

    with col_right:
        st.markdown("**Per-ROI Correlation Heatmap**")
        corr_targets = (
            [t for t in ["likes_per_1k", "likes", "views", "comments"] if t in df.columns]
            if is_real
            else ["saves", "shares", "likes", "comments"]
        )
        corr_labels = {
            "likes_per_1k": "Likes/1K",
            "likes": "Likes",
            "views": "Views",
            "saves": "Saves",
            "shares": "Shares",
            "comments": "Comments",
        }
        corr_matrix = pd.DataFrame(
            {
                corr_labels.get(m, m): {
                    ROI_LABELS[roi]: stats.pearsonr(df[roi], df[m])[0]
                    for roi in ROI_COLS
                }
                for m in corr_targets
            }
        )

        fig4 = px.imshow(
            corr_matrix,
            color_continuous_scale="RdBu",
            zmin=-0.6, zmax=0.6,
            text_auto=".2f",
            labels={"color": "Pearson r"},
            aspect="auto",
        )
        fig4.update_layout(margin=dict(t=10), height=350)
        st.plotly_chart(fig4, use_container_width=True)

    st.divider()
    st.markdown("**Go / No-Go Verdict**")

    go_target = "likes_per_1k" if is_real else "saves"
    go_label  = "likes/1K views" if is_real else "saves"

    passed = sum(
        1 for roi in ROI_COLS
        if stats.pearsonr(df[roi], df[go_target])[0] > 0.3
    )
    r_primary, _ = stats.pearsonr(df["composite_score"], df[go_target])

    if r_primary > 0.4 or passed >= 2:
        st.success(
            f"**GO** — {passed} ROI(s) exceed r > 0.3 with {go_label}; "
            f"composite r = {r_primary:.2f}. Proceed to Phase 2."
        )
    else:
        st.error(
            f"**NO-GO** — Only {passed} ROI(s) pass. Composite r = {r_primary:.2f}. "
            f"Expand corpus before proceeding."
        )

    # Show correlation figure if present
    if is_real and os.path.isfile(FIGURE_PATH):
        with st.expander("📈 Full correlation panel (Phase 1b report)"):
            st.image(FIGURE_PATH, use_column_width=True)


# ─────────────────────────────────────────────────────────────────────────────
# TAB 3 — Score New Video
# ─────────────────────────────────────────────────────────────────────────────
with tab3:
    st.subheader("Score a New Reel")
    st.caption("Enter TRIBE v2 outputs from RunPod, or use sliders to simulate.")

    col_s1, col_s2, col_s3 = st.columns(3)
    with col_s1:
        vmPFC_v   = st.slider("vmPFC (Valuation)",       0.0, 1.0, 0.50, 0.01)
        TPJ_v     = st.slider("TPJ (Social Cognition)",  0.0, 1.0, 0.50, 0.01)
    with col_s2:
        IFJa_v    = st.slider("IFJa (Attention)",        0.0, 1.0, 0.50, 0.01)
        IFJp_v    = st.slider("IFJp (Attention)",        0.0, 1.0, 0.50, 0.01)
    with col_s3:
        area45_v  = st.slider("Area 45 (Language)",      0.0, 1.0, 0.50, 0.01)
        MT_V5_v   = st.slider("MT/V5 (Motion)",          0.0, 1.0, 0.50, 0.01)
    hook_attn_v = st.slider("Hook Attention (0–3 s)", 0.0, 1.0, 0.60, 0.01)

    composite_v = (
        0.25 * vmPFC_v
        + 0.25 * TPJ_v
        + 0.20 * IFJa_v
        + 0.15 * area45_v
        + 0.15 * MT_V5_v
    ) * 100

    st.divider()
    col_gauge, col_radar = st.columns(2)

    with col_gauge:
        st.markdown("**Composite Neural Score**")
        fig_g = go.Figure(go.Indicator(
            mode="gauge+number",
            value=composite_v,
            number={"suffix": " / 100", "font": {"size": 36}},
            gauge={
                "axis": {"range": [0, 100], "tickwidth": 1},
                "steps": [
                    {"range": [0,  40], "color": "#fecaca"},
                    {"range": [40, 65], "color": "#fef9c3"},
                    {"range": [65,100], "color": "#bbf7d0"},
                ],
                "bar": {"color": ACCENT, "thickness": 0.25},
                "threshold": {
                    "line": {"color": "black", "width": 3},
                    "thickness": 0.8,
                    "value": composite_v,
                },
            },
        ))
        fig_g.update_layout(height=280, margin=dict(t=40, b=0, l=20, r=20))
        st.plotly_chart(fig_g, use_container_width=True)

        if composite_v >= 65:
            st.success(f"**POST** — Score {composite_v:.1f} clears the neural threshold.")
        elif composite_v >= 40:
            st.warning(f"**REVISE** — Score {composite_v:.1f}. See recommendations below.")
        else:
            st.error(f"**RETHINK** — Score {composite_v:.1f}. Fundamental content issues.")

    with col_radar:
        st.markdown("**ROI Radar vs. Corpus Average**")
        roi_values   = [vmPFC_v, TPJ_v, IFJa_v, IFJp_v, area45_v, MT_V5_v]
        labels_short = [ROI_SHORT[c] for c in ROI_COLS]
        corpus_avgs  = df[ROI_COLS].mean().tolist()

        fig_r = go.Figure()
        rv = roi_values + [roi_values[0]]
        ca = corpus_avgs + [corpus_avgs[0]]
        ls = labels_short + [labels_short[0]]

        fig_r.add_trace(go.Scatterpolar(
            r=rv, theta=ls, fill="toself",
            name="This video", line_color=ACCENT, fillcolor="rgba(99,102,241,0.25)",
        ))
        fig_r.add_trace(go.Scatterpolar(
            r=ca, theta=ls, fill="toself",
            name="Corpus avg", line_color="#94a3b8", fillcolor="rgba(148,163,184,0.15)",
        ))
        fig_r.update_layout(
            polar=dict(radialaxis=dict(range=[0, 1], showticklabels=True)),
            legend=dict(orientation="h", y=-0.15),
            margin=dict(t=30, b=40),
            height=320,
        )
        st.plotly_chart(fig_r, use_container_width=True)

    # Revision recommendations
    st.markdown("**Revision Recommendations**")
    video_vals = {
        "vmPFC_mean":   vmPFC_v,
        "TPJ_mean":     TPJ_v,
        "IFJa_mean":    IFJa_v,
        "IFJp_mean":    IFJp_v,
        "area_45_mean": area45_v,
        "MT_V5_mean":   MT_V5_v,
    }
    weak = [(roi, val) for roi, val in video_vals.items() if val < 0.45]
    if weak:
        for roi, val in sorted(weak, key=lambda x: x[1]):
            st.warning(f"**{ROI_LABELS[roi]}** ({val:.2f}) — {REVISION_TIPS[roi]}")
    else:
        st.success("All ROIs above 0.45. Content profile looks strong.")

    # Content strategy hooks
    if weak:
        with st.expander("💡 Hook templates for weak ROIs"):
            st.caption(
                "Field-indiscriminant hooks extracted from viral content analysis. "
                "Adapt to your niche."
            )
            for roi, val in sorted(weak, key=lambda x: x[1]):
                st.markdown(f"**{ROI_LABELS[roi]}** — top-performing hook patterns:")
                for hook in HOOK_TEMPLATES.get(roi, []):
                    st.markdown(f"- {hook}")
                st.divider()

    # Temporal breakdown
    st.divider()
    st.markdown("**Temporal Activation Breakdown (simulated)**")
    t_df = generate_temporal(
        vmPFC=vmPFC_v, TPJ=TPJ_v, IFJa=IFJa_v, hook_attn=hook_attn_v, seed=42
    )
    fig_t = px.line(
        t_df, x="second", y=["Attention", "Social Cognition", "Valuation"],
        labels={"value": "Activation (0–1)", "second": "Second", "variable": "Region"},
        color_discrete_map={
            "Attention":        "#6366f1",
            "Social Cognition": "#10b981",
            "Valuation":        "#f59e0b",
        },
    )
    fig_t.add_vrect(x0=0, x1=3,  fillcolor="blue",  opacity=0.07,
                    annotation_text="Hook",   annotation_position="top left")
    fig_t.add_vrect(x0=45, x1=60, fillcolor="green", opacity=0.07,
                    annotation_text="CTA",    annotation_position="top right")
    fig_t.update_layout(margin=dict(t=10), height=300, legend=dict(orientation="h", y=1.15))
    st.plotly_chart(fig_t, use_container_width=True)

    st.caption(
        "Hook (0–3s): attention should spike. "
        "Body (3–45s): social cognition builds. "
        "CTA (45–60s): valuation + social should peak."
    )
