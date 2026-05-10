"""
tribe-score — automate the tribe-social RunPod pipeline.

Subcommands:
  batch    Full Phase 1b: provision pod → upload reels → score → download → analyze
  score    Phase 2 single video: provision → score → download preds → local analyze
  analyze  Local only: run phase1b_correlation.py on existing scores.csv
"""

import argparse
import sys
from pathlib import Path

from .config import load_config
from . import pipeline


def _cmd_batch(args) -> None:
    cfg = load_config()
    if args.reels_dir:
        cfg.tribe_dir = Path(args.reels_dir).parent  # allow override
    pipeline.run_batch(cfg, no_analyze=args.no_analyze)


def _cmd_score(args) -> None:
    cfg = load_config()
    video = Path(args.video).resolve()
    label = args.label or video.stem
    pipeline.run_single(cfg, video, label)


def _cmd_analyze(args) -> None:
    cfg = load_config()
    pipeline.run_analyze(cfg)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="tribe-score",
        description="Automate TRIBE v2 scoring pipeline via RunPod.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # batch
    p_batch = sub.add_parser("batch", help="Full Phase 1b corpus pipeline")
    p_batch.add_argument("--reels-dir", default=None,
                         help="Override reels directory (default: tribe-social/reels/)")
    p_batch.add_argument("--no-analyze", action="store_true",
                         help="Skip local phase1b analysis after download")
    p_batch.set_defaults(func=_cmd_batch)

    # score
    p_score = sub.add_parser("score", help="Score a single video (Phase 2)")
    p_score.add_argument("video", help="Path to .mp4 file")
    p_score.add_argument("--label", default=None,
                         help="Label for output files (default: video stem)")
    p_score.set_defaults(func=_cmd_score)

    # analyze
    p_analyze = sub.add_parser("analyze", help="Run phase1b_correlation.py locally")
    p_analyze.set_defaults(func=_cmd_analyze)

    args = parser.parse_args()
    args.func(args)
