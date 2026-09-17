"""End-to-end pipeline orchestration."""

import subprocess
import sys
import time
from pathlib import Path

from rich.console import Console
from rich.rule import Rule

from .config import Config
from . import runpod, remote

console = Console()

# The shared scoring module now lives in the monorepo's tribe_scoring package
# (packages/tribe_scoring/run_and_save.py). It is uploaded to the pod as a
# standalone file named run_and_save.py and run there with `python run_and_save.py`.
_SCORING_DIR = Path(__file__).resolve().parents[2] / "packages" / "tribe_scoring"

# Files uploaded to RunPod for batch scoring (absolute source paths)
_REMOTE_SCRIPTS = [_SCORING_DIR / "run_and_save.py"]
_REMOTE_WORK_DIR = "/workspace/tribe"


def _step(msg: str) -> None:
    console.print(f"\n[bold cyan]▸[/bold cyan] {msg}")


def _ok(msg: str) -> None:
    console.print(f"  [green]✓[/green] {msg}")


def _warn(msg: str) -> None:
    console.print(f"  [yellow]![/yellow] {msg}")


def _note(msg: str) -> None:
    """Informational. For facts about the data that are expected and not actionable —
    distinct from _warn, which means 'something needs fixing'."""
    console.print(f"  [dim]·[/dim] [dim]{msg}[/dim]")


# Engagement fields the correlation analysis can actually use. `saves` and
# `shares` are deliberately NOT here: neither is exposed publicly by YouTube,
# which is where the whole corpus comes from. They were the originally-intended
# primary metrics back when the corpus was going to be Instagram Reels, and
# demanding them made this check warn on every run about data that can never
# arrive. Phase 1b uses likes-per-1k-views as its engagement proxy instead.
_REQUIRED_ENGAGEMENT_COLS = ["filename", "views", "likes"]
_OPTIONAL_ENGAGEMENT_COLS = ["comments", "shares"]


def _check_engagement_coverage(engagement_csv: Path) -> None:
    import pandas as pd
    if not engagement_csv.exists():
        _warn(f"engagement.csv not found at {engagement_csv} — Phase 1b will fail without it")
        return

    df = pd.read_csv(engagement_csv)
    total = len(df)

    missing_cols = [c for c in _REQUIRED_ENGAGEMENT_COLS if c not in df.columns]
    if missing_cols:
        _warn(
            f"engagement.csv: missing required column(s) {', '.join(missing_cols)} — "
            "Phase 1b cannot compute its engagement proxy without them."
        )
        return

    gaps = {
        col: int(df[col].isna().sum())
        for col in _REQUIRED_ENGAGEMENT_COLS
        if col != "filename" and df[col].isna().any()
    }
    if gaps:
        detail = ", ".join(f"{n}/{total} missing {col}" for col, n in gaps.items())
        _warn(
            f"engagement.csv: {detail} — fill these in before Phase 1b "
            "for valid correlation results."
        )
    else:
        _ok(f"engagement.csv: {total} rows, views + likes complete")

    # Optional columns: report as information, never as a problem to fix.
    for col in _OPTIONAL_ENGAGEMENT_COLS:
        if col not in df.columns:
            continue
        present = int(df[col].notna().sum())
        if present == 0:
            _note(f"engagement.csv: '{col}' column is empty (not public on YouTube) — not used as an outcome")
        elif present < total:
            _note(f"engagement.csv: '{col}' present for {present}/{total} rows — partial, not used as an outcome")


def run_batch(cfg: Config, no_analyze: bool = False) -> None:
    """
    Full Phase 1b pipeline:
      provision pod → upload → score → download scores.csv → terminate → analyze
    """
    reels = list(cfg.reels_dir.glob("*.mp4"))
    if not reels:
        console.print(f"[red]No .mp4 files found in {cfg.reels_dir}[/red]")
        sys.exit(1)

    console.print(Rule("[bold]tribe-score batch[/bold]"))
    gpu_list = [cfg.gpu_type_id] + cfg.gpu_fallback_ids
    console.print(f"  Videos:  {len(reels)} .mp4 files")
    console.print(f"  Reels:   {cfg.reels_dir}")
    console.print(f"  GPU:     {cfg.gpu_type_id} (+ {len(cfg.gpu_fallback_ids)} fallback(s))")

    _check_engagement_coverage(cfg.engagement_csv)

    # --- Provision -------------------------------------------------------
    _step("Provisioning RunPod pod…")
    pod_id, gpu_used = runpod.provision(
        cfg.runpod_api_key, gpu_list, cfg.image, cfg.container_disk_gb
    )
    _ok(f"Pod ID: {pod_id}  GPU: {gpu_used}")

    try:
        _step("Waiting for SSH…")
        host, port = runpod.wait_for_ssh(cfg.runpod_api_key, pod_id)
        _ok(f"SSH ready → {host}:{port}")

        with remote.ssh_session(host, port, cfg.ssh_user, cfg.ssh_key_path) as sess:

            # --- Pod setup -----------------------------------------------
            _step("Installing TRIBE v2 on pod…")
            setup_cmd = (
                "pip install -q --upgrade pip && "
                "pip install -q 'tribev2 @ git+https://github.com/facebookresearch/tribev2.git' "
                "--extra-index-url https://download.pytorch.org/whl/cu118"
            )
            rc = sess.run(setup_cmd, env={"HF_TOKEN": cfg.hf_token})
            if rc != 0:
                console.print(f"[red]Pod setup failed (exit {rc}) — tribev2 install error[/red]")
                sys.exit(1)
            _ok("tribev2 installed")

            # --- Upload --------------------------------------------------
            _step(f"Uploading {len(reels)} videos + scripts…")
            scripts = list(_REMOTE_SCRIPTS)
            sess.upload(scripts + reels, _REMOTE_WORK_DIR)

            # --- Score ---------------------------------------------------
            _step("Running TRIBE v2 batch scoring…")
            cmd = (
                f"cd {_REMOTE_WORK_DIR} && "
                f"python run_and_save.py --batch-dir . --results-csv scores.csv"
            )
            exit_code = sess.run(cmd, env={"HF_TOKEN": cfg.hf_token})
            if exit_code != 0:
                console.print(f"[red]Scoring failed (exit {exit_code})[/red]")
                sys.exit(1)
            _ok("Scoring complete")

            # --- Download ------------------------------------------------
            _step("Downloading scores.csv…")
            sess.download(
                f"{_REMOTE_WORK_DIR}/scores.csv",
                cfg.scores_csv,
            )
            _ok(f"scores.csv → {cfg.scores_csv}")

    finally:
        # Always terminate to avoid surprise charges
        _step("Terminating pod…")
        try:
            runpod.terminate(cfg.runpod_api_key, pod_id)
            _ok("Pod terminated")
        except Exception as e:
            _warn(f"Failed to terminate pod {pod_id}: {e} — terminate manually!")

    # --- Analyze locally -------------------------------------------------
    if not no_analyze:
        run_analyze(cfg)


