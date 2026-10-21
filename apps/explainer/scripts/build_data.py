"""Build the explainer's data files from the generated media.

    uv run --no-project --with faster-whisper --with numpy python scripts/build_data.py \
        [--preds ../../research/demo_mac_and_cheese_preds.npy]

Writes
  src/data/narration.json  per v6 narration line (public/media/narration_v6/lines.tsv,
                           synced by scripts/vo.py): its duration, word-timed captions
                           (script text, Whisper timing) and whether it is a stand-in
  src/data/result.json     per-second whole-cortex response for the scored clip (only with --preds)

The per-second line is global field power (RMS across all 20,484 fsaverage5
vertices) of TRIBE v2's prediction. It uses no region masks on purpose: the
index-range masks in run_and_save.py / roi_masks.py are not anatomical regions,
so the explainer shows only mask-free model output until they are fixed.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent.parent
MEDIA = HERE / "public" / "media"
DATA = HERE / "src" / "data"

NARRATION = MEDIA / "narration_v6"
PACE = 2.6  # words/s, for evenly timed captions when there is no voice to align to


def _pcm(path: Path) -> np.ndarray:
    raw = subprocess.run(
        ["ffmpeg", "-loglevel", "error", "-i", str(path), "-ac", "1", "-ar", "16000", "-f", "s16le", "-"],
        capture_output=True, check=True,
    ).stdout
    return np.frombuffer(raw, np.int16).astype(np.float32) / 32768


def _duration(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True, check=True,
    ).stdout
    return float(out)


def _norm(w: str) -> str:
    return re.sub(r"[^a-z0-9]", "", w.lower())


def _align(script_words: list[str], timed: list[dict]) -> tuple[list[dict], int]:
    """Give each script word a time. Whisper's words are used only for timing:
    its spelling ('weekly', '20,000', 'F.M.A. Right') never reaches the screen.
    Unmatched script words are spread between their matched neighbours. Also returns
    how many script words were matched."""
    out: list[dict] = []
    j = 0
    for w in script_words:
        k = j
        while k < min(j + 4, len(timed)) and _norm(timed[k]["w"]) != _norm(w):
            k += 1
        if k < min(j + 4, len(timed)):
            out.append({"w": w, "s": timed[k]["s"], "e": timed[k]["e"]})
            j = k + 1
        else:
            out.append({"w": w, "s": None, "e": None})
    matched = sum(1 for o in out if o["s"] is not None)
    last_end = 0.0
    for i, item in enumerate(out):
        if item["s"] is not None:
            last_end = item["e"]
            continue
        nxt = next((o["s"] for o in out[i + 1:] if o["s"] is not None), last_end + 0.4)
        item["s"], item["e"] = last_end, max(nxt, last_end + 0.05)
        last_end = item["e"]
    return out, matched


def _even(words: list[str], duration: float) -> list[dict]:
    """Evenly spaced word timings over the line, for a silent placeholder."""
    step = duration / max(1, len(words))
    return [{"w": w, "s": round(i * step, 2), "e": round((i + 0.85) * step, 2)} for i, w in enumerate(words)]


def build_narration(model) -> None:
    """Align each v6 line (Ben's take, or its stand-in) against its script text. The
    .txt is the caption text; Whisper only supplies the timing."""
    rows = [r.split("\t", 1)[0].strip() for r in (NARRATION / "lines.tsv").read_text().splitlines() if r.strip()]
    out = {}
    for line in rows:
        mp3 = NARRATION / f"{line}.mp3"
        text = (NARRATION / f"{line}.txt").read_text().strip()
        duration = _duration(mp3)
        script = text.split()
        pcm = _pcm(mp3)

        def transcribe(**kw) -> list[dict]:
            segs, _ = model.transcribe(pcm, word_timestamps=True, condition_on_previous_text=False, **kw)
            return [{"w": w.word.strip(), "s": round(w.start, 2), "e": round(w.end, 2)} for s in segs for w in s.words]

        words, matched = _align(script, transcribe())
        if matched < 0.9 * len(script):
            # Whisper sometimes drops a sentence after a pause; primed with the script it
            # keeps going. Only the timing is used either way.
            primed, n = _align(script, transcribe(initial_prompt=text))
            if n > matched:
                words, matched = primed, n
        if matched < len(script) / 2:
            # No voice to align to (a silent placeholder): spread the words evenly instead.
            words = _even(script, duration)
        standin = (NARRATION / f"{line}.standin").exists()
        out[line] = {"text": text, "duration": round(duration, 3), "standin": standin, "words": words}
        print(f"  {line}: {duration:.2f}s  {matched}/{len(script)} words matched{'  (stand-in)' if standin else ''}")
    (DATA / "narration.json").write_text(json.dumps(out, indent=1) + "\n")
    print(f"narration.json  {len(out)} lines")


def build_result(model, preds_path: Path) -> None:
    preds = np.load(preds_path).astype(np.float32)
    if preds.ndim != 2 or preds.shape[1] != 20484:
        raise ValueError(f"expected [T, 20484] preds, got {preds.shape}")
    gfp = np.sqrt((preds ** 2).mean(axis=1))
    lo, hi = float(gfp.min()), float(gfp.max())
    rel = (gfp - lo) / (hi - lo + 1e-9)

    segs, _ = model.transcribe(_pcm(MEDIA / "stimulus.mp4"), word_timestamps=True)
    words = [(w.start, w.end, w.word.strip()) for s in segs for w in s.words]

    def said_at(sec: int) -> str:
        near = [w for (s, e, w) in words if s < sec + 1.5 and e > sec - 1.5]
        return " ".join(near).strip(" ,.")

    # The fMRI signal TRIBE predicts lags the stimulus by ~5 s, so every clip
    # starts low. Those seconds are shown as warm-up, never read as a weak hook.
    warmup = 5
    peak = int(rel.argmax())
    falls = np.diff(rel)[warmup - 1:]          # falls[i] = rel[warmup+i] - rel[warmup+i-1]
    drop = int(falls.argmin()) + warmup
    # The same curve slid back by the lag, so second s lines up with second s of the
    # video (the explainer shows this slide). Not renormalised: same 0..1 scale as
    # "relative". The clip's last `lag` seconds have no aligned reading yet.
    lag = warmup
    aligned = rel[lag:]
    a_peak = int(aligned.argmax())
    a_falls = np.diff(aligned)
    a_drop = int(a_falls.argmin()) + 1
    result = {
        "source": "tribe",
        "model": "TRIBE v2 (CC-BY-NC-4.0)",
        "measure": "Global field power: RMS of the predicted response across all 20,484 cortical points, per second",
        "seconds": int(len(gfp)),
        "gfp": [round(float(v), 5) for v in gfp],
        "relative": [round(float(v), 4) for v in rel],
        "warmup_seconds": warmup,
        "peak": {"second": peak, "said": said_at(peak)},
        "drop": {"second": drop, "said": said_at(drop), "size": round(float(-falls.min()), 4)},
        "lag_seconds": lag,
        "aligned": {
            "relative": [round(float(v), 4) for v in aligned],
            "peak": {"second": a_peak, "said": said_at(a_peak)},
            "drop": {"second": a_drop, "said": said_at(a_drop), "size": round(float(-a_falls.min()), 4)},
        },
    }
    (DATA / "result.json").write_text(json.dumps(result, indent=1) + "\n")
    print(f"result.json  {len(gfp)} s  peak@{peak}s  drop@{drop}s  aligned: peak@{a_peak}s drop@{a_drop}s")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--preds", type=Path, help="TRIBE *_preds.npy for the stimulus clip")
    args = p.parse_args()

    from faster_whisper import WhisperModel

    DATA.mkdir(parents=True, exist_ok=True)
    model = WhisperModel("small.en", device="cpu", compute_type="int8")
    build_narration(model)
    if args.preds:
        build_result(model, args.preds)


if __name__ == "__main__":
    main()
