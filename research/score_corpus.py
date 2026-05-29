"""
score_corpus.py — End-to-end pipeline: real corpus → RunPod scoring → ranked list.

Usage:
    # Full pipeline (provisions RunPod, uploads videos, scores, downloads results):
    .venv/bin/python score_corpus.py --corpus reels_new

    # Specify an explicit directory:
    .venv/bin/python score_corpus.py --corpus /path/to/my/reels

    # Use the existing pre-fetched corpus (same as tribe-score batch default):
    .venv/bin/python score_corpus.py --corpus reels

    # Dry-run: validate pipeline without touching RunPod (no cost):
    .venv/bin/python score_corpus.py --corpus reels_new --dry-run

    # Write ranked output to a file:
    .venv/bin/python score_corpus.py --corpus reels_new --output ranked.csv

    # Skip local correlation analysis after scoring:
    .venv/bin/python score_corpus.py --corpus reels_new --no-analyze

Env vars (loaded from .env automatically):
    RUNPOD_API_KEY  — required
    HF_TOKEN        — required
    RUNPOD_GPU_TYPE_ID, RUNPOD_IMAGE, RUNPOD_SSH_KEY_PATH, RUNPOD_SSH_USER,
    RUNPOD_CONTAINER_DISK_GB — optional (have defaults in config.py)
"""

import argparse
import sys
from pathlib import Path

# Allow running from the project root without installing the package
_HERE = Path(__file__).parent.resolve()
sys.path.insert(0, str(_HERE))

from rich.console import Console
from rich.rule import Rule
from rich.table import Table

console = Console()


def _find_corpus_dir(corpus_arg: str) -> Path:
    """Resolve --corpus to an absolute path, trying relative-to-project if needed."""
    p = Path(corpus_arg)
    if p.is_absolute():
        return p
    # Relative: try relative to CWD first, then relative to this script's dir
    candidates = [p, _HERE / corpus_arg]
    for c in candidates:
        if c.is_dir():
            return c.resolve()
    # Not found — return the canonical candidate so the error message is useful
    return (_HERE / corpus_arg).resolve()


def print_ranked(scores_csv: Path, output_path: Path | None) -> None:
    """Load scores.csv and print/write a ranked table sorted by composite_score desc."""
    import csv
    rows = []
    with open(scores_csv, newline="") as f:
        for row in csv.DictReader(f):
            rows.append(row)

    if not rows:
        console.print("[yellow]scores.csv is empty — nothing to rank.[/yellow]")
        return

    # Sort by composite_raw descending (numeric)
    try:
        rows.sort(key=lambda r: float(r.get("composite_raw", 0)), reverse=True)
    except ValueError:
        pass

    # ── Console table ──────────────────────────────────────────────────────────
    table = Table(
        title="Ranked Content — TRIBE v2 Neural Scores",
        show_header=True,
        header_style="bold cyan",
    )
    table.add_column("Rank", style="bold", justify="right", width=5)
    table.add_column("Filename",        width=28)
    table.add_column("Composite",       justify="right", width=10)
    table.add_column("Attention",       justify="right", width=10)
    table.add_column("Social",          justify="right", width=8)
    table.add_column("Valuation",       justify="right", width=10)
    table.add_column("Language",        justify="right", width=10)
    table.add_column("Motion",          justify="right", width=8)
    table.add_column("Seconds",         justify="right", width=8)

    _f = lambda r, k: f"{float(r[k]):.4f}" if k in r and r[k] != "" else "—"
    _i = lambda r, k: str(r[k]) if k in r and r[k] != "" else "—"

    for rank, row in enumerate(rows, 1):
        composite = float(row.get("composite_raw", 0))
        color = "green" if composite >= 0.65 else ("yellow" if composite >= 0.40 else "red")
        table.add_row(
            str(rank),
            row.get("filename", row.get("label", "?")),
            f"[{color}]{_f(row, 'composite_raw')}[/{color}]",
            _f(row, "attention_mean"),
            _f(row, "social_mean"),
            _f(row, "valuation_mean"),
            _f(row, "language_mean"),
            _f(row, "motion_mean"),
            _i(row, "n_seconds"),
        )

    console.print()
    console.print(table)

    # ── Verdict summary ────────────────────────────────────────────────────────
    post    = sum(1 for r in rows if float(r.get("composite_raw", 0)) >= 0.65)
    revise  = sum(1 for r in rows if 0.40 <= float(r.get("composite_raw", 0)) < 0.65)
    rethink = sum(1 for r in rows if float(r.get("composite_raw", 0)) < 0.40)
    console.print(
        f"\n  [green]POST (≥ 0.65):[/green] {post}  "
        f"[yellow]REVISE (0.40–0.65):[/yellow] {revise}  "
        f"[red]RETHINK (< 0.40):[/red] {rethink}"
    )

    # ── Optional CSV output ────────────────────────────────────────────────────
    if output_path:
        import csv as csv_mod
        fieldnames = list(rows[0].keys()) if rows else []
        with open(output_path, "w", newline="") as f:
            writer = csv_mod.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        console.print(f"\n  [dim]Ranked CSV written → {output_path}[/dim]")


