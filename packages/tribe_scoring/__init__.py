"""tribe_scoring — single shared TRIBE v2 scoring module.

This package is the canonical home of ``run_and_save.py``, used by:
  - research/ (visualize.py, and the tribe_score RunPod upload pipeline)
  - apps/pod_server/server.py
  - apps/runpod_handler/handler.py

It replaces the three byte-identical copies that previously lived in
research/, apps/pod_server/ and apps/runpod_handler/.
"""

from .run_and_save import load_model, quick_scores, _BATCH_MASKS

__all__ = ["load_model", "quick_scores", "_BATCH_MASKS"]
