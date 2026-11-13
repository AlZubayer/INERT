import hashlib
import io
import json
import os
import sqlite3
import subprocess
import tarfile
import tempfile
import time
from dataclasses import dataclass

from inert.config import Config, Paths


class SandboxError(RuntimeError):
    """Sandbox setup, timeout or output-limit failure; never a fabricated test result."""


class SandboxSetupError(SandboxError):
    """Infrastructure failure before candidate execution; stop the stage."""


@dataclass(frozen=True)
class SandboxResult:
    stdout: str
    stderr: str
    returncode: int


class DockerSandbox:
    def __init__(self, paths: Paths, config: Config) -> None:
        self.paths = paths
        self.config = config
        self.image_id: str | None = None

    def run(self, source: str, harness: str, *, use_cache: bool = True) -> SandboxResult:
        cfg = self.config
        if self.image_id is None:
            try:
                image = subprocess.run(
                    ["docker", "image", "inspect", cfg["image"], "--format", "{{.Id}}"],
                    capture_output=True,
                    text=True,
                    timeout=20,
                )
            except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
                raise SandboxSetupError(
                    "Docker is unavailable; no host fallback was used."
                ) from exc
            if image.returncode:
                raise SandboxSetupError(
                    "Docker image is unavailable; pull the prescribed image before running."
                )
            self.image_id = image.stdout.strip()
        if use_cache:
            identity = json.dumps(
                {
                    "source": source,
                    "harness": harness,
                    "config": cfg,
                    "image_id": self.image_id,
                    "protocol": "tmpfs-nonroot-v1",
                },
                sort_keys=True,
            )
            key = hashlib.sha256(identity.encode()).hexdigest()
            cache_path = self.paths.cache("sandbox")
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            with sqlite3.connect(cache_path) as database:
                database.execute(
                    "CREATE TABLE IF NOT EXISTS executions "
                    "(key TEXT PRIMARY KEY, request TEXT NOT NULL, result TEXT NOT NULL)"
                )
                cached = database.execute(
                    "SELECT result FROM executions WHERE key = ?", (key,)
                ).fetchone()
            if cached:
                return SandboxResult(**json.loads(cached[0]))
        name = f"inert-{os.getpid()}-{time.monotonic_ns()}"
        archive = io.BytesIO()
        with tarfile.open(fileobj=archive, mode="w") as stream:
            for filename, content in [("solution.py", source), ("run_tests.py", harness)]:
                encoded = content.encode("utf-8")
                info = tarfile.TarInfo(filename)
                info.size = len(encoded)
                info.mode = 0o644
                stream.addfile(info, io.BytesIO(encoded))
        command = [
            "docker",
            "create",
            "--name",
            name,
            "--interactive",
            "--network",
            "none",
            "--memory",
            cfg["memory"],
            "--cpus",
            str(cfg["cpus"]),
            "--pids-limit",
            str(cfg["pids_limit"]),
            "--read-only",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "--user",
            "65534:65534",
            "--tmpfs",
            f"/work:rw,nosuid,nodev,noexec,size={cfg['tmpfs_size']},mode=1777",
            "--workdir",
            "/work",
            cfg["image"],
            "/bin/sh",
            "-c",
            "tar -xf - -C /work && python -B run_tests.py",
        ]
        try:
            try:
                created = subprocess.run(command, capture_output=True, timeout=cfg["setup_seconds"])
            except subprocess.TimeoutExpired as exc:
                raise SandboxSetupError(
                    "Docker container creation timed out; execution did not start."
                ) from exc
            if created.returncode:
                raise SandboxSetupError(
                    "Docker is unavailable or container creation failed: "
                    + created.stderr.decode(errors="replace")
                )
            with tempfile.TemporaryFile() as output, tempfile.TemporaryFile() as errors:
                try:
                    done = subprocess.run(
                        ["docker", "start", "--attach", "--interactive", name],
                        input=archive.getvalue(),
                        stdout=output,
                        stderr=errors,
                        timeout=cfg["wall_seconds"],
                    )
                except subprocess.TimeoutExpired as exc:
                    raise SandboxError(
                        "Sandbox timed out; candidate was not assigned a reward."
                    ) from exc
                limit = cfg["max_output_bytes"]
                if output.tell() > limit or errors.tell() > limit:
                    raise SandboxError("Sandbox output limit exceeded.")
                output.seek(0)
                errors.seek(0)
                result = SandboxResult(
                    output.read().decode("utf-8", errors="replace"),
                    errors.read().decode("utf-8", errors="replace"),
                    done.returncode,
                )
                if use_cache:
                    from dataclasses import asdict

                    with sqlite3.connect(cache_path) as database:
                        database.execute(
                            "INSERT OR REPLACE INTO executions VALUES (?, ?, ?)",
                            (key, identity, json.dumps(asdict(result))),
                        )
                return result
        except FileNotFoundError as exc:
            raise SandboxSetupError(
                "Docker is unavailable. No host fallback is permitted without approval."
            ) from exc
        finally:
            try:
                subprocess.run(["docker", "rm", "--force", name], capture_output=True, timeout=10)
            except (FileNotFoundError, subprocess.TimeoutExpired):
                pass
