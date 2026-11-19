"""Generate the v3 talking shots in talk_shots.json with Seedance 2.0 via the Higgsfield CLI.

Each shot lip-syncs to its slice of the narration (<media>/v3/narration/<line>.mp3)
and runs centre anchor to centre anchor (<media>/v2/anchors/A_C.png), so shots are
independent and run in parallel. Results land in <media>/v3/clips as <name>.mp4 plus
the job record <name>.json, and the audio slice as <name>.mp3 (the composition plays
that slice from the shot's first frame). Existing clips are skipped unless named.

    python scripts/gen_talk.py --media $EXPLAINER_MEDIA [names...]
"""

from __future__ import annotations

import argparse
import json
import subprocess
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).parent


def cut_audio(src: Path, dst: Path, start: float, end: float | None) -> None:
    span = ["-ss", str(start)] + (["-to", str(end)] if end is not None else [])
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(src), *span, "-c:a", "libmp3lame", "-q:a", "2", str(dst)], check=True)


def generate(name: str, shot: dict, prompt: str, media: Path, resolution: str) -> str:
    try:
        return _generate(name, shot, prompt, media, resolution)
    except (json.JSONDecodeError, OSError, subprocess.CalledProcessError) as e:
        return f"{name}: ERROR {e}"


def _generate(name: str, shot: dict, prompt: str, media: Path, resolution: str) -> str:
    clips = media / "v3" / "clips"
    line, start, end = shot["audio"]
    audio = clips / f"{name}.mp3"
    cut_audio(media / "v3" / "narration" / f"{line}.mp3", audio, start, end)
    anchor = media / "v2" / "anchors" / "A_C.png"
    out = subprocess.run(
        ["higgsfield", "generate", "create", "seedance_2_0", "--resolution", resolution, "--duration", str(shot["duration"]),
         "--aspect_ratio", "16:9", "--generate_audio", "false", "--start-image", str(anchor), "--end-image", str(anchor),
         "--audio", str(audio), "--prompt", prompt, "--wait", "--json"],
        capture_output=True, text=True,
    )
    if out.returncode != 0:
        return f"{name}: FAILED {out.stderr.strip()[-300:]}"
    job = json.loads(out.stdout)
    job = job[0] if isinstance(job, list) else job
    (clips / f"{name}.json").write_text(json.dumps(job, indent=1))
    if job.get("status") != "completed" or not job.get("result_url"):
        return f"{name}: {job.get('status')}"
    urllib.request.urlretrieve(job["result_url"], clips / f"{name}.mp4")
    return f"{name}: ok"


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--media", type=Path, required=True, help="the explainer media folder (business/explainer)")
    p.add_argument("names", nargs="*")
    p.add_argument("--resolution", default="720p")
    p.add_argument("--workers", type=int, default=8)
    a = p.parse_args()
    spec = json.loads((HERE / "talk_shots.json").read_text())
    clips = a.media / "v3" / "clips"
    clips.mkdir(parents=True, exist_ok=True)
    todo = [
        (n, s, spec["prefix"] + s["prompt"] + spec["suffix"])
        for n, s in spec["shots"].items()
        if ((n in a.names) if a.names else not (clips / f"{n}.mp4").exists())
    ]
    print(f"generating {len(todo)}: {' '.join(t[0] for t in todo)}", flush=True)
    with ThreadPoolExecutor(a.workers) as pool:
        for msg in pool.map(lambda t: generate(*t, a.media, a.resolution), todo):
            print(msg, flush=True)


if __name__ == "__main__":
    main()
