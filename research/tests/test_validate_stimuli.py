"""Tests for validate_stimuli.py, on synthetic clips built with ffmpeg.

Each case is one base of four variants where exactly one thing is wrong, so a
passing test proves the gate catches that specific defect and nothing else.
Fixture loudness is calibrated with ffmpeg's ebur128 filter, a different code
path from the loudnorm measurement the gate uses, so the two check each other.
"""
import csv
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import validate_stimuli as vs

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")

OPENINGS = {"spoken": ("red", 300), "visual": ("green", 500), "text": ("blue", 700), "cold": ("gray", 900)}


def ebur128_lufs(path: Path) -> float:
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-af", "ebur128",
                        "-f", "null", "-"], capture_output=True, text=True, check=True)
    summary = r.stderr[r.stderr.rindex("Summary:"):]
    return float(re.search(r"I:\s+(-?[0-9.]+) LUFS", summary).group(1))


def make_clip(path: Path, variant: str, *, body_src: str = "testsrc2", body_seed: int = 42,
              hook_frames: int = 90, body_frames: int = 360, size: str = "1080x1920",
              rate: str = "30", gain_db: float = 0.0) -> None:
    """Opening unique to the variant, then a body shared across the base, at -14 LUFS plus gain_db."""
    color, freq = OPENINGS[variant]
    graph = (
        f"color=c={color}:s={size}:r={rate}:d=10,trim=end_frame={hook_frames}[v0];"
        f"{body_src}=s={size}:r={rate}:d=30,trim=end_frame={body_frames}[v1];"
        f"sine=f={freq}:d={hook_frames / 30}:sample_rate=48000[a0];"
        f"anoisesrc=d={body_frames / 30}:c=pink:seed={body_seed}:a=0.3:r=48000[a1];"
        "[v0][a0][v1][a1]concat=n=2:v=1:a=1[v][a]"
    )
    raw = path.with_suffix(".raw.mp4")
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-filter_complex", graph, "-map", "[v]", "-map", "[a]",
         "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k",
         str(raw)],
        check=True,
    )
    correction = -14.0 - ebur128_lufs(raw) + gain_db
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", str(raw), "-c:v", "copy",
         "-af", f"volume={correction}dB", "-c:a", "aac", "-b:a", "128k", str(path)],
        check=True,
    )
    raw.unlink()


def delay_audio(src: Path, dst: Path, ms: int) -> None:
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-c:v", "copy",
                    "-af", f"adelay={ms}:all=1,atrim=end=15", "-c:a", "aac", "-b:a", "128k", str(dst)],
                   check=True)


@pytest.fixture(scope="module")
def good_base(tmp_path_factory) -> Path:
    d = tmp_path_factory.mktemp("good")
    for v in vs.VARIANTS:
        make_clip(d / f"base01_{v}.mp4", v)
    return d


def base_with(good_base: Path, tmp_path: Path, replace: str | None = None, drop: str | None = None, **kw) -> Path:
    """Copy the good base, then swap one variant for a defective one or drop it."""
    for v in vs.VARIANTS:
        if v in (replace, drop):
            continue
        shutil.copy(good_base / f"base01_{v}.mp4", tmp_path / f"base01_{v}.mp4")
    if replace:
        make_clip(tmp_path / f"base01_{replace}.mp4", replace, **kw)
    return tmp_path


def problems_for(folder: Path, bases: int = 1) -> list[str]:
    clips, base_problems, _ = vs.validate(folder, bases)
    out = [p for ps in base_problems.values() for p in ps]
    out += [f"{c.variant}: {p}" for b in clips.values() for c in b.values() for p in c.problems]
    return out


def test_clean_base_passes(good_base, tmp_path):
    manifest = tmp_path / "manifest.csv"
    assert vs.main([str(good_base), "--bases", "1", "--manifest", str(manifest)]) == 0
    rows = list(csv.DictReader(manifest.open()))
    assert [r["status"] for r in rows] == ["PASS"] * 4
    assert all(len(r["sha256"]) == 64 for r in rows)
    assert all(int(r["frames"]) == 450 for r in rows)
    assert all(float(r["body_ssim_min"]) > 0.99 for r in rows)


