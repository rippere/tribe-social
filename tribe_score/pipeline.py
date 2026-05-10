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

# Files uploaded to RunPod for batch scoring
_REMOTE_SCRIPTS = ["run_and_save.py"]
_REMOTE_WORK_DIR = "/workspace/tribe"


def _step(msg: str) -> None:
    console.print(f"\n[bold cyan]▸[/bold cyan] {msg}")


def _ok(msg: str) -> None:
    console.print(f"  [green]✓[/green] {msg}")


def _warn(msg: str) -> None:
    console.print(f"  [yellow]![/yellow] {msg}")


def _check_engagement_coverage(engagement_csv: Path) -> None:
    import pandas as pd
    if not engagement_csv.exists():
        _warn(f"engagement.csv not found at {engagement_csv} — Phase 1b will fail without it")
        return
    df = pd.read_csv(engagement_csv)
    missing_saves  = df["saves"].isna().sum()  if "saves"  in df.columns else len(df)
    missing_shares = df["shares"].isna().sum() if "shares" in df.columns else len(df)
    total = len(df)
    if missing_saves or missing_shares:
        _warn(
            f"engagement.csv: {missing_saves}/{total} missing saves, "
            f"{missing_shares}/{total} missing shares — "
            "fill these in before Phase 1b for valid correlation results."
        )
    else:
        _ok(f"engagement.csv: {total} rows, all saves + shares present")


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
    console.print(f"  Videos:  {len(reels)} .mp4 files")
    console.print(f"  Reels:   {cfg.reels_dir}")
    console.print(f"  GPU:     {cfg.gpu_type_id}")

    _check_engagement_coverage(cfg.engagement_csv)

    # --- Provision -------------------------------------------------------
    _step("Provisioning RunPod pod…")
    pod_id = runpod.provision(
        cfg.runpod_api_key, cfg.gpu_type_id, cfg.image, cfg.container_disk_gb
    )
    _ok(f"Pod ID: {pod_id}")

    try:
        _step("Waiting for SSH…")
        host, port = runpod.wait_for_ssh(cfg.runpod_api_key, pod_id)
        _ok(f"SSH ready → {host}:{port}")

        with remote.ssh_session(host, port, cfg.ssh_user, cfg.ssh_key_path) as sess:

            # --- Upload --------------------------------------------------
            _step(f"Uploading {len(reels)} videos + scripts…")
            scripts = [cfg.tribe_dir / s for s in _REMOTE_SCRIPTS]
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

    console.print(Rule(f"[bold]tribe-score score[/bold]  {label}"))
    console.print(f"  Video: {video_path}")
    console.print(f"  GPU:   {cfg.gpu_type_id}")

    _step("Provisioning RunPod pod…")
    pod_id = runpod.provision(
        cfg.runpod_api_key, cfg.gpu_type_id, cfg.image, cfg.container_disk_gb
    )
    _ok(f"Pod ID: {pod_id}")

    preds_local = cfg.tribe_dir / f"{label}_preds.npy"

    try:
        _step("Waiting for SSH…")
        host, port = runpod.wait_for_ssh(cfg.runpod_api_key, pod_id)
        _ok(f"SSH ready → {host}:{port}")

        with remote.ssh_session(host, port, cfg.ssh_user, cfg.ssh_key_path) as sess:

            _step("Uploading video + script…")
            scripts = [cfg.tribe_dir / "run_and_save.py"]
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
