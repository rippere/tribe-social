"""Synthetic corpus data for the tribe-social Streamlit demo."""

import numpy as np
import pandas as pd


def generate_corpus(n: int = 50, seed: int = 42) -> pd.DataFrame:
    """Return a DataFrame of n synthetic Reels with ROI scores + engagement metrics."""
    rng = np.random.default_rng(seed)

    # Latent quality factor (most videos mediocre, few exceptional)
    quality = rng.beta(2, 3, n)

    def roi(q: np.ndarray, strength: float = 0.4, noise: float = 0.12) -> np.ndarray:
        return np.clip(0.28 + q * strength + rng.normal(0, noise, n), 0.05, 0.95)

    vmPFC   = roi(quality, 0.50)
    TPJ     = roi(quality, 0.45)
    IFJa    = roi(quality, 0.42)
    IFJp    = roi(quality, 0.38)
    area_45 = roi(quality, 0.35)
    MT_V5   = roi(quality, 0.28)
    hook_attn = roi(quality, 0.45)

    composite = (
        0.25 * vmPFC
        + 0.25 * TPJ
        + 0.20 * IFJa
        + 0.15 * area_45
        + 0.15 * MT_V5
    ) * 100

    base_views = rng.integers(5_000, 500_000, n)
    saves    = (base_views * (0.010 + quality * 0.080) + rng.normal(0, 500, n)).clip(0).astype(int)
    shares   = (base_views * (0.005 + quality * 0.040) + rng.normal(0, 200, n)).clip(0).astype(int)
    likes    = (base_views * (0.050 + quality * 0.100) + rng.normal(0, 1_000, n)).clip(0).astype(int)
    comments = (base_views * (0.010 + quality * 0.030) + rng.normal(0, 200, n)).clip(0).astype(int)

    creators = rng.choice(
        ["huberman_lab", "ali_abdaal", "sahil_bloom", "chris_williamson",
         "codie_sanchez", "ai_creator_1", "ai_creator_2"],
        n,
    )

    return pd.DataFrame({
        "video_id":           [f"video_{i:03d}" for i in range(n)],
        "creator":            creators,
        "views":              base_views,
        "likes":              likes,
        "saves":              saves,
        "shares":             shares,
        "comments":           comments,
        "vmPFC_mean":         vmPFC,
        "TPJ_mean":           TPJ,
        "IFJa_mean":          IFJa,
        "IFJp_mean":          IFJp,
        "area_45_mean":       area_45,
        "MT_V5_mean":         MT_V5,
        "hook_attention_mean": hook_attn,
        "composite_score":    composite,
    })


def generate_temporal(
    duration_s: int = 60,
    vmPFC: float = 0.5,
    TPJ: float = 0.5,
    IFJa: float = 0.5,
    hook_attn: float = 0.6,
    seed: int = 0,
) -> pd.DataFrame:
    """Return per-second simulated activations for three key region groups."""
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

    return pd.DataFrame({
        "second":           t,
        "Attention":        attn,
        "Social Cognition": social,
        "Valuation":        val,
    })
