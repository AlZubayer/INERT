import os
import socket
import subprocess
import time
from collections.abc import Callable
from typing import IO, Self

import httpx

from inert.config import Config, Paths


class ServerError(RuntimeError):
    """Local server setup or lifecycle failure."""


class ModelServer:
    def __init__(
        self,
        paths: Paths,
        config: Config,
        executable: list[str],
        flags: list[str],
        health: Callable[[], bool] | None = None,
    ) -> None:
        self.paths = paths
        self.config = config
        self.command = executable + flags
        self.process: subprocess.Popen | None = None
        self.log: IO[bytes] | None = None
        self.owns_lock = False
        self.health = health or self._health

    def _health(self) -> bool:
        try:
            with httpx.Client(trust_env=False, timeout=1) as client:
                return (
                    client.get(
                        f"http://{self.config['host']}:{self.config['port']}/health"
                    ).status_code
                    == 200
                )
        except httpx.HTTPError:
            return False

    def __enter__(self) -> Self:
        if self.config["host"] != "127.0.0.1":
            raise ServerError("Only a 127.0.0.1 bind is permitted.")
        self.paths.shared_data.mkdir(parents=True, exist_ok=True)
        try:
            descriptor = os.open(self.paths.server_lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError as exc:
            raise ServerError(
                "A server lock already exists; verify its process before removal."
            ) from exc
        self.owns_lock = True
        os.close(descriptor)
        try:
            with socket.socket() as probe:
                try:
                    probe.bind((self.config["host"], self.config["port"]))
                except OSError as exc:
                    raise ServerError(
                        "The inference port is already in use; no second model was started."
                    ) from exc
            path = self.paths.log_file("server")
            path.parent.mkdir(parents=True, exist_ok=True)
            self.log = path.open("wb")
            self.process = subprocess.Popen(self.command, stdout=self.log, stderr=subprocess.STDOUT)
            self.paths.server_lock.write_text(str(self.process.pid), encoding="ascii")
            deadline = time.monotonic() + self.config["startup_seconds"]
            while time.monotonic() < deadline:
                if self.process.poll() is not None:
                    raise ServerError(f"llama-server exited during startup; see {path}.")
                if self.health():
                    return self
                time.sleep(0.05)
            raise ServerError(f"llama-server startup timed out; see {path}.")
        except BaseException:
            self.__exit__()
            raise

    def __exit__(self, *args: object) -> None:
        if self.process is not None and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=10)
        if self.log is not None:
            self.log.close()
        if self.owns_lock:
            self.paths.server_lock.unlink(missing_ok=True)
            self.owns_lock = False
