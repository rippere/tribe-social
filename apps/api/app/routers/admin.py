import hmac
import os

from fastapi import APIRouter, Header, HTTPException

from app import state
from app.services.corpus_writer import flush_to_disk

router = APIRouter(prefix="/admin", tags=["admin"])

_ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "")


@router.post("/flush-corpus")
async def flush_corpus(x_admin_token: str = Header(...)):
    # Constant-time compare; bytes so a non-ASCII header can't raise TypeError.
    if not _ADMIN_TOKEN or not hmac.compare_digest(
        x_admin_token.encode("utf-8", "surrogateescape"),
        _ADMIN_TOKEN.encode("utf-8", "surrogateescape"),
    ):
        raise HTTPException(401, "Invalid admin token")
    flush_to_disk()
    count = len(state.corpus_data["videos"]) if state.corpus_data else 0
    return {"flushed": True, "video_count": count}