def run_single(cfg: Config, video_path: Path, label: str) -> None:
    """
    Phase 2 single-video flow:
      provision → upload video → run_and_save (single) → download preds.npy → terminate → analyze.py locally
    """
    if not video_path.exists():
        console.print(f"[red]Video not found: {video_path}[/red]")
        sys.exit(1)

    gpu_list = [cfg.gpu_type_id] + cfg.gpu_fallback_ids
    console.print(Rule(f"[bold]tribe-score score[/bold]  {label}"))
    console.print(f"  Video: {video_path}")
    console.print(f"  GPU:   {cfg.gpu_type_id} (+ {len(cfg.gpu_fallback_ids)} fallback(s))")

    _step("Provisioning RunPod pod…")
    pod_id, gpu_used = runpod.provision(
        cfg.runpod_api_key, gpu_list, cfg.image, cfg.container_disk_gb
    )
    _ok(f"Pod ID: {pod_id}  GPU: {gpu_used}")

    preds_local = cfg.tribe_dir / f"{label}_preds.npy"

    try:
        _step("Waiting for SSH…")
        host, port = runpod.wait_for_ssh(cfg.runpod_api_key, pod_id)
        _ok(f"SSH ready → {host}:{port}")

        with remote.ssh_session(host, port, cfg.ssh_user, cfg.ssh_key_path) as sess:

            # --- Pod setup -----------------------------------------------
            _step("Installing TRIBE v2 on pod…")
            setup_cmd = (
                "pip install -q --upgrade pip && "
                "pip install -q 'tribev2 @ git+https://github.com/facebookresearch/tribev2.git' "
                "--extra-index-url https://download.pytorch.org/whl/cu118"
            )
            rc = sess.run(setup_cmd, env={"HF_TOKEN": cfg.hf_token})
            if rc != 0:
                console.print(f"[red]Pod setup failed (exit {rc}) — tribev2 install error[/red]")
                sys.exit(1)
            _ok("tribev2 installed")

            _step("Uploading video + script…")
            scripts = [_SCORING_DIR / "run_and_save.py"]
            sess.upload(scripts + [video_path], _REMOTE_WORK_DIR)

            _step("Running TRIBE v2 inference…")
            cmd = (
                f"cd {_REMOTE_WORK_DIR} && "
                f"python run_and_save.py --input {video_path.name} --label {label}"
            )
            exit_code = sess.run(cmd, env={"HF_TOKEN": cfg.hf_token})
            if exit_code != 0:
                console.print(f"[red]Inference failed (exit {exit_code})[/red]")
                sys.exit(1)

            _step(f"Downloading {label}_preds.npy…")
            sess.download(
                f"{_REMOTE_WORK_DIR}/{label}_preds.npy",
                preds_local,
            )
            _ok(f"{label}_preds.npy → {preds_local}")

    finally:
        _step("Terminating pod…")
        try:
            runpod.terminate(cfg.runpod_api_key, pod_id)
            _ok("Pod terminated")
        except Exception as e:
            _warn(f"Failed to terminate pod {pod_id}: {e} — terminate manually!")

    # --- Analyze locally with analyze.py ---------------------------------
    _step("Running local analysis…")
    result = subprocess.run(
        [sys.executable, str(cfg.tribe_dir / "analyze.py"),
         "--input", str(preds_local), "--label", label],
        cwd=str(cfg.tribe_dir),
    )
    if result.returncode != 0:
        _warn("analyze.py exited with errors — check output above")


def run_analyze(cfg: Config) -> None:
    """Run phase1b_correlation.py locally (no RunPod)."""
    if not cfg.scores_csv.exists():
        console.print(f"[red]scores.csv not found: {cfg.scores_csv}[/red]")
        console.print("  Run [bold]tribe-score batch[/bold] first to generate it.")
        sys.exit(1)
    if not cfg.engagement_csv.exists():
        console.print(f"[red]engagement.csv not found: {cfg.engagement_csv}[/red]")
        sys.exit(1)

    console.print(Rule("[bold]Phase 1b — Correlation Analysis[/bold]"))
    result = subprocess.run(
        [sys.executable, str(cfg.tribe_dir / "phase1b_correlation.py")],
        cwd=str(cfg.tribe_dir),
        env={
            **__import__("os").environ,
            "TRIBE_SCORES_CSV":     str(cfg.scores_csv),
            "TRIBE_ENGAGEMENT_CSV": str(cfg.engagement_csv),
        },
    )
    if result.returncode != 0:
        _warn("phase1b_correlation.py exited with errors")
