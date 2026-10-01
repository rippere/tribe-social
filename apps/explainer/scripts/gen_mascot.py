"""Generate the mascot shots in mascot_shots.json with Kling 3.0 via the Higgsfield CLI.

Each shot runs anchor-to-anchor (start and end frames from <media>/v2/anchors), so
shots are independent and run in parallel. Results land in <media>/v2/clips as
<name>.mp4 plus the job record <name>.json. Existing clips are skipped unless named.

    python scripts/gen_mascot.py --media $EXPLAINER_MEDIA [names...]
"""

from __future__ import annotations

import argparse
import json
import subprocess
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).parent


def generate(name: str, start: str, end: str, prompt: str, v2: Path) -> str:
    anchors, clips = v2 / "anchors", v2 / "clips"
    out = subprocess.run(
        ["higgsfield", "generate", "create", "kling3_0", "--mode", "pro", "--duration", "5", "--sound", "off",
         "--aspect_ratio", "16:9", "--start-image", str(anchors / f"A_{start}.png"),
         "--end-image", str(anchors / f"A_{end}.png"), "--prompt", prompt, "--wait", "--json"],
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
    p.add_argument("--workers", type=int, default=6)
    a = p.parse_args()
    spec = json.loads((HERE / "mascot_shots.json").read_text())
    v2 = a.media / "v2"
    todo = [
        (n, s, e, spec["prefix"] + text + spec["suffix"])
        for n, (s, e, text) in spec["shots"].items()
        if ((n in a.names) if a.names else not (v2 / "clips" / f"{n}.mp4").exists())
    ]
    print(f"generating {len(todo)}: {' '.join(t[0] for t in todo)}", flush=True)
    with ThreadPoolExecutor(a.workers) as pool:
        for msg in pool.map(lambda t: generate(*t, v2), todo):
            print(msg, flush=True)


if __name__ == "__main__":
    main()
