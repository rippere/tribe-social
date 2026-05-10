"""
TRIBE Social Lab — Neural Content Intelligence Dashboard
Run: uv run streamlit run demo.py
"""

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
POST_GREEN  = "#16a34a"
REVISE_AMBER = "#d97706"
RETHINK_RED  = "#dc2626"
ACCENT = "#6366f1"

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🧠 TRIBE Social Lab")
    st.caption("Neural content intelligence for Instagram Reels")
    st.divider()

    data_source = st.radio("Data source", ["Demo data (synthetic)", "Upload scores.csv"])
    if data_source == "Upload scores.csv":
        uploaded = st.file_uploader("scores.csv", type="csv")
        df = pd.read_csv(uploaded) if uploaded else generate_corpus()
        if not uploaded:
            st.info("Using demo data until a file is uploaded.")
    else:
        n_videos = st.slider("Corpus size", 20, 150, 50)
        df = generate_corpus(n=n_videos)

    st.divider()
    st.caption(f"**{len(df)}** videos loaded")
    st.caption("Post ≥ 65 · Revise 40–65 · Rethink < 40")

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs(["📊 Corpus Analysis", "🔬 Engagement Correlations", "🎯 Score New Video"])


# ─────────────────────────────────────────────────────────────────────────────
# TAB 1 — Corpus Analysis
# ─────────────────────────────────────────────────────────────────────────────
with tab1:
    st.subheader("Corpus Overview")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Videos", len(df))
    c2.metric("Avg neural score", f"{df['composite_score'].mean():.1f} / 100")
    c3.metric("Post-worthy (≥ 65)", int((df["composite_score"] >= 65).sum()))
    c4.metric("Median saves", int(df["saves"].median()))

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
        top10 = (
            df.nlargest(10, "composite_score")
            [["video_id", "creator", "composite_score", "saves", "shares"]]
            .rename(columns={"video_id": "Video", "creator": "Creator",
                              "composite_score": "Score", "saves": "Saves", "shares": "Shares"})
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


# ─────────────────────────────────────────────────────────────────────────────
# TAB 2 — Engagement Correlations
# ─────────────────────────────────────────────────────────────────────────────
with tab2:
    st.subheader("Neural Score ↔ Engagement Correlations")
    target = st.selectbox("Engagement target", ["saves", "shares", "likes", "comments"])

    col_left, col_right = st.columns(2)

    with col_left:
        st.markdown(f"**Composite Score vs. {target.title()}**")
        r_comp, p_comp = stats.pearsonr(df["composite_score"], df[target])
        fig3 = px.scatter(
            df, x="composite_score", y=target, color="creator",
            trendline="ols",
            labels={"composite_score": "Composite Neural Score", target: target.title()},
        )
        fig3.update_layout(margin=dict(t=10), height=350)
        st.plotly_chart(fig3, use_container_width=True)

        st.markdown(f"**r = {r_comp:.3f}, p = {p_comp:.4f}**")
        if r_comp > 0.4:
            st.success(f"Strong signal (r > 0.4). Composite predicts {target}. ✅")
        elif r_comp > 0.3:
            st.warning(f"Moderate signal (r > 0.3). Collect more data before proceeding.")
        else:
            st.error(f"Weak signal (r < 0.3). Hypothesis not supported for {target}.")

    with col_right:
        st.markdown("**Per-ROI Correlation Heatmap**")
        metrics = ["saves", "shares", "likes", "comments"]
        corr_matrix = pd.DataFrame(
            {
                m: {ROI_LABELS[roi]: stats.pearsonr(df[roi], df[m])[0] for roi in ROI_COLS}
                for m in metrics
            }
        ).rename(columns=str.title)

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
    passed = sum(
        1 for roi in ROI_COLS
        if (stats.pearsonr(df[roi], df["saves"])[0] > 0.3
            or stats.pearsonr(df[roi], df["shares"])[0] > 0.3)
    )
    r_saves, _ = stats.pearsonr(df["composite_score"], df["saves"])

    if r_saves > 0.4 or passed >= 2:
        st.success(
            f"**GO** — {passed} ROI(s) exceed r > 0.3 with saves/shares; "
            f"composite r (saves) = {r_saves:.2f}. Proceed to Phase 2."
        )
    else:
        st.error(
            f"**NO-GO** — Only {passed} ROI(s) pass. Composite r = {r_saves:.2f}. "
            f"Expand corpus before proceeding."
        )


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

    # Gauge
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

    # Radar
    with col_radar:
        st.markdown("**ROI Radar vs. Corpus Average**")
        roi_values   = [vmPFC_v, TPJ_v, IFJa_v, IFJp_v, area45_v, MT_V5_v]
        labels_short = [ROI_SHORT[c] for c in ROI_COLS]
        corpus_avgs  = df[ROI_COLS].mean().tolist()

        fig_r = go.Figure()
        # Close polygon
        rv = roi_values + [roi_values[0]]
        ca = corpus_avgs + [corpus_avgs[0]]
        ls = labels_short + [labels_short[0]]

        fig_r.add_trace(go.Scatterpolar(
            r=rv, theta=ls, fill="toself",
            name="This video", line_color=ACCENT, fillcolor=f"rgba(99,102,241,0.25)",
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
