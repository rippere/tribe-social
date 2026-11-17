"""Build the per-second norm band from the UGC baseline predictions and sanity-check it.

Runs where the *_preds.npy live (the Spark `tribe` container), with the scorer package on the path:
    python build_norm_band.py <preds_dir> <vetting.json> <out_band.json> [<probe_preds.npy> ...]

Checks printed (no per-clip IDs in the output):
- leave-one-out: each reference clip ranked against a band built from the other clips. If the band is
  calibrated, about 25% of ranked seconds fall below P25 and 25% above P75.
- probes: any extra clips (not in the band) diagnosed against the full band.

The band's lag is norms.LAG_S = 0: TRIBE v2 output is stimulus-aligned, so a flag's video seconds equal
its predicted seconds and the opening seconds are ranked too (there is no BOLD warm-up to skip).
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, "/tribe/work_main")
from tribe_scoring import norms  # noqa: E402
from tribe_scoring.run_and_save import _BATCH_MASKS  # noqa: E402


def main(preds_dir, vetting, out, *probes):
    include = {x["name"] for x in json.loads(Path(vetting).read_text()) if x.get("include")}
    tcs = [norms.timecourses(np.load(p), _BATCH_MASKS)
           for p in sorted(Path(preds_dir).glob("*_preds.npy")) if p.name[:-10] in include]
    meta = {"source": "UGC baseline: public short-form ads, 12-60 s, one per channel",
            "masks": "Destrieux anatomical (tribe_scoring roi_masks_fsaverage5.json)",
            "stack": "DGX Spark, whisperx CPU int8; do not rank RunPod-scored clips against this band"}
    band = norms.build_band(tcs, name="ugc64-v1", meta=meta)
    norms.save_band(band, Path(out))
    print(f"band: {band['n_clips']} clips, predicted seconds 0-{band['n_seconds'] - 1} (lag {band['lag_s']} s) "
          f"(n at last second {band['n_per_second'][-1]}), {Path(out).stat().st_size // 1024} KB")

    below = above = total = 0
    n_flags = []
    for i, tc in enumerate(tcs):
        loo = norms.build_band(tcs[:i] + tcs[i + 1:], name="loo")
        d = norms.diagnose(tc, loo)
        for r in d["ranks"].values():
            v = [x for x in r if x is not None]
            below += sum(x < 25 for x in v); above += sum(x > 75 for x in v); total += len(v)
        n_flags.append(len(d["flags"]))
    print(f"leave-one-out: {100 * below / total:.1f}% of ranked seconds < P25, "
          f"{100 * above / total:.1f}% > P75 (expect ~25/25); flags per clip median "
          f"{int(np.median(n_flags))}, range {min(n_flags)}-{max(n_flags)}")

    for p in probes:
        d = norms.diagnose(norms.timecourses(np.load(p), _BATCH_MASKS), band)
        print(f"\nprobe {Path(p).stem}: {d['n_seconds']} s, ranked predicted s {d['ranked_seconds']}")
        for f in d["flags"][:6]:
            print(f"  {f['signal']:10s} {f['direction']:4s} video ~{f['video_start_s']}-{f['video_end_s']} s "
                  f"(pred {f['pred_start_s']}-{f['pred_end_s']}), mean rank P{f['mean_rank']:.0f}, "
                  f"extreme P{f['extreme_rank']:.0f}")


if __name__ == "__main__":
    main(*sys.argv[1:])