def run_dry(corpus_dir: Path) -> None:
    """Validate pipeline inputs without touching RunPod."""
    console.print(Rule("[bold yellow]DRY-RUN — validating pipeline (no RunPod calls)[/bold yellow]"))

    ok = True

    # 1. Corpus dir
    if corpus_dir.is_dir():
        mp4s = list(corpus_dir.glob("*.mp4")) + list(corpus_dir.glob("*.mov"))
        if mp4s:
            console.print(f"  [green]✓[/green] Corpus dir: {corpus_dir}  ({len(mp4s)} video(s))")
            for v in mp4s[:5]:
                console.print(f"      {v.name}")
            if len(mp4s) > 5:
                console.print(f"      … and {len(mp4s) - 5} more")
        else:
            console.print(f"  [red]✗[/red] Corpus dir exists but has no .mp4/.mov files: {corpus_dir}")
            ok = False
    else:
        console.print(f"  [red]✗[/red] Corpus dir not found: {corpus_dir}")
        console.print(f"       Run [bold]make fetch[/bold] first (downloads to reels_new/)")
        ok = False

    # 2. engagement.csv
    eng_csv = _HERE / "engagement.csv"
    if eng_csv.exists():
        import csv
        with open(eng_csv) as f:
            eng_rows = list(csv.DictReader(f))
        console.print(f"  [green]✓[/green] engagement.csv: {len(eng_rows)} row(s)")
    else:
        console.print(f"  [yellow]![/yellow] engagement.csv not found at {eng_csv}")
        console.print("       Correlation analysis will be skipped.")

    # 3. run_and_save.py
    script = _HERE / "run_and_save.py"
    if script.exists():
        console.print(f"  [green]✓[/green] Scoring script: {script.name}")
    else:
        console.print(f"  [red]✗[/red] run_and_save.py not found at {script}")
        ok = False

    # 4. Env vars / config
    try:
        from tribe_score.config import load_config
        cfg = load_config()
        console.print(f"  [green]✓[/green] Config loaded — GPU: {cfg.gpu_type_id}")
        console.print(f"  [green]✓[/green] SSH key: {cfg.ssh_key_path}")
        console.print(f"  [green]✓[/green] RunPod image: {cfg.image}")
    except SystemExit:
        console.print("  [red]✗[/red] Config failed — check .env (see .env.example)")
        ok = False
    except Exception as e:
        console.print(f"  [red]✗[/red] Config error: {e}")
        ok = False

    # 5. Existing scores.csv (may be stale)
    scores_csv = _HERE / "scores.csv"
    if scores_csv.exists():
        console.print(f"  [dim]  scores.csv already exists ({scores_csv}) — will be overwritten on real run[/dim]")

    console.print()
    if ok:
        console.print("[green bold]Pipeline inputs look good.[/green bold]  Remove --dry-run to execute.")
    else:
        console.print("[red bold]Fix the issues above before running.[/red bold]")
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="score_corpus",
        description="E2E pipeline: real corpus → RunPod scoring → ranked list.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--corpus",
        default="reels_new",
        metavar="DIR",
        help="Directory of .mp4 videos to score (default: reels_new). "
             "Accepts relative or absolute paths. "
             "Use 'reels' for the pre-existing corpus.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate pipeline inputs without calling RunPod (no cost).",
    )
    parser.add_argument(
        "--output",
        default=None,
        metavar="FILE",
        help="Write ranked results CSV to this file (in addition to stdout table). "
             "Default: ranked_YYYYMMDD.csv",
    )
    parser.add_argument(
        "--no-analyze",
        action="store_true",
        help="Skip phase1b_correlation.py after downloading scores.",
    )
    args = parser.parse_args()

    corpus_dir = _find_corpus_dir(args.corpus)

    if args.dry_run:
        run_dry(corpus_dir)
        return

    # ── Real run ───────────────────────────────────────────────────────────────
    console.print(Rule("[bold]score-corpus — E2E pipeline[/bold]"))
    console.print(f"  Corpus dir:  {corpus_dir}")
    console.print(f"  Scores out:  {_HERE / 'scores.csv'}")

    if not corpus_dir.is_dir():
        console.print(f"[red]Corpus directory not found: {corpus_dir}[/red]")
        console.print("  → Run [bold]make fetch[/bold] to download viral Shorts into reels_new/")
        console.print("  → Or pass [bold]--corpus reels[/bold] to use the existing pre-scored corpus")
        console.print("  → Or use [bold]--dry-run[/bold] to diagnose without cost")
        sys.exit(1)

    mp4s = list(corpus_dir.glob("*.mp4")) + list(corpus_dir.glob("*.mov"))
    if not mp4s:
        console.print(f"[red]No .mp4/.mov files found in {corpus_dir}[/red]")
        console.print("  → Run [bold]make fetch[/bold] to download videos first")
        sys.exit(1)

    console.print(f"  Videos found: {len(mp4s)}")

    from tribe_score.config import load_config
    from tribe_score import pipeline

    cfg = load_config()

    # Point config at the resolved corpus dir (override the default reels/ path)
    # pipeline.run_batch reads cfg.reels_dir, which is cfg.tribe_dir / "reels"
    # We patch tribe_dir to make reels_dir point at corpus_dir's parent if
    # corpus_dir is named "reels", or we use a config subclass trick.
    #
    # Simplest approach: temporarily override cfg.tribe_dir to the corpus dir's
    # parent, then run_batch will look for reels/ inside it... but that only
    # works if the dir is literally named "reels".
    #
    # Better: pass the corpus_dir directly via the --reels-dir path the CLI
    # already supports (tribe_dir = corpus_dir.parent, and reels_dir = tribe_dir / "reels").
    # Since our corpus_dir might be "reels_new" we need a cleaner override.
    #
    # Cleanest: monkeypatch cfg so cfg.reels_dir returns corpus_dir.
    class _PatchedConfig:
        """Thin wrapper that overrides reels_dir only."""
        def __init__(self, base, reels_override: Path):
            self._base = base
            self._reels = reels_override

        def __getattr__(self, name):
            return getattr(self._base, name)

        @property
        def reels_dir(self) -> Path:
            return self._reels

        @property
        def engagement_csv(self) -> Path:
            return self._base.tribe_dir / "engagement.csv"

        @property
        def scores_csv(self) -> Path:
            return self._base.tribe_dir / "scores.csv"

    patched_cfg = _PatchedConfig(cfg, corpus_dir)

    pipeline.run_batch(patched_cfg, no_analyze=args.no_analyze)

    # ── Ranked output ──────────────────────────────────────────────────────────
    scores_csv = cfg.tribe_dir / "scores.csv"
    if scores_csv.exists():
        if args.output:
            out_path = Path(args.output)
        else:
            from datetime import date
            out_path = _HERE / f"ranked_{date.today().strftime('%Y%m%d')}.csv"

        print_ranked(scores_csv, out_path)
    else:
        console.print("[yellow]scores.csv not found after pipeline run — ranked output skipped.[/yellow]")


if __name__ == "__main__":
    main()
