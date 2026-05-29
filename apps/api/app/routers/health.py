import os
import shutil

from fastapi import APIRouter

router = APIRouter()

_RUNPOD_KEY = os.getenv("RUNPOD_API_KEY", "")
_RUNPOD_EP  = os.getenv("RUNPOD_ENDPOINT_ID", "")


@router.get("/health")
async def health() -> dict:
    real_mode = bool(_RUNPOD_KEY and _RUNPOD_EP)
    return {
        "status": "ok",
        "mode": "real" if real_mode else "mock",
        "version": "1.0.0",
        "yt_dlp_available": shutil.which("yt-dlp") is not None,
        "runpod_endpoint_configured": bool(_RUNPOD_EP),
    }