def test_gate_loudness_agrees_with_independent_meter(good_base):
    for v in vs.VARIANTS:
        clip = good_base / f"base01_{v}.mp4"
        assert abs(vs.loudness(clip) - ebur128_lufs(clip)) < 0.5
        assert abs(ebur128_lufs(clip) + 14) < 0.6  # AAC re-encode drifts a few tenths


def test_different_footage_after_hook_fails(good_base, tmp_path):
    probs = problems_for(base_with(good_base, tmp_path, replace="text", body_src="smptehdbars"))
    assert any("text" in p and "footage after 0:03 differs" in p for p in probs), probs
    assert "likely culprit: text" in probs
    assert not any("audio after" in p for p in probs), probs


def test_different_audio_after_hook_fails(good_base, tmp_path):
    probs = problems_for(base_with(good_base, tmp_path, replace="cold", body_seed=7))
    assert any("cold" in p and "audio after 0:03 differs" in p for p in probs), probs
    assert "likely culprit: cold" in probs
    assert not any("footage after" in p for p in probs), probs


def test_hook_one_frame_short_with_matching_length_fails(good_base, tmp_path):
    """The reviewer's repro: same total frames, body starting one frame early."""
    probs = problems_for(base_with(good_base, tmp_path, replace="visual", hook_frames=89, body_frames=361))
    assert not any(p.startswith("variants differ in length") for p in probs), probs
    assert any("visual's body starts 1 frame(s) early" in p or "body starts 1 frame(s) late" in p
               for p in probs), probs


def test_audio_offset_of_one_frame_fails(good_base, tmp_path):
    base_with(good_base, tmp_path, drop="cold")
    delay_audio(good_base / "base01_cold.mp4", tmp_path / "base01_cold.mp4", 33)
    probs = problems_for(tmp_path)
    assert any("cold" in p and "audio after 0:03 is offset" in p for p in probs), probs


def test_audio_offset_within_tolerance_passes(good_base, tmp_path):
    base_with(good_base, tmp_path, drop="cold")
    delay_audio(good_base / "base01_cold.mp4", tmp_path / "base01_cold.mp4", 5)
    assert problems_for(tmp_path) == []


def test_missing_variant_fails(good_base, tmp_path):
    probs = problems_for(base_with(good_base, tmp_path, drop="cold"))
    assert "missing cold" in probs


def test_length_mismatch_inside_base_fails(good_base, tmp_path):
    probs = problems_for(base_with(good_base, tmp_path, replace="visual", body_frames=390))
    assert any(p.startswith("variants differ in length") for p in probs), probs


def test_off_target_loudness_fails(good_base, tmp_path):
    probs = problems_for(base_with(good_base, tmp_path, replace="spoken", gain_db=-3))
    assert any(p.startswith("spoken: loudness -17") for p in probs), probs


def test_wrong_resolution_fails(good_base, tmp_path):
    probs = problems_for(base_with(good_base, tmp_path, replace="text", size="720x1280"))
    assert any("resolution 720x1280" in p for p in probs), probs


def test_ntsc_frame_rate_fails(good_base, tmp_path):
    probs = problems_for(base_with(good_base, tmp_path, replace="visual", rate="30000/1001"))
    assert any("frame rate 29.970" in p for p in probs), probs


def test_undelivered_base_and_bad_name_block_exit(good_base, tmp_path):
    for v in vs.VARIANTS:
        shutil.copy(good_base / f"base01_{v}.mp4", tmp_path / f"base01_{v}.mp4")
    shutil.copy(good_base / "base01_cold.mp4", tmp_path / "Base 2 cold FINAL.mp4")
    clips, base_problems, stray = vs.validate(tmp_path, 2)
    assert base_problems[1] == [] and all(c.ok for c in clips[1].values())
    assert base_problems[2] == ["not delivered"]
    assert stray == ["Base 2 cold FINAL.mp4"]
    assert vs.main([str(tmp_path), "--bases", "2"]) == 1


def test_corrupt_file_is_reported_not_crashed(good_base, tmp_path):
    base_with(good_base, tmp_path, drop="text")
    (tmp_path / "base01_text.mp4").write_bytes(b"not a video")
    probs = problems_for(tmp_path)
    assert any(p.startswith("text: unreadable by ffprobe") for p in probs), probs
