"""
validate_stimuli.py — QA gate for the hook-test stimulus set (PREREGISTRATION.md §3).

Every clip must pass before scoring or freeze. A base video with one bad variant
measures nothing, so a single failure fails the whole base.

Checks, per clip:
    name        baseNN_{spoken,visual,text,cold}.mp4
    video       1080 x 1920, 30 fps, 15 to 25 seconds
    loudness    integrated loudness within ±1 LU of -14 LUFS

Checks, per base, on every pair of variants (the rule that makes or breaks the study):
    complete    all four variants present
    length      same number of decoded frames
    boundary    the body starts on the same frame (hook exactly 90 frames in all four)
    body video  frames after 0:03 match (SSIM)
    body audio  audio after 0:03 matches and is not offset by more than 10 ms

Usage:
    .venv/bin/python validate_stimuli.py stimuli/
    .venv/bin/python validate_stimuli.py stimuli/ --manifest stimuli_manifest.csv

Exit code 0 only when every expected base is complete and passes.
Requires ffmpeg and ffprobe on PATH.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from itertools import combinations
from pathlib import Path

import numpy as np
from rich.console import Console
from rich.table import Table
from scipy.signal import correlate, correlation_lags

console = Console()

VARIANTS = ("spoken", "visual", "text", "cold")
NAME_RE = re.compile(r"^base(\d{2})_(spoken|visual|text|cold)\.mp4$")

WIDTH, HEIGHT, FPS = 1080, 1920, 30
MIN_S, MAX_S = 15.0, 25.0
TARGET_LUFS, LUFS_TOL = -14.0, 1.0
HOOK_FRAMES = 90  # 3 seconds at 30 fps
HOOK_S = HOOK_FRAMES / FPS
MIN_BODY_SSIM = 0.95
MIN_BODY_AUDIO_R = 0.95

AUDIO_RATE = 8000
MAX_LAG = 400  # search ±50 ms so an offset is measured, not just failed
MAX_AUDIO_OFFSET_MS = 10.0
BOUNDARY_SEARCH = 2  # frames either side of 0:03
BOUNDARY_WINDOW = 60  # frames of body compared when locating the boundary
BOUNDARY_MARGIN = 0.01  # SSIM gain a shifted alignment needs before it counts as the true one


@dataclass
class Clip:
    path: Path
    base: int
    variant: str
    width: int = 0
    height: int = 0
    fps: float = 0.0
    duration: float = 0.0
    frames: int = 0
    lufs: float | None = None
    body_ssim: float | None = None  # worst pairwise value involving this clip
    body_audio_r: float | None = None
    sha256: str = ""
    problems: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.problems


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, check=False)


def probe(clip: Clip) -> None:
    """Fill resolution, frame rate, duration and decoded frame count from ffprobe."""
    r = _run([
        "ffprobe", "-v", "error", "-count_frames", "-show_streams", "-show_format",
        "-of", "json", str(clip.path),
    ])
    if r.returncode != 0:
        clip.problems.append(f"unreadable by ffprobe: {r.stderr.strip()[:120]}")
        return
    try:
        info = json.loads(r.stdout)
        video = next((s for s in info["streams"] if s["codec_type"] == "video"), None)
        audio = next((s for s in info["streams"] if s["codec_type"] == "audio"), None)
        if video is None:
            clip.problems.append("no video stream")
            return
        num, den = (int(x) for x in video["r_frame_rate"].split("/"))
        clip.width, clip.height = int(video["width"]), int(video["height"])
        clip.fps = num / den if den else 0.0
        clip.duration = float(info["format"]["duration"])
        clip.frames = int(video["nb_read_frames"])
    except (KeyError, ValueError, TypeError) as exc:
        clip.width = 0
        clip.problems.append(f"ffprobe output missing a field ({exc!r})")
        return
    if audio is None:
        clip.problems.append("no audio stream (spec requires real audio)")


def loudness(path: Path) -> float | None:
    """Integrated loudness in LUFS via ffmpeg's loudnorm analysis pass."""
    r = _run([
        "ffmpeg", "-hide_banner", "-nostats", "-i", str(path),
        "-af", "loudnorm=print_format=json", "-f", "null", "-",
    ])
    if r.returncode != 0:
        return None
    m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", r.stderr, re.DOTALL)
    if not m:
        return None
    value = json.loads(m.group(0))["input_i"]
    return None if value in ("-inf", "inf") else float(value)


def ssim(a: Path, b: Path, start_a: int, start_b: int, n_frames: int | None = None) -> float | None:
    """Mean SSIM of two clips from the given frame indices, at quarter resolution."""
    def trim(start: int) -> str:
        end = f":end_frame={start + n_frames}" if n_frames else ""
        return f"trim=start_frame={start}{end},setpts=PTS-STARTPTS,scale=270:480"
    graph = f"[0:v]{trim(start_a)}[a];[1:v]{trim(start_b)}[b];[a][b]ssim"
    r = _run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(a), "-i", str(b),
              "-lavfi", graph, "-f", "null", "-"])
    if r.returncode != 0:
        return None
    m = re.search(r"All:([0-9.]+)", r.stderr)
    return float(m.group(1)) if m else None


