"""
RunPod Serverless handler for TRIBE v2 inference.
Deployed as a Docker container to RunPod — NOT part of Railway.

Input:  {"input": {"video_b64": "<base64 mp4>", "filename": "video.mp4"}}
Output: <quick_scores() flat dict>  — RunPod wraps this in the single "output"
        key itself, so the handler must NOT add its own "output" wrapper.
        {"error": "<message>"} on failure
"""
import base64
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

# RunPod's PyTorch base image sets HF_HUB_ENABLE_HF_TRANSFER=1, but hf_transfer
# isn't installed — whisperx (spawned by TRIBE v2 to transcribe the video's audio)
# inherits the flag and dies fetching the faster-whisper model. Force it off so the
# subprocess falls back to the standard HF downloader. Hard set (not setdefault):
# the base image already exports =1, so we must override it.
os.environ["HF_HUB_ENABLE_HF_TRANSFER"] = "0"

sys.path.insert(0, "/workspace")

import runpod

_model = None


def _get_model():
    global _model
    if _model is None:
        from tribe_scoring.run_and_save import load_model
        _t0 = time.time()
        print("[handler] Loading TRIBE v2 model...", flush=True)
        _model = load_model(cache_folder="/workspace/cache")
        print(f"[handler] TRIBE v2 model loaded in {time.time() - _t0:.1f}s", flush=True)
    return _model



# Linux NAME_MAX is 255 bytes; stay well under it so a long client filename
# can't make write_bytes()/unlink() raise.
_MAX_NAME_BYTES = 200


def _safe_filename(raw) -> str:
    """Client-supplied filename reduced to something safe to create in tmp_dir.

    Basename only (writes/unlinks stay in tmp_dir), NULs stripped, lone
    surrogates replaced, and truncated to _MAX_NAME_BYTES of UTF-8 while keeping
    a short extension -- otherwise open()/unlink() raise ValueError/OSError.
    """
    text = str(raw or "").replace("\x00", "")
    # Lone surrogates (valid in JSON "\ud800") can't be encoded to a path.
    text = text.encode("utf-8", "replace").decode("utf-8")
    name = Path(text).name
    if len(name.encode("utf-8")) > _MAX_NAME_BYTES:
        suffix = Path(name).suffix
        if len(suffix.encode("utf-8")) > 16:
            suffix = ""
        stem = name[: len(name) - len(suffix)] if suffix else name
        budget = _MAX_NAME_BYTES - len(suffix.encode("utf-8"))
        stem = stem.encode("utf-8")[:budget].decode("utf-8", "ignore")
        name = stem + suffix
    if name in ("", ".", ".."):
        return "video.mp4"
    return name


def handler(event: dict) -> dict:
    inp       = event.get("input", {})
    video_b64 = inp.get("video_b64")
    filename  = _safe_filename(inp.get("filename", "video.mp4"))

    if not video_b64:
        return {"error": "Missing video_b64 in input"}

    try:
        video_bytes = base64.b64decode(video_b64)
    except (ValueError, TypeError):
        return {"error": "Invalid video data — video_b64 is not valid base64"}
    if len(video_bytes) < 1024:
        return {"error": "Invalid video data — payload too small or corrupted"}
    tmp_dir     = tempfile.mkdtemp()
    video_path  = Path(tmp_dir) / filename

    try:
        video_path.write_bytes(video_bytes)
        model     = _get_model()
        from tribe_scoring.run_and_save import quick_scores
        events_df = model.get_events_dataframe(video_path=str(video_path))
        preds, _  = model.predict(events=events_df)
        row = quick_scores(preds)
        row["filename"]  = filename
        row["label"]     = Path(filename).stem
        row["n_seconds"] = preds.shape[0]
        # Return the flat row directly — RunPod adds the single "output" wrapper.
        # Returning {"output": row} would double-nest to {"output": {"output": row}}.
        return row
    except Exception as exc:
        return {"error": str(exc)}
    finally:
        # rmtree never raises here, so cleanup can't turn a result (or the
        # {"error": ...} above) into an unhandled exception.
        shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    runpod.serverless.start({"handler": handler})
