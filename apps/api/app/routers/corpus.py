from fastapi import APIRouter, HTTPException
from ..models.scores import CorpusResponse, CorpusStats, CorpusVideo, CorrelationPair
from .. import state

router = APIRouter(prefix="/corpus")


@router.get("", response_model=CorpusResponse)
async def get_corpus() -> CorpusResponse:
    if state.corpus_data is None:
        raise HTTPException(status_code=503, detail="Corpus not loaded")
    videos = [CorpusVideo(**v) for v in state.corpus_data["videos"]]
    return CorpusResponse(videos=videos)


@router.get("/stats", response_model=CorpusStats)
async def get_stats() -> CorpusStats:
    if state.corpus_data is None:
        raise HTTPException(status_code=503, detail="Corpus not loaded")
    s = state.corpus_data["stats"]
    # Coerce correlations into CorrelationPair objects
    corr = {k: CorrelationPair(**v) for k, v in s["correlations"].items()}
    return CorpusStats(
        total_videos=s["total_videos"],
        avg_composite=s["avg_composite"],
        post_count=s["post_count"],
        median_likes_per_1k=s["median_likes_per_1k"],
        roi_means=s["roi_means"],
        correlations=corr,
        go_no_go=s["go_no_go"],
        composite_r=s["composite_r"],
        rois_above_threshold=s["rois_above_threshold"],
    )
