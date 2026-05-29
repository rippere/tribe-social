import os

from fastapi import APIRouter, Header, HTTPException

from app import state
from app.services.corpus_writer import flush_to_disk

router = APIRouter(prefix="/admin", tags=["admin"])

_ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "")


@router.post("/flush-corpus")
async def flush_corpus(x_admin_token: str = Header(...)):
    if not _ADMIN_TOKEN or x_admin_token != _ADMIN_TOKEN:
        raise HTTPException(401, "Invalid admin token")
    flush_to_disk()
    count = len(state.corpus_data["videos"]) if state.corpus_data else 0
    return {"flushed": True, "video_count": count}
