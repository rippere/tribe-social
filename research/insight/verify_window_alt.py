"""Sensitivity re-run of event_effects.py with a lag-0 window (verification only).

verify_lag.py found that TRIBE's predicted timecourses co-vary with content at
lag ~0 (speech -> auditory r peaks at lag 0, ~0 by lag +5; motion energy ->
motion the same), not at the assumed 4 s lag. Under lag 0 the fixed design's
baseline (predicted s+1..s+3) holds the response and its response window
(s+4..s+7) is mostly past it.

This script runs event_effects.py's exact code with only the window constants
changed, so the two runs differ in nothing else:
    baseline = predicted s-3..s-1, response = predicted s..s+2,
    event second s kept if s - 3 >= 4 and s + 2 < n.
It is a post-hoc sensitivity check, not a replacement for the pre-registered
design; any test it finds must be read with that in mind.

Run inside the `tribe` container:
    python verify_window_alt.py --out /tribe/insight/verify/effects_lag0.json \
        --agg-out /tribe/insight/verify/effects_lag0_aggregate.json
"""
from pathlib import Path
import sys

src = Path(__file__).with_name("event_effects.py").read_text()
subs = [
    ("MIN_S = 3 ", "MIN_S = 7 "),
    ("BASE = (1, 3)", "BASE = (-3, -1)"),
    ("RESP = (4, 7)", "RESP = (0, 2)"),
    ("lo, hi = MIN_S, n - 8", "lo, hi = MIN_S, n - 3"),
]
for a, b in subs:
    if src.count(a) != 1:
        raise SystemExit(f"patch anchor not found exactly once: {a!r}")
    src = src.replace(a, b)
sys.argv[0] = "event_effects_lag0"
exec(compile(src, "event_effects_lag0", "exec"), {"__name__": "__main__"})
