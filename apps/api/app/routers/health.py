import os
import shutil

from fastapi import APIRouter

router = APIRouter()

_RUNPOD_KEY = os.getenv("RUNPOD_API_KEY", "")
_RUNPOD_EP  = os.getenv("RUNPOD_ENDPOINT_ID", "")
_POD_URL    = os.getenv("POD_URL", "").rstrip("/")


@router.get("/health")
async def health() -> dict:
    # mode is "pod" (POD_URL warm-pod path), "real" (RunPod serverless
    # key+endpoint), or "mock" (no inference backend). Precedence MUST match
    # inference.submit_job routing, which is POD_URL-first: when both are set the
    # warm pod runs, so health reports "pod". A POD_URL-only deploy scores for
    # real, so it must report "pod" — not "mock" as the old real_mode-only check did.
    if _POD_URL:
        mode = "pod"
    elif _RUNPOD_KEY and _RUNPOD_EP:
        mode = "real"
    else:
        mode = "mock"
    return {
        "status": "ok",
        "mode": mode,
        "version": "1.0.0",
        "yt_dlp_available": shutil.which("yt-dlp") is not None,
        "runpod_endpoint_configured": bool(_RUNPOD_EP),
    }
