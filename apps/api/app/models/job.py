from enum import Enum
from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class JobStatus(str, Enum):
    queued = "queued"
    uploading = "uploading"
    scoring = "scoring"
    downloading = "downloading"
    analyzing = "analyzing"
    complete = "complete"
    failed = "failed"


class TemporalPoint(BaseModel):
    second: int
    attention: float
    social_cognition: float
    valuation: float


class RevisionTip(BaseModel):
    roi: str
    score: float
    tip: str
    hook_templates: list[str]


class ScoreResult(BaseModel):
    video_id: str
    composite_score: float
    verdict: str  # "POST" | "REVISE" | "RETHINK"
    roi: dict[str, float]  # normalized 0-1 values
    corpus_roi_means: dict[str, float]  # from corpus.json stats
    weak_rois: list[str]
    revision_tips: list[RevisionTip]
    temporal: list[TemporalPoint]


class Job(BaseModel):
    job_id: str
    status: JobStatus
    progress_pct: int = 0
    message: str = "Queued"
    result: Optional[ScoreResult] = None
    error: Optional[str] = None
    runpod_job_id: Optional[str] = None
    created_at: datetime