def body_ssim(a: Path, b: Path) -> float | None:
    return ssim(a, b, HOOK_FRAMES, HOOK_FRAMES)


def boundary_shift(a: Path, b: Path) -> int | None:
    """Frames by which b's body starts later (+) or earlier (-) than a's; 0 when aligned.

    Compares the first two seconds of body at small offsets. A shifted alignment only
    counts when it beats the unshifted one by BOUNDARY_MARGIN, so near-static footage,
    where every offset looks alike, reads as aligned rather than as noise.
    """
    scores = {}
    for k in range(-BOUNDARY_SEARCH, BOUNDARY_SEARCH + 1):
        s = ssim(a, b, HOOK_FRAMES, HOOK_FRAMES + k, BOUNDARY_WINDOW)
        if s is not None:
            scores[k] = s
    if 0 not in scores:
        return None
    best = max(scores, key=scores.get)
    return best if scores[best] - scores[0] > BOUNDARY_MARGIN else 0


def _body_audio(path: Path) -> np.ndarray | None:
    r = subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-ss", str(HOOK_S), "-i", str(path),
         "-vn", "-ac", "1", "-ar", str(AUDIO_RATE), "-f", "s16le", "-"],
        capture_output=True, check=False,
    )
    if r.returncode != 0:
        return None
    return np.frombuffer(r.stdout, dtype=np.int16).astype(np.float64)


def body_audio(a: Path, b: Path) -> tuple[float, float] | None:
    """Best correlation of the two clips' audio after 0:03 within ±50 ms, and that offset in ms."""
    x, y = _body_audio(a), _body_audio(b)
    if x is None or y is None:
        return None
    n = min(len(x), len(y))
    if n < AUDIO_RATE:  # under a second of audio after the hook
        return None
    x, y = x[:n] - x[:n].mean(), y[:n] - y[:n].mean()
    norm = np.sqrt((x * x).sum() * (y * y).sum())
    if norm == 0:
        return None
    c = correlate(x, y, mode="full", method="fft")
    lags = correlation_lags(n, n, mode="full")
    window = np.abs(lags) <= MAX_LAG
    i = int(np.argmax(c[window]))
    return float(c[window][i] / norm), float(lags[window][i]) * 1000 / AUDIO_RATE


def body_audio_r(a: Path, b: Path) -> float | None:
    result = body_audio(a, b)
    return None if result is None else result[0]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def check_clip(clip: Clip) -> None:
    probe(clip)
    if clip.width == 0:
        return
    if (clip.width, clip.height) != (WIDTH, HEIGHT):
        clip.problems.append(f"resolution {clip.width}x{clip.height}, need {WIDTH}x{HEIGHT}")
    if abs(clip.fps - FPS) > 0.01:
        clip.problems.append(f"frame rate {clip.fps:.3f}, need {FPS} (not 29.97)")
    if not MIN_S <= clip.duration <= MAX_S:
        clip.problems.append(f"length {clip.duration:.2f}s, need {MIN_S:.0f} to {MAX_S:.0f}s")
    clip.lufs = loudness(clip.path)
    if clip.lufs is None:
        clip.problems.append("could not measure loudness")
    elif abs(clip.lufs - TARGET_LUFS) > LUFS_TOL:
        clip.problems.append(f"loudness {clip.lufs:.1f} LUFS, need {TARGET_LUFS:.0f} ±{LUFS_TOL:.0f}")
    clip.sha256 = sha256(clip.path)


def _worst(current: float | None, value: float | None) -> float | None:
    if value is None:
        return current
    return value if current is None else min(current, value)


def check_base(clips: dict[str, Clip]) -> list[str]:
    """Pairwise body checks across the base's variants. Returns base-level problems."""
    problems = []
    missing = [v for v in VARIANTS if v not in clips]
    if missing:
        problems.append("missing " + ", ".join(missing))
    present = [clips[v] for v in VARIANTS if v in clips and clips[v].width]
    if len(present) < 2:
        return problems

    frame_counts = {c.variant: c.frames for c in present}
    if len(set(frame_counts.values())) > 1:
        detail = ", ".join(f"{v} {n}" for v, n in frame_counts.items())
        problems.append(f"variants differ in length (frames: {detail})")

    failed_pairs: dict[str, int] = {c.variant: 0 for c in present}
    for a, b in combinations(present, 2):
        pair = f"{b.variant} vs {a.variant}"
        pair_failed = False

        shift = boundary_shift(a.path, b.path)
        if shift:
            when = "late" if shift > 0 else "early"
            problems.append(f"{pair}: {b.variant}'s body starts {abs(shift)} frame(s) {when}; "
                            f"every hook must be exactly {HOOK_FRAMES} frames")
            pair_failed = True

        s = body_ssim(a.path, b.path)
        for c in (a, b):
            c.body_ssim = _worst(c.body_ssim, s)
        if s is None or s < MIN_BODY_SSIM:
            shown = "unmeasurable" if s is None else f"{s:.3f}"
            problems.append(f"{pair}: footage after 0:03 differs (SSIM {shown}, need {MIN_BODY_SSIM})")
            pair_failed = True

        audio = body_audio(a.path, b.path)
        r = None if audio is None else audio[0]
        for c in (a, b):
            c.body_audio_r = _worst(c.body_audio_r, r)
        if audio is None or r < MIN_BODY_AUDIO_R:
            shown = "unmeasurable" if audio is None else f"{r:.3f}"
            problems.append(f"{pair}: audio after 0:03 differs (r {shown}, need {MIN_BODY_AUDIO_R})")
            pair_failed = True
        elif abs(audio[1]) > MAX_AUDIO_OFFSET_MS:
            problems.append(f"{pair}: audio after 0:03 is offset by {audio[1]:+.0f} ms")
            pair_failed = True

        if pair_failed:
            failed_pairs[a.variant] += 1
            failed_pairs[b.variant] += 1

    # One variant failing against every other one is the odd one out; say so.
    others = len(present) - 1
    culprits = [v for v, n in failed_pairs.items() if n == others]
    if len(culprits) == 1 and others > 1:
        problems.append(f"likely culprit: {culprits[0]}")
    return problems


