"""SSH / SFTP operations via paramiko."""

import socket
import time
from contextlib import contextmanager
from pathlib import Path

import paramiko
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, FileSizeColumn, TransferSpeedColumn

console = Console()


class SSHSession:
    def __init__(self, host: str, port: int, user: str, key_path: Path):
        self.host = host
        self.port = port
        self.user = user
        self.key_path = key_path
        self._client: paramiko.SSHClient | None = None

    def connect(self, retries: int = 6, delay: int = 10) -> None:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        for attempt in range(retries):
            try:
                client.connect(
                    self.host, port=self.port, username=self.user,
                    key_filename=str(self.key_path), timeout=15,
                    banner_timeout=30,
                )
                self._client = client
                return
            except (paramiko.ssh_exception.NoValidConnectionsError,
                    socket.error, EOFError) as e:
                if attempt == retries - 1:
                    raise
                console.print(f"  [dim]SSH not ready yet, retrying in {delay}s… ({e})[/dim]")
                time.sleep(delay)

    def close(self) -> None:
        if self._client:
            self._client.close()

    def run(self, cmd: str, env: dict[str, str] | None = None) -> int:
        """Run command, stream stdout/stderr to console. Returns exit code."""
        assert self._client
        env_prefix = " ".join(f"{k}={v}" for k, v in (env or {}).items())
        full_cmd = f"{env_prefix} {cmd}".strip() if env_prefix else cmd

        _, stdout, stderr = self._client.exec_command(full_cmd, get_pty=True)
        channel = stdout.channel

        while not channel.exit_status_ready():
            if channel.recv_ready():
                data = channel.recv(4096).decode("utf-8", errors="replace")
                console.print(data, end="", markup=False, highlight=False)
            time.sleep(0.05)

        # drain remaining output
        while channel.recv_ready():
            data = channel.recv(4096).decode("utf-8", errors="replace")
            console.print(data, end="", markup=False, highlight=False)

        return channel.recv_exit_status()

    def upload(self, local_paths: list[Path], remote_dir: str) -> None:
        assert self._client
        sftp = self._client.open_sftp()
        try:
            try:
                sftp.mkdir(remote_dir)
            except OSError:
                pass  # already exists

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                FileSizeColumn(),
                TransferSpeedColumn(),
                console=console,
            ) as progress:
                for local in local_paths:
                    remote = f"{remote_dir}/{local.name}"
                    size = local.stat().st_size
                    task = progress.add_task(f"↑ {local.name}", total=size)

                    def _callback(sent, total, t=task):
                        progress.update(t, completed=sent)

                    sftp.put(str(local), remote, callback=_callback)
        finally:
            sftp.close()

    def download(self, remote_path: str, local_path: Path) -> None:
        assert self._client
        sftp = self._client.open_sftp()
        try:
            stat = sftp.stat(remote_path)
            size = stat.st_size or 0
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                FileSizeColumn(),
                TransferSpeedColumn(),
                console=console,
            ) as progress:
                task = progress.add_task(f"↓ {Path(remote_path).name}", total=size)

                def _callback(sent, total, t=task):
                    progress.update(t, completed=sent)

                sftp.get(remote_path, str(local_path), callback=_callback)
        finally:
            sftp.close()


@contextmanager
def ssh_session(host: str, port: int, user: str, key_path: Path):
    session = SSHSession(host, port, user, key_path)
    session.connect()
    try:
        yield session
    finally:
        session.close()
