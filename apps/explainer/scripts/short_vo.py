"""Narration for the ~30 s short: Ben's v6 takes, cut on word boundaries.

    uv run --no-project --with numpy python scripts/short_vo.py

Reads the v6 lines as synced into public/media/narration_v6 (scripts/vo.py, already
trimmed and levelled to -16 LUFS) and their word timings in src/data/narration.json.
Writes the cut lines, re-levelled to -16 LUFS, as 44.1 kHz mono WAV (no second lossy encode) to
public/media/narration_short/ and their timings to src/data/narration_short.json.

  s1_intro  b1 without "I built fMRIght.": "Hey, I'm Ben." + "It predicts ... second by second."
  s2_upload b2's first sentence, as spoken: "First, you upload a clip."
  b6_read, b8_read2 are used whole, straight from narration_v6.

Cut points were read off the take's 20 ms RMS envelope, not Whisper's word ends
(Whisper stretches "fMRIght." over the pause after it): "Ben." has decayed to the
room tone (~-40 dBFS) by 1.36 s and "It" starts at 4.23 s. Each joint lands in room
tone with 15 ms fades, so the splice can't click, and the kept tone makes a ~0.3 s pause.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent.parent
V6 = HERE / "public" / "media" / "narration_v6"
OUT = HERE / "public" / "media" / "narration_short"
DATA = HERE / "src" / "data"
SR = 44100
FADE = 0.015
LUFS = -16.0  # v6's per-line level (scripts/vo.py TARGET_LUFS)

# line id -> (source v6 line, [(start, end) seconds kept, in order], caption text)
CUTS = {
    "s1_intro": ("b1_intro", [(0.0, 1.38), (4.00, None)],
                 "Hey, I'm Ben. It predicts how an average viewer's brain responds to a short video, second by second."),
    # The take says "First you upload a clip, then ..." (the v6 caption drops "First").
    # "First"'s /st/ runs straight into "you" (fricative to 0.38 s, the t's release to
    # 0.43 s), so cutting it leaves a "t"-coloured onset that Whisper, and likely a
    # listener, hears as "Do you upload a clip?". Kept as spoken, ending in the pause
    # after "clip". Captions carry the spoken word, timed off the envelope.
    "s2_upload": ("b2_upload", [(0.0, 1.72)], "First, you upload a clip."),
}
WHOLE = ["b6_read", "b8_read2"]
# Words the v6 timings lack (they follow the script, not the take): source-time spans.
RETIME = {"s2_upload": [("First,", 0.20, 0.38), ("you", 0.40, 0.52)]}


def decode(path: Path) -> np.ndarray:
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
                         check=True, capture_output=True).stdout
    return np.frombuffer(raw, np.float32).copy()


def faded(x: np.ndarray) -> np.ndarray:
    n = min(len(x) // 2, int(FADE * SR))
    ramp = np.linspace(0.0, 1.0, n, dtype=np.float32)
    x[:n] *= ramp
    x[-n:] *= ramp[::-1]
    return x


def write_wav(x: np.ndarray, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "f32le", "-ar", str(SR), "-ac", "1", "-i", "-",
                    "-c:a", "pcm_s16le", str(dst)], input=x.astype(np.float32).tobytes(), check=True)


def integrated(x: np.ndarray) -> float:
    err = subprocess.run(["ffmpeg", "-hide_banner", "-f", "f32le", "-ar", str(SR), "-ac", "1", "-i", "-",
                          "-af", "ebur128", "-f", "null", "-"], input=x.tobytes(), check=True, capture_output=True).stderr.decode()
    return float(err[err.rindex("I:"):].split()[1])


def main() -> None:
    v6 = json.loads((DATA / "narration.json").read_text())
    out: dict[str, dict] = {}
    for line, (src, spans, text) in CUTS.items():
        x = decode(V6 / f"{src}.mp3")
        total = len(x) / SR
        parts, words, t = [], [], 0.0
        for s, e in spans:
            e = total if e is None else e
            parts.append(faded(x[int(s * SR): int(e * SR)]))
            for w in v6[src]["words"]:
                # Whisper's word edges are loose (it gives "fMRIght." the pause after it
                # and "You" the "-st" before it), so a word is kept when at least 30 % of
                # its timed span falls inside the kept stretch.
                inside = min(e, w["e"]) - max(s, w["s"])
                if inside > 0.3 * max(w["e"] - w["s"], 0.01):
                    words.append({"w": w["w"], "s": round(max(0.0, w["s"] - s) + t, 3), "e": round(min(e, w["e"]) - s + t, 3)})
            t += e - s
        if line in RETIME:
            fixed = [{"w": w, "s": a, "e": b} for w, a, b in RETIME[line]]
            words = fixed + [w for w in words if w["w"].lower() not in {"you", "first,"}]
        got = " ".join(w["w"] for w in words)
        if got != text:
            raise SystemExit(f"{line}: kept words {got!r} != script {text!r}: move the cut points")
        y = np.concatenate(parts)
        # A cut keeps less of the take's quiet tail than the whole line did, so it reads
        # louder: bring it back to the line level with a plain gain (only ever down here).
        y = y * np.float32(10 ** ((LUFS - integrated(y)) / 20))
        write_wav(y, OUT / f"{line}.wav")
        out[line] = {"text": text, "duration": round(len(y) / SR, 3), "standin": False, "src": f"media/narration_short/{line}.wav", "words": words}
        print(f"{line}: {len(y) / SR:.2f}s  {got}")
    for line in WHOLE:
        out[line] = {**v6[line], "src": f"media/narration_v6/{line}.mp3"}
        print(f"{line}: {v6[line]['duration']:.2f}s  (whole v6 take)")
    (DATA / "narration_short.json").write_text(json.dumps(out, indent=1) + "\n")
    print(f"narration_short.json  {len(out)} lines")


if __name__ == "__main__":
    main()
