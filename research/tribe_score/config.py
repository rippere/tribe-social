from dataclasses import dataclass, field
from pathlib import Path
import os
import sys

try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv(*a, **kw): pass  # noqa: E704


TRIBE_DIR = Path(__file__).parent.parent


@dataclass
class Config:
    runpod_api_key: str
    gpu_type_id: str
    gpu_fallback_ids: list[str]
    image: str
    ssh_key_path: Path
    ssh_user: str
    container_disk_gb: int
    hf_token: str
    tribe_dir: Path = field(default_factory=lambda: TRIBE_DIR)

    @property
    def reels_dir(self) -> Path:
        return self.tribe_dir / "reels"

    @property
    def engagement_csv(self) -> Path:
        return self.tribe_dir / "engagement.csv"

    @property
    def scores_csv(self) -> Path:
        return self.tribe_dir / "scores.csv"


def load_config() -> Config:
    load_dotenv(TRIBE_DIR / ".env")

    missing = []

    def req(key: str) -> str:
        val = os.environ.get(key, "").strip()
        if not val:
            missing.append(key)
        return val

    _fallback_default = "NVIDIA A100-SXM4-80GB,NVIDIA RTX A6000,NVIDIA GeForce RTX 4090"
    cfg = Config(
        runpod_api_key    = req("RUNPOD_API_KEY"),
        gpu_type_id       = os.environ.get("RUNPOD_GPU_TYPE_ID", "NVIDIA A100 80GB PCIe"),
        gpu_fallback_ids  = [
            g.strip() for g in
            os.environ.get("RUNPOD_GPU_FALLBACK_IDS", _fallback_default).split(",")
            if g.strip()
        ],
        image             = os.environ.get(
            "RUNPOD_IMAGE",
            "runpod/pytorch:2.1.0-py3.10-cuda11.8.0-devel-ubuntu22.04"
        ),
        ssh_key_path      = Path(os.environ.get("RUNPOD_SSH_KEY_PATH", "~/.ssh/id_rsa")).expanduser(),
        ssh_user          = os.environ.get("RUNPOD_SSH_USER", "root"),
        container_disk_gb = int(os.environ.get("RUNPOD_CONTAINER_DISK_GB", "50")),
        hf_token          = req("HF_TOKEN"),
    )

    if missing:
        print(f"[tribe-score] Missing required env vars: {', '.join(missing)}")
        print(f"  → Set them in {TRIBE_DIR / '.env'}")
        sys.exit(1)

    if not cfg.ssh_key_path.exists():
        print(f"[tribe-score] SSH key not found: {cfg.ssh_key_path}")
        print("  → Set RUNPOD_SSH_KEY_PATH in .env")
        sys.exit(1)

    return cfg
