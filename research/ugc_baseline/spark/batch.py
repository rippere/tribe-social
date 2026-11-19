"""Resumable TRIBE batch worker. Skips clips with preds or in quarantine.txt.
Writes current.json (clip, start time) so the supervisor can enforce a per-clip time limit.
A clip that raises twice is quarantined (skipped) instead of retried forever."""
import json, os, sys, time
from pathlib import Path
import numpy as np, torch
torch.cuda.set_per_process_memory_fraction(float(os.environ.get("GPU_FRAC", "0.22")))
sys.path.insert(0, "/tribe/work")
from tribe_scoring.run_and_save import load_model
W = Path("/tribe/work"); src = Path(sys.argv[1]); out = Path(sys.argv[2]); out.mkdir(exist_ok=True)
def lines(p): return [l.strip() for l in p.read_text().splitlines() if l.strip()] if p.exists() else []
quar = set(lines(W / "quarantine.txt"))
todo = [v for v in sorted(src.glob("*.mp4")) if not (out / f"{v.stem}_preds.npy").exists() and v.stem not in quar]
print(f"{len(todo)} to score ({len(quar)} quarantined)", flush=True)
model = load_model("/tribe/cache")
for i, v in enumerate(todo, 1):
    t = time.time()
    (W / "current.json").write_text(json.dumps({"clip": v.stem, "started": t, "pid": os.getpid()}))
    try:
        preds, _ = model.predict(events=model.get_events_dataframe(video_path=str(v)))
        np.save(out / f"{v.stem}_preds.npy", preds)
        print(f"DONE {i}/{len(todo)} {v.stem} shape={preds.shape} {time.time()-t:.0f}s", flush=True)
    except Exception as e:
        print(f"FAIL {i}/{len(todo)} {v.stem} {type(e).__name__}: {str(e)[:300]}", flush=True)
        with open(W / "attempts.txt", "a") as f: f.write(v.stem + "\n")
        if lines(W / "attempts.txt").count(v.stem) >= 2:
            with open(W / "quarantine.txt", "a") as f: f.write(v.stem + "\n")
            print(f"QUARANTINE {v.stem} (2 failures)", flush=True)
(W / "current.json").unlink(missing_ok=True)
print("BATCH_END", flush=True)