def validate(folder: Path, expected_bases: int) -> tuple[dict[int, dict[str, Clip]], dict[int, list[str]], list[str]]:
    bases: dict[int, dict[str, Clip]] = {}
    stray: list[str] = []
    for p in sorted(folder.iterdir()):
        if p.name.startswith(".") or p.is_dir():
            continue
        m = NAME_RE.match(p.name)
        if not m:
            if p.suffix.lower() in (".mp4", ".mov", ".m4v"):
                stray.append(p.name)
            continue
        clip = Clip(path=p, base=int(m.group(1)), variant=m.group(2))
        bases.setdefault(clip.base, {})[clip.variant] = clip

    base_problems: dict[int, list[str]] = {}
    for b in range(1, expected_bases + 1):
        clips = bases.get(b, {})
        for c in clips.values():
            check_clip(c)
        base_problems[b] = check_base(clips) if clips else ["not delivered"]
    for b in bases:
        if b > expected_bases or b < 1:
            base_problems[b] = [f"base number outside 01 to {expected_bases:02d}"]
    return bases, base_problems, stray


def write_manifest(path: Path, bases: dict[int, dict[str, Clip]], base_problems: dict[int, list[str]]) -> None:
    cols = ["filename", "base", "variant", "width", "height", "fps", "duration_s", "frames",
            "lufs", "body_ssim_min", "body_audio_r_min", "sha256", "status", "problems"]
    with path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(cols)
        for b in sorted(bases):
            base_ok = not base_problems.get(b)
            for v in VARIANTS:
                c = bases[b].get(v)
                if c is None:
                    continue
                w.writerow([
                    c.path.name, f"{c.base:02d}", c.variant, c.width, c.height, f"{c.fps:.3f}",
                    f"{c.duration:.3f}", c.frames,
                    "" if c.lufs is None else f"{c.lufs:.2f}",
                    "" if c.body_ssim is None else f"{c.body_ssim:.4f}",
                    "" if c.body_audio_r is None else f"{c.body_audio_r:.4f}",
                    c.sha256, "PASS" if c.ok and base_ok else "FAIL", "; ".join(c.problems),
                ])


def report(bases, base_problems, stray, expected_bases: int) -> int:
    table = Table(title="Hook-test stimuli", show_lines=False)
    for col in ("Base", "Status", "What to fix"):
        table.add_column(col)
    passed = 0
    for b in sorted(base_problems):
        clip_issues = [f"{c.variant}: {p}" for c in bases.get(b, {}).values() for p in c.problems]
        issues = base_problems[b] + clip_issues
        if issues == ["not delivered"]:
            status = "[dim]waiting[/dim]"
        elif issues:
            status = "[red]FAIL[/red]"
        else:
            status, passed = "[green]PASS[/green]", passed + 1
        table.add_row(f"{b:02d}", status, "\n".join(issues))
    console.print(table)
    for name in stray:
        console.print(f"[yellow]Ignored {name}: name must look like base03_spoken.mp4[/yellow]")
    console.print(f"\n[bold]{passed} of {expected_bases} bases pass.[/bold]")
    return 0 if passed == expected_bases and len(base_problems) == expected_bases else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("folder", type=Path, help="folder holding the baseNN_variant.mp4 files")
    parser.add_argument("--bases", type=int, default=18, help="bases expected (pre-registered: 18)")
    parser.add_argument("--manifest", type=Path, help="write a per-clip CSV with measurements and SHA-256")
    args = parser.parse_args(argv)

    for tool in ("ffmpeg", "ffprobe"):
        if shutil.which(tool) is None:
            console.print(f"[red]{tool} not found on PATH.[/red]")
            return 2
    if not args.folder.is_dir():
        console.print(f"[red]{args.folder} is not a folder.[/red]")
        return 2

    bases, base_problems, stray = validate(args.folder, args.bases)
    if args.manifest:
        write_manifest(args.manifest, bases, base_problems)
        console.print(f"Manifest written to {args.manifest}")
    return report(bases, base_problems, stray, args.bases)


if __name__ == "__main__":
    sys.exit(main())
