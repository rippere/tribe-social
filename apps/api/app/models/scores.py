"""Pydantic models for TRIBE corpus data."""

from __future__ import annotations

from typing import Optional
from pydantic import BaseModel


class ROIBreakdown(BaseModel):
    vmPFC_mean: float
    TPJ_mean: float
    IFJa_mean: float
    IFJp_mean: float
    area_45_mean: float
    MT_V5_mean: float


class CorpusVideo(BaseModel):
    video_id: str
    creator: str
    filename: str
    views: Optional[int] = None
    likes: Optional[int] = None
    shares: Optional[int] = None
    saves: Optional[int] = None
    comments: Optional[int] = None
    likes_per_1k: Optional[float] = None
    vmPFC_mean: float
    TPJ_mean: float
    IFJa_mean: float
    IFJp_mean: float
    area_45_mean: float
    MT_V5_mean: float
    composite_score: float


class CorpusResponse(BaseModel):
    videos: list[CorpusVideo]


class CorrelationPair(BaseModel):
    r: Optional[float] = None
    p: Optional[float] = None


class CorpusStats(BaseModel):
    total_videos: int
    avg_composite: float
    post_count: int
    median_likes_per_1k: float
    roi_means: dict[str, float]
    correlations: dict[str, CorrelationPair]
    go_no_go: str
    composite_r: float
    rois_above_threshold: int
