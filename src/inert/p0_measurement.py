"""Durable live-request provenance for P0 GPU memory and latency."""

import hashlib
import json
import math
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from inert.audit import StopRequired
from inert.config import Config, Paths
from inert.llm_client import CachedClient
from inert.schemas import Score, write_json

SOURCE = (
    "nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits during live WM-A requests"
)


def query_vram_mib() -> int:
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as error:
        raise StopRequired("P0 cannot measure GPU memory with nvidia-smi.") from error
    values = result.stdout.strip().splitlines()
    if result.returncode or len(values) != 1 or not values[0].strip().isdigit():
        raise StopRequired("P0 received no valid single-GPU memory reading from nvidia-smi.")
    return int(values[0].strip())


def trial_identity(
    paths: Paths,
    registry: Config,
    client: CachedClient,
    quantization: str,
    gpu_layers: int,
    parameters: Config,
    manifest_sha256: str,
) -> dict[str, Any]:
    model = registry["models"]["wm_a"]
    files = [entry for entry in model["files"] if quantization.lower() in entry["filename"].lower()]
    if len(files) != 1 or client.model_hash != files[0]["sha256"]:
        raise StopRequired("P0 model hash does not match the pinned quantization.")
    flags = dict(client.flags)
    if flags.get("gpu_layers") != gpu_layers:
        raise StopRequired("P0 GPU offload does not match the serving session.")
    executable = (paths.root / registry["serving"]["executable"]).resolve()
    arguments = [
        "--model",
        str((paths.root / files[0]["path"]).resolve()),
        "--host",
        client.base_url.split("//", 1)[1].split(":", 1)[0],
        "--port",
        client.base_url.rsplit(":", 1)[1],
        "--ctx-size",
        str(flags["context_size"]),
        "--n-gpu-layers",
        str(gpu_layers),
        "--jinja",
        "--reasoning-format",
        str(flags["reasoning_format"]),
    ]
    return {
        "model_sha256": client.model_hash,
        "quantization": quantization,
        "gpu_layers": gpu_layers,
        "context_length": flags["context_size"],
        "server": {
            "executable": str(executable),
            "binary_sha256": flags["server_sha256"],
            "build": registry["serving"]["build"],
            "commit": registry["serving"]["commit"],
            "arguments": arguments,
        },
        "server_flags": flags,
        "inference_settings": {
            key: parameters[key] for key in ("temperature", "top_p", "max_tokens", "seed")
        },
        "item_manifest_sha256": manifest_sha256,
    }


def _digest(value: Any) -> str:
    data = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(data.encode()).hexdigest()


def measurement_path(paths: Paths, identity: dict[str, Any]) -> Path:
    return paths.p0_measurements / f"{_digest(identity)}.json"


def _record_hash(record: dict[str, Any]) -> str:
    return _digest({key: value for key, value in record.items() if key != "record_sha256"})


def _read_record(paths: Paths, identity: dict[str, Any]) -> dict[str, Any] | None:
    path = measurement_path(paths, identity)
    if not path.exists():
        return None
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError) as error:
        raise StopRequired("P0 VRAM measurement record is unreadable.") from error
    if (
        record.get("identity") != identity
        or record.get("identity_sha256") != _digest(identity)
        or record.get("record_sha256") != _record_hash(record)
        or record.get("source") != SOURCE
        or record.get("status") not in ("INCOMPLETE", "COMPLETE")
        or not isinstance(record.get("live_observations"), dict)
    ):
        raise StopRequired("P0 measurement provenance is missing, stale, or incompatible.")
    for observation in record["live_observations"].values():
        if (
            type(observation.get("peak_vram_mib")) is not int
            or observation["peak_vram_mib"] <= 0
            or type(observation.get("sample_count")) is not int
            or observation["sample_count"] <= 0
            or not isinstance(observation.get("latency_s"), (int, float))
            or not math.isfinite(observation["latency_s"])
            or observation["latency_s"] <= 0
            or type(observation.get("completion_tokens")) is not int
            or observation["completion_tokens"] < 0
        ):
            raise StopRequired("P0 live measurement contains invalid observation fields.")
    return record


