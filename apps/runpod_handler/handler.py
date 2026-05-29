"""
RunPod Serverless handler for TRIBE v2 inference.
Deployed as a Docker container to RunPod — NOT part of Railway.

Input:  {"input": {"video_b64": "<base64 mp4>", "filename": "video.mp4"}}
Output: {"output": <quick_scores() flat dict>}
        {"error": "<message>"} on failure
"""
import base64
import os
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


def handler(event: dict) -> dict:
    inp       = event.get("input", {})
    video_b64 = inp.get("video_b64")
    filename  = inp.get("filename", "video.mp4")

    if not video_b64:
        return {"error": "Missing video_b64 in input"}

    video_bytes = base64.b64decode(video_b64)
    if len(video_bytes) < 1024:
        raise RuntimeError("Invalid video data — payload too small or corrupted")
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
        return {"output": row}
    except Exception as exc:
        return {"error": str(exc)}
    finally:
        video_path.unlink(missing_ok=True)
        try:
            Path(tmp_dir).rmdir()
        except OSError:
            pass


if __name__ == "__main__":
    runpod.serverless.start({"handler": handler})
