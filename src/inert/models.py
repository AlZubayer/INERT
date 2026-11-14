import hashlib
import json
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from inert.config import Config, Paths
from inert.llm_client import CachedClient
from inert.server import ModelServer, ServerError


@dataclass(frozen=True)
class ResolvedModel:
    files: list[Path]
    sha256: str


def load_models(paths: Paths) -> Config:
    with (paths.configs / "models.yaml").open(encoding="utf-8") as stream:
        return yaml.safe_load(stream)


def resolve_model(paths: Paths, model: Config, quantization: str) -> ResolvedModel:
    files, hashes = [], []
    for entry in model["files"]:
        if quantization.lower() not in entry["filename"].lower():
            continue
        path = (paths.root / entry["path"]).resolve()
        if not path.is_relative_to(paths.shared_data.resolve()):
            raise ValueError("Model path must be inside data/.")
        if not path.is_file():
            raise FileNotFoundError(f"Model file not downloaded: {path}")
        with path.open("rb") as stream:
            actual = hashlib.file_digest(stream, "sha256").hexdigest()
        if actual != entry["sha256"]:
            raise ValueError(f"Model SHA-256 mismatch: {path}")
        files.append(path)
        hashes.append(actual)
    if not files:
        raise ValueError(f"No {quantization} model files configured.")
    order = sorted(zip(files, hashes, strict=True))
    files = [path for path, _ in order]
    hashes = [digest for _, digest in order]
    identity = (
        hashes[0] if len(hashes) == 1 else hashlib.sha256(json.dumps(hashes).encode()).hexdigest()
    )
    return ResolvedModel(files, identity)


@contextmanager
def model_session(
    paths: Paths,
    config: Config,
    role: str,
    quantization: str | None = None,
    gpu_layers: int | None = None,
) -> Iterator[CachedClient]:
    registry = load_models(paths)
    model = registry["models"][role]
    quantization = quantization or model.get("quantization", "Q4_K_M")
    resolved = resolve_model(paths, model, quantization)
    layers = gpu_layers if gpu_layers is not None else model["n_gpu_layers"]
    if layers is None:
        raise ValueError("WM-A offload setting is not recorded; run P0 first.")
    executable = Path(registry["serving"]["executable"])
    if not executable.is_absolute():
        executable = paths.root / executable
    flags: dict[str, Any] = {
        "context_size": config["server"]["context_size"],
        "gpu_layers": layers,
        "jinja": True,
        "reasoning_format": "none",
        "server_sha256": hashlib.sha256(executable.read_bytes()).hexdigest(),
    }
    arguments = [
        "--model",
        str(resolved.files[0]),
        "--host",
        config["server"]["host"],
        "--port",
        str(config["server"]["port"]),
        "--ctx-size",
        str(flags["context_size"]),
        "--n-gpu-layers",
        str(layers),
        "--jinja",
        "--reasoning-format",
        "none",
    ]
    server = ModelServer(paths, config["server"], [str(executable)], arguments)
    started = False

    def ensure_server() -> None:
        nonlocal started
        if not started:
            startup_started = time.perf_counter()
            try:
                server.__enter__()
            except ServerError as error:
                error.startup_seconds = time.perf_counter() - startup_started
                error.log_path = str(server.log.name) if server.log is not None else None
                raise
            client.server_startup_seconds = time.perf_counter() - startup_started
            client.server_log_path = str(server.log.name) if server.log is not None else None
            client.server_pid = server.process.pid if server.process is not None else None
            started = True

    url = f"http://{config['server']['host']}:{config['server']['port']}"
    with CachedClient(
        paths.cache(role),
        url,
        resolved.sha256,
        flags,
        timeout=config["server"]["request_seconds"],
        on_miss=ensure_server,
    ) as client:
        client.server_command = server.command
        try:
            yield client
        finally:
            if started:
                try:
                    server.__exit__()
                finally:
                    client.server_shutdown_ok = (
                        server.process is not None
                        and server.process.poll() is not None
                        and not paths.server_lock.exists()
                    )
