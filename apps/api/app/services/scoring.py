"""
TRIBE Social Lab — scoring logic ported from demo.py / demo_data.py
"""
import numpy as np
from app.models.job import RevisionTip, TemporalPoint
from tribe_scoring.composite import POST_THRESHOLD, REVISE_THRESHOLD, compute_verdict  # single source of truth

# ── Constants (verbatim from demo.py) ─────────────────────────────────────────
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
    "vmPFC_mean": [
        "\"Most people don't know this will cost them $___\"",
        "\"The decision you made at 22 is still costing you money\"",
        "\"Here's what $100K/yr actually looks like after tax\"",
    ],
    "TPJ_mean": [
        "\"Your brain does something weird when you watch this\"",
        "\"This is what happens in someone's head when they trust you\"",
        "\"The social mistake that tanks 80% of first impressions\"",
    ],
    "IFJa_mean": [
        "\"Stop — read this before you scroll past\"",
        "\"I tested 47 hooks. This one outperformed every other by 3x\"",
        "\"Nobody talks about this. I don't know why.\"",
    ],
    "IFJp_mean": [
        "\"The counterintuitive thing about [topic] that experts miss\"",
        "\"What if everything you know about [topic] is backwards?\"",
        "\"[Surprising fact] — and no one's connecting the dots\"",
    ],
    "area_45_mean": [
        "\"In 60 seconds: the precise mental model that changed how I work\"",
        "\"One sentence that reframes everything about [topic]\"",
        "\"The exact framework I use: [clear, named concept]\"",
    ],
    "MT_V5_mean": [
        "Show-don't-tell: open with B-roll or fast visual before speaking",
        "Add text overlay animations synced to speech rhythm",
        "Use jump cuts every 2–3 seconds to maintain motion energy",
    ],
}



def get_revision_tips(roi: dict[str, float]) -> list[RevisionTip]:
    """
    Return RevisionTip objects for ROIs below 0.45.
    roi keys are short names (vmPFC, TPJ, IFJa, IFJp, area_45, MT_V5).
    """
    # Map short names to REVISION_TIPS / HOOK_TEMPLATES keys (which use _mean suffix)
    short_to_col = {
        "vmPFC":   "vmPFC_mean",
        "TPJ":     "TPJ_mean",
        "IFJa":    "IFJa_mean",
        "IFJp":    "IFJp_mean",
        "area_45": "area_45_mean",
        "MT_V5":   "MT_V5_mean",
    }
    tips = []
    for short, val in sorted(roi.items(), key=lambda x: x[1]):
        if val < 0.45 and short != "IFJp":
            col = short_to_col.get(short, short)
            tips.append(RevisionTip(
                roi=ROI_SHORT.get(col, short),
                score=round(val, 3),
                tip=REVISION_TIPS.get(col, ""),
                hook_templates=HOOK_TEMPLATES.get(col, []),
            ))
    return tips


def generate_temporal_data(
    vmPFC: float,
    TPJ: float,
    IFJa: float,
    hook_attn: float,
    seed: int = 42,
    duration_s: int = 60,
) -> list[TemporalPoint]:
    """
    Port of demo_data.py::generate_temporal() — deterministic per-second activations.
    Three curves: Attention (exponential decay), Social Cognition (power-law growth),
    Valuation (clipped ramp).
    """
    rng = np.random.default_rng(seed)
    t = np.arange(duration_s, dtype=float)

    # Attention: spikes at hook, decays, partial recovery at CTA
    attn = IFJa * 0.4 + hook_attn * 0.55 * np.exp(-t / 7)
    attn += 0.18 * np.exp(-((t - 52) ** 2) / 40)   # CTA spike
    attn += rng.normal(0, 0.025, duration_s)
    attn = np.clip(attn, 0, 1)

    # Social cognition: builds through middle, peaks near CTA
    social = TPJ * 0.25 + TPJ * 0.55 * (t / duration_s) ** 0.7
    social += rng.normal(0, 0.025, duration_s)
    social = np.clip(social, 0, 1)

    # Valuation: flat, then rises sharply at CTA
    val = vmPFC * 0.25 + vmPFC * 0.55 * np.clip((t - 42) / 18, 0, 1)
    val += rng.normal(0, 0.025, duration_s)
    val = np.clip(val, 0, 1)

    return [
        TemporalPoint(
            second=int(t[i]),
            attention=float(round(attn[i], 4)),
            social_cognition=float(round(social[i], 4)),
            valuation=float(round(val[i], 4)),
        )
        for i in range(duration_s)
    ]