def _save_record(paths: Paths, identity: dict[str, Any], record: dict[str, Any]) -> None:
    record["record_sha256"] = _record_hash(record)
    write_json(measurement_path(paths, identity), record)


def record_live_request(
    paths: Paths,
    identity: dict[str, Any],
    request_key: str,
    peak_vram_mib: int,
    sample_count: int,
    latency_s: float,
    completion_tokens: int | None,
    startup_seconds: float | None,
) -> dict[str, Any]:
    if (
        peak_vram_mib <= 0
        or sample_count <= 0
        or not math.isfinite(latency_s)
        or latency_s <= 0
        or completion_tokens is None
        or completion_tokens < 0
    ):
        raise StopRequired("P0 live request lacks trustworthy VRAM or timing evidence.")
    record = _read_record(paths, identity) or {
        "status": "INCOMPLETE",
        "identity": identity,
        "identity_sha256": _digest(identity),
        "source": SOURCE,
        "live_observations": {},
        "startup_seconds": None,
    }
    observation = {
        "peak_vram_mib": peak_vram_mib,
        "sample_count": sample_count,
        "latency_s": latency_s,
        "completion_tokens": completion_tokens,
        "observed_at_utc": datetime.now(UTC).isoformat(),
    }
    prior = record["live_observations"].get(request_key)
    if prior is not None and (
        prior["latency_s"] != latency_s or prior["completion_tokens"] != completion_tokens
    ):
        raise StopRequired("P0 live request conflicts with persisted timing evidence.")
    if prior is None or peak_vram_mib > prior["peak_vram_mib"]:
        record["live_observations"][request_key] = observation
    if startup_seconds is not None:
        if not math.isfinite(startup_seconds) or startup_seconds < 0:
            raise StopRequired("P0 server startup timing is invalid.")
        if record["startup_seconds"] is None:
            record["startup_seconds"] = startup_seconds
        else:
            record.setdefault("additional_startup_seconds", []).append(startup_seconds)
    record["live_requests_completed"] = len(record["live_observations"])
    record["peak_vram_mib"] = max(
        item["peak_vram_mib"] for item in record["live_observations"].values()
    )
    _save_record(paths, identity, record)
    return record


def finalize_measurement(
    paths: Paths,
    identity: dict[str, Any],
    request_keys: list[str],
    scores: list[Score],
    total_elapsed_seconds: float,
) -> dict[str, Any]:
    record = _read_record(paths, identity)
    if record is None or not record["live_observations"]:
        raise StopRequired("P0 cache-only trial lacks matching live VRAM evidence.")
    if len(request_keys) != len(scores) or not math.isfinite(total_elapsed_seconds):
        raise StopRequired("P0 trial completion accounting is invalid.")
    if total_elapsed_seconds < 0 or record.get("startup_seconds") is None:
        raise StopRequired("P0 live server startup timing is unavailable.")
    missing = [key for key in request_keys if key not in record["live_observations"]]
    if missing:
        raise StopRequired("P0 cached requests lack matching live measurement provenance.")
    for key, score in zip(request_keys, scores, strict=True):
        observed = record["live_observations"][key]
        if (
            score.latency_s != observed["latency_s"]
            or score.completion_tokens != observed["completion_tokens"]
        ):
            raise StopRequired("P0 cached timing conflicts with live request provenance.")
    expected_hash = _digest(request_keys)
    if record["status"] == "COMPLETE" and record.get("request_keys_sha256") != expected_hash:
        raise StopRequired("P0 completed trial request set changed.")
    record["status"] = "COMPLETE"
    record["request_keys_sha256"] = expected_hash
    record["completed_assignments"] = len(scores)
    record["last_run_live_requests"] = sum(not score.cache_hit for score in scores)
    record["last_run_cache_hits"] = sum(score.cache_hit for score in scores)
    record["last_run_elapsed_seconds"] = total_elapsed_seconds
    _save_record(paths, identity, record)
    return record


def load_live_measurement(paths: Paths, identity: dict[str, Any]) -> dict[str, Any]:
    record = _read_record(paths, identity)
    if (
        record is None
        or record["status"] != "COMPLETE"
        or not record["live_observations"]
        or record.get("completed_assignments", 0) <= 0
    ):
        raise StopRequired("P0 cache-only trial lacks matching completed live evidence.")
    return record
