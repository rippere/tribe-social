"""Narration for the v6 explainer: Ben's voice, off-screen, one take per line.

The script is <media>/v6/lines.tsv (line id, text) with the caption text in
<media>/v6/narration/<line>.txt. Every line needs <media>/v6/narration/<line>.mp3; a
line whose audio is a stand-in carries a <line>.standin marker next to it, and the
render shows a "stand-in voice" tag while any marker is left.

    # stand-ins (free, offline: piper TTS, voice en_US-ryan-medium); skips real takes
    uv run --no-project --with numpy --with piper-tts python scripts/vo.py standin

    # Ben's takes: <media>/v6/recordings/<line>.{wav,m4a,mp3}; trims, levels, replaces
    uv run --no-project --with numpy python scripts/vo.py ingest

Both trim leading/trailing silence to PAD seconds, loudness-normalise to the level the
v5 narration was mixed at (measured from public/media/narration/n1_intro.mp3 when it is
there), and then copy the v6 narration into public/media/narration_v6/ for the render.
Re-run scripts/build_data.py afterwards for the word timings (`npm run vo:ingest` does).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent.parent
ROOT = HERE.parent.parent
PUBLIC = HERE / "public" / "media" / "narration_v6"
V5_REF = HERE / "public" / "media" / "narration" / "n1_intro.mp3"
V5_LUFS = -11.5  # n1_intro.mp3, measured 2026-10-20; used when the file is not synced
TRUE_PEAK = -1.0
PAD = 0.15
SR = 44100
TAKE_EXTS = (".wav", ".m4a", ".mp3", ".flac", ".aif", ".aiff")

VOICE = "en_US-ryan-medium"
VOICE_URL = "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/ryan/medium/"
VOICE_DIR = Path.home() / ".cache" / "piper-voices"
# How the stand-in voice should say words it would otherwise spell or misread. Only
# the audio uses these; captions always come from the .txt.
SPOKEN = {"fMRIght": "Eff em aright", "TRIBE v2": "Tribe vee two", "TRIBE": "Tribe", "MRI": "M R I"}
PACE = 2.6  # target words per second for stand-ins


def lines(v6: Path) -> list[str]:
    rows = [r.split("\t", 1)[0].strip() for r in (v6 / "lines.tsv").read_text().splitlines() if r.strip()]
    return [r for r in rows if r and not r.startswith("#")]


def run(cmd: list[str]) -> str:
    return subprocess.run(cmd, check=True, capture_output=True, text=True).stdout


def decode(path: Path) -> np.ndarray:
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path), "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
        check=True, capture_output=True,
    ).stdout
    return np.frombuffer(raw, np.float32)


def speech_span(x: np.ndarray) -> tuple[float, float]:
    """First and last moment of speech: 10 ms RMS frames above a threshold set from the
    take's own noise floor and peak, held for 30 ms so a click doesn't count."""
    hop = SR // 100
    n = len(x) // hop
    if n < 3:
        return 0.0, len(x) / SR
    rms = np.sqrt((x[: n * hop].reshape(n, hop) ** 2).mean(axis=1) + 1e-12)
    db = 20 * np.log10(rms)
    thr = max(np.percentile(db, 10) + 12, db.max() - 40)
    on = db > thr
    held = on & np.roll(on, -1) & np.roll(on, -2)
    idx = np.nonzero(held)[0]
    if not len(idx):
        return 0.0, len(x) / SR
    return idx[0] * hop / SR, min(len(x), (idx[-1] + 3) * hop) / SR


def loudness(path: Path, extra: list[str] | None = None) -> dict:
    out = subprocess.run(
        ["ffmpeg", "-hide_banner", "-i", str(path), *(extra or []), "-af",
         "loudnorm=print_format=json", "-f", "null", "-"],
        check=True, capture_output=True, text=True,
    ).stderr
    return json.loads(out[out.rindex("{"): out.rindex("}") + 1])


def target_lufs() -> float:
    return float(loudness(V5_REF)["input_i"]) if V5_REF.exists() else V5_LUFS


def level(src: Path, dst: Path, lufs: float) -> float:
    """Trim to speech ± PAD and bring to `lufs` integrated with peaks held under
    TRUE_PEAK, as 44.1 kHz mono 128k MP3 like the v5 narration. Returns the duration.

    v5 was compressed TTS (-11.5 LUFS with peaks at -0.3 dBTP). A plain recording has
    far more peak-to-loudness range, so a straight gain (or loudnorm, which tops out
    a few LU short here) can't reach that level: gain into a peak limiter, re-measured
    and corrected until it lands within 0.2 LU."""
    x = decode(src)
    s, e = speech_span(x)
    s, e = max(0.0, s - PAD), min(len(x) / SR, e + PAD)
    with tempfile.TemporaryDirectory() as tmp:
        cut = Path(tmp) / "cut.wav"
        out = Path(tmp) / "out.mp3"
        # Trim inside the filter graph and reset timestamps, so the fade-out is timed
        # on the trimmed take (an output -ss would leave the original timeline).
        trim = (f"aresample={SR},atrim=start={s:.3f}:end={e:.3f},asetpts=PTS-STARTPTS,"
                f"afade=t=in:d=0.01,afade=t=out:st={max(0.0, e - s - 0.01):.3f}:d=0.01")
        run(["ffmpeg", "-v", "error", "-y", "-i", str(src), "-ac", "1", "-af", trim, "-ar", str(SR), str(cut)])
        gain = lufs - float(loudness(cut)["input_i"])
        limit = 10 ** ((TRUE_PEAK - 0.5) / 20)  # sample-peak limiter; 0.5 dB margin for true peak
        # Measured on the encoded MP3: the encode itself costs ~0.5 LU.
        for _ in range(10):
            run(["ffmpeg", "-v", "error", "-y", "-i", str(cut), "-af",
                 f"volume={gain:.2f}dB,alimiter=limit={limit:.4f}:attack=3:release=60:level=disabled",
                 "-ar", str(SR), "-ac", "1", "-c:a", "libmp3lame", "-b:a", "128k", str(out)])
            miss = lufs - float(loudness(out)["input_i"])
            if abs(miss) < 0.2:
                break
            gain += 1.5 * miss  # the limiter eats part of every step
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(out, dst)
    return e - s


def sync_public(v6: Path) -> None:
    """Copy the v6 narration (audio, caption text, stand-in markers) into public/."""
    if PUBLIC.exists():
        shutil.rmtree(PUBLIC)
    PUBLIC.mkdir(parents=True)
    shutil.copy2(v6 / "lines.tsv", PUBLIC / "lines.tsv")
    for line in lines(v6):
        for ext in (".mp3", ".txt", ".standin"):
            f = v6 / "narration" / f"{line}{ext}"
            if f.exists():
                shutil.copy2(f, PUBLIC / f.name)
    print(f"synced v6 narration → {PUBLIC}")


def voice() -> Path:
    VOICE_DIR.mkdir(parents=True, exist_ok=True)
    for f in (f"{VOICE}.onnx", f"{VOICE}.onnx.json"):
        if not (VOICE_DIR / f).exists():
            print(f"downloading piper voice {f}")
            urllib.request.urlretrieve(VOICE_URL + f, VOICE_DIR / f)
    return VOICE_DIR / f"{VOICE}.onnx"


def spoken(text: str) -> str:
    for k, v in SPOKEN.items():
        text = re.sub(rf"\b{re.escape(k)}\b", v, text)
    return text


def silent(dst: Path, seconds: float) -> None:
    run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"anullsrc=r={SR}:cl=mono", "-t", f"{seconds:.2f}",
         "-c:a", "libmp3lame", "-b:a", "128k", str(dst)])


def cmd_standin(v6: Path, force: bool) -> None:
    lufs = target_lufs()
    try:
        model = voice()
        import piper  # noqa: F401  (only to fail early into the silent fallback)
    except Exception as e:  # no network, no piper: silent placeholders, evenly timed captions
        print(f"piper unavailable ({e}); writing silent placeholders at {PACE} words/s", file=sys.stderr)
        model = None
    for line in lines(v6):
        mp3 = v6 / "narration" / f"{line}.mp3"
        marker = v6 / "narration" / f"{line}.standin"
        if mp3.exists() and not marker.exists() and not force:
            print(f"{line}: real take, kept")
            continue
        text = (v6 / "narration" / f"{line}.txt").read_text().strip()
        words = len(text.split())
        if model is None:
            silent(mp3, words / PACE)
            marker.write_text("silent placeholder: no voice; captions evenly timed\n")
            print(f"{line}: silent {words / PACE:.2f}s")
            continue
        with tempfile.TemporaryDirectory() as tmp:
            wav = Path(tmp) / "tts.wav"

            def tts(scale: float) -> float:
                subprocess.run(
                    [sys.executable, "-m", "piper", "-m", str(model), "-f", str(wav),
                     "--sentence-silence", "0.3", "--length-scale", f"{scale:.3f}"],
                    input=spoken(text), text=True, check=True, capture_output=True,
                )
                return level(wav, mp3, lufs)

            # piper's default pace is ~3.2 words/s and length-scale isn't linear in
            # duration (pauses don't stretch): step it until the line is near PACE.
            scale = 1.0
            dur = tts(scale)
            for _ in range(4):
                if abs(words / dur / PACE - 1) < 0.04:
                    break
                scale = float(np.clip(scale * words / dur / PACE, 0.8, 2.2))
                dur = tts(scale)
        marker.write_text(f"stand-in: piper {VOICE}, not Ben. Replace with v6/recordings/{line}.* + vo.py ingest\n")
        print(f"{line}: stand-in {dur:.2f}s  {words / dur:.2f} words/s")
    sync_public(v6)


def cmd_ingest(v6: Path) -> None:
    lufs = target_lufs()
    rec = v6 / "recordings"
    done = []
    for line in lines(v6):
        takes = sorted((p for p in rec.glob(f"{line}.*") if p.suffix.lower() in TAKE_EXTS), key=lambda p: p.stat().st_mtime)
        if not takes:
            continue
        take = takes[-1]  # newest wins if there are several formats
        dur = level(take, v6 / "narration" / f"{line}.mp3", lufs)
        (v6 / "narration" / f"{line}.standin").unlink(missing_ok=True)
        done.append(line)
        print(f"{line}: {take.name} → {dur:.2f}s at {lufs} LUFS")
    left = [line for line in lines(v6) if (v6 / "narration" / f"{line}.standin").exists()]
    print(f"ingested {len(done)} take(s); still stand-in: {', '.join(left) if left else 'none'}")
    sync_public(v6)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("cmd", choices=["standin", "ingest", "sync"])
    p.add_argument("--media", type=Path, default=None, help="business/explainer folder (default $EXPLAINER_MEDIA or repo business/explainer)")
    p.add_argument("--force", action="store_true", help="standin: overwrite real takes too")
    a = p.parse_args()
    media = a.media or Path(os.environ.get("EXPLAINER_MEDIA") or ROOT / "business" / "explainer")
    v6 = media / "v6"
    if not (v6 / "lines.tsv").exists():
        sys.exit(f"no v6 script at {v6}/lines.tsv (set EXPLAINER_MEDIA to the main checkout's business/explainer)")
    if a.cmd == "standin":
        cmd_standin(v6, a.force)
    elif a.cmd == "ingest":
        cmd_ingest(v6)
    else:
        sync_public(v6)


if __name__ == "__main__":
    main()
