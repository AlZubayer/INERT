"""One owner-authorized, isolated WM-A P0 call-62 telemetry replay."""

import hashlib
import json
import logging
import os
import socket
import sqlite3
import threading
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from inert.audit import StopRequired
from inert.config import Config, Paths
from inert.gpu_telemetry import GpuMemorySample, sample_gpu_memory
from inert.llm_client import CachedClient, Completion, completion_request
from inert.models import load_models, resolve_model
from inert.p0_measurement import SOURCE
from inert.p0_selection import load_p0_manifest
from inert.parse import parse_result
from inert.schemas import Item, write_json
from inert.server import ModelServer

TARGET_ITEM_ID = "mbpp-633:mbpp-633-g10:D:NAT:kt_ab:vendored"
TARGET_REQUEST_KEY = "675281ba380346155c537838d325bf18de2e58f24b8b38dea854a5389e41478d"
EXPECTED_MANIFEST_SHA256 = "81431897467fe7a62821c44967c888bfd1b9bec9ae8520538470fe35051827e0"
EXPECTED_MODEL_SHA256 = "98de3cd55f5bd89a15708e084ccbb838ff00dec6c35e9daa15eb3f3fad596bdd"
EXPECTED_SERVER_SHA256 = "00d50686815af38249d0218c91558fbd0e9093ac8c074bac86196907f4305e31"
EXPECTED_RAW_SHA256 = "0efa5258550aa36b1b405032959e77bca7b6a6f9597be41d58a6388d00419db0"
EXPECTED_RESPONSE_SHA256 = "c54ee1caaeb81fc04b4f24d3c26e05ed30ba48c8cd1bb87c98ddaface2e9ad3b"


@dataclass(frozen=True)
class RecoveryPaths:
    paths: Paths

    @property
    def directory(self) -> Path:
        return self.paths.data / "p0" / "telemetry_recovery_20261114"

    @property
    def cache(self) -> Path:
        return self.directory / "replay.sqlite"

    @property
    def guard(self) -> Path:
        return self.directory / "one_replay_guard.json"

    @property
    def measurement(self) -> Path:
        return self.directory / "supplemental_measurement.json"

    @property
    def telemetry_attempts(self) -> Path:
        return self.directory / "telemetry_attempts.jsonl"

    @property
    def original_before(self) -> Path:
        return self.directory / "original_before.json"

    @property
    def original_after(self) -> Path:
        return self.directory / "original_after.json"

    @property
    def summary(self) -> Path:
        return self.directory / "audit_summary.json"


def _hash_file(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _digest(value: Any) -> str:
    serialized = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(serialized.encode()).hexdigest()


def _api_content(response: str) -> tuple[str, int | None, str | None]:
    body = json.loads(response)
    choice = body["choices"][0]
    message = choice["message"]
    content = message.get("content") or ""
    if message.get("reasoning_content"):
        content = "<think>" + message["reasoning_content"] + "</think>\n" + content
    return content, body.get("usage", {}).get("completion_tokens"), choice.get("finish_reason")


def inspect_original(paths: Paths, config: Config) -> dict[str, Any]:
    """Verify all original evidence without opening any file for writing."""
    if paths.profile != "pilot" or (paths.results / "p0.json").exists():
        raise StopRequired("Call-62 recovery requires an undecided pilot P0 trial.")
    manifest, task_map, items = load_p0_manifest(paths, config)
    if manifest["manifest_sha256"] != EXPECTED_MANIFEST_SHA256 or len(items) != 100:
        raise StopRequired("Frozen P0 selection changed before replay.")
    selected = [item for item in items if item.item_id == TARGET_ITEM_ID]
    if len(selected) != 1:
        raise StopRequired("Original call-62 assignment is not unique in the manifest.")
    item: Item = selected[0]
    registry = load_models(paths)
    model = resolve_model(paths, registry["models"]["wm_a"], "Q4_K_M")
    server_path = (paths.root / registry["serving"]["executable"]).resolve()
    server_hash = _hash_file(server_path)
    if model.sha256 != EXPECTED_MODEL_SHA256 or server_hash != EXPECTED_SERVER_SHA256:
        raise StopRequired("WM-A model or local server binary hash changed.")
    if config["server"]["host"] != "127.0.0.1" or config["server"]["context_size"] != 8192:
        raise StopRequired("Original local serving configuration changed.")
    parameters = dict(config["sampling"]["wm"])
    if parameters != {"temperature": 0.0, "top_p": 1.0, "max_tokens": 1024, "seed": 0}:
        raise StopRequired("Original WM-A inference settings changed.")
    flags = {
        "context_size": config["server"]["context_size"],
        "gpu_layers": 41,
        "jinja": True,
        "reasoning_format": "none",
        "server_sha256": server_hash,
    }
    expected_requests = {
        key: serialized
        for case in items
        for key, serialized, _ in [
            completion_request(model.sha256, flags, case.messages, parameters)
        ]
    }
    if len(expected_requests) != 100:
        raise StopRequired("Frozen P0 requests are not unique.")
    request_key, serialized, _ = completion_request(model.sha256, flags, item.messages, parameters)
    if request_key != TARGET_REQUEST_KEY:
        raise StopRequired("Call-62 replay request identity differs from original.")
    cache_path = paths.cache("wm_a")
    with sqlite3.connect(f"file:{cache_path.as_posix()}?mode=ro", uri=True) as database:
        database.execute("PRAGMA query_only=ON")
        if database.execute("PRAGMA integrity_check").fetchone() != ("ok",):
            raise StopRequired("Original WM-A cache failed SQLite integrity_check.")
        rows = database.execute(
            "SELECT key, request, response, completion FROM calls ORDER BY key"
        ).fetchall()
    if len(rows) != 62 or len({row[0] for row in rows}) != 62:
        raise StopRequired("Original WM-A cache no longer has 62 unique calls.")
    if any(expected_requests.get(key) != request for key, request, _, _ in rows):
        raise StopRequired("Original WM-A cache requests differ from the frozen manifest.")
    row = next((row for row in rows if row[0] == request_key), None)
    if row is None or row[1] != serialized:
        raise StopRequired("Original call-62 request is missing or changed.")
    original_completion = Completion(**json.loads(row[3]))
    api_raw, api_tokens, api_finish = _api_content(row[2])
    if (
        _digest_for_text(original_completion.raw_output) != EXPECTED_RAW_SHA256
        or _digest_for_text(row[2]) != EXPECTED_RESPONSE_SHA256
        or api_raw != original_completion.raw_output
        or api_tokens != original_completion.completion_tokens
        or api_finish != original_completion.finish_reason
        or original_completion.completion_tokens != 1024
        or original_completion.finish_reason != "length"
        or original_completion.cache_hit
        or parse_result(original_completion.raw_output, task_map[item.task_id].n_tests).parse_status
        != "fail"
    ):
        raise StopRequired("Original call-62 response or completion changed.")
    measurement_files = list(paths.p0_measurements.glob("*.json"))
    if len(measurement_files) != 1:
        raise StopRequired("Original P0 measurement record is missing or ambiguous.")
    measurement_path = measurement_files[0]
    measurement = json.loads(measurement_path.read_text(encoding="utf-8"))
    if (
        measurement.get("status") != "INCOMPLETE"
        or measurement.get("source") != SOURCE
        or measurement.get("identity_sha256") != measurement_path.stem
        or _digest(measurement["identity"]) != measurement_path.stem
        or _digest({k: v for k, v in measurement.items() if k != "record_sha256"})
        != measurement.get("record_sha256")
        or measurement["identity"]["server_flags"] != flags
        or measurement["identity"]["model_sha256"] != model.sha256
        or measurement["identity"]["item_manifest_sha256"] != manifest["manifest_sha256"]
        or measurement["identity"]["inference_settings"] != parameters
    ):
        raise StopRequired("Original P0 live measurement provenance changed.")
    observations = measurement["live_observations"]
    cache_rows = {saved[0]: Completion(**json.loads(saved[3])) for saved in rows}
    if len(observations) != 61 or set(cache_rows) - set(observations) != {request_key}:
        raise StopRequired("Call 62 is not the only missing original live observation.")
    if any(
        cache_rows[key].latency_s != observation["latency_s"]
        or cache_rows[key].completion_tokens != observation["completion_tokens"]
        for key, observation in observations.items()
    ):
        raise StopRequired("Original live measurements conflict with cached completions.")
    protected_files = [
        cache_path,
        cache_path.with_name(cache_path.name + "-wal"),
        cache_path.with_name(cache_path.name + "-shm"),
        measurement_path,
        paths.p0_manifest,
    ]
    snapshot = {
        "manifest_sha256": manifest["manifest_sha256"],
        "original_calls": len(rows),
        "original_live_observations": len(observations),
        "missing_original_key": request_key,
        "logical_cache_sha256": _digest(rows),
        "protected_file_sha256": {
            str(path.relative_to(paths.root)): _hash_file(path) if path.exists() else None
            for path in protected_files
        },
        "call62_raw_sha256": EXPECTED_RAW_SHA256,
        "call62_response_sha256": EXPECTED_RESPONSE_SHA256,
        "model_sha256": model.sha256,
        "server_sha256": server_hash,
    }
    return {
        "request_key": request_key,
        "serialized_request": serialized,
        "item": item,
        "n_tests": task_map[item.task_id].n_tests,
        "original_completion": original_completion,
        "original_response_sha256": EXPECTED_RESPONSE_SHA256,
        "model_path": model.files[0],
        "model_sha256": model.sha256,
        "server_path": server_path,
        "server_sha256": server_hash,
        "flags": flags,
        "parameters": parameters,
        "snapshot": snapshot,
    }


def _digest_for_text(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def record_supplemental_measurement(
    recovery: RecoveryPaths,
    request_key: str,
    samples: list[GpuMemorySample],
    request_start_ns: int,
    request_end_ns: int,
    latency_s: float,
) -> dict[str, Any]:
    """Persist replay VRAM only under the isolated recovery directory."""
    live = [
        sample
        for sample in samples
        if sample.start_monotonic_ns >= request_start_ns
        and sample.end_monotonic_ns <= request_end_ns
    ]
    if not live or request_end_ns <= request_start_ns or latency_s <= 0:
        raise ValueError("Replay lacks a valid GPU sample during live inference.")
    record = {
        "provenance": "independent_replay_not_original_measurement",
        "request_key": request_key,
        "request_start_monotonic_ns": request_start_ns,
        "request_end_monotonic_ns": request_end_ns,
        "http_latency_s": latency_s,
        "accepted_samples": [asdict(sample) for sample in samples],
        "accepted_live_samples": len(live),
        "peak_vram_mib": max(sample.mib for sample in live),
        "original_vram_observation_available": False,
        "created_utc": datetime.now(UTC).isoformat(),
    }
    record["record_sha256"] = _digest(record)
    write_json(recovery.measurement, record)
    return record


def check_replay_preflight(paths: Paths, config: Config, recovery: RecoveryPaths) -> None:
    """Check local isolation and a valid single-GPU telemetry path."""
    if paths.server_lock.exists():
        raise StopRequired("An active or stale server lock blocks the isolated replay.")
    with socket.socket() as probe:
        try:
            probe.bind((config["server"]["host"], config["server"]["port"]))
        except OSError as error:
            raise StopRequired("The local inference port is already occupied.") from error
    if recovery.cache.exists():
        with sqlite3.connect(f"file:{recovery.cache.as_posix()}?mode=ro", uri=True) as database:
            existing = database.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='calls'"
            ).fetchone()
            if existing and database.execute("SELECT COUNT(*) FROM calls").fetchone()[0]:
                raise StopRequired("The isolated replay cache already contains a completion.")
    baseline = sample_gpu_memory(recovery.telemetry_attempts)
    write_json(
        recovery.directory / "preflight.json",
        {
            "status": "PASS",
            "baseline_gpu_memory_mib": baseline.mib,
            "baseline_sample": asdict(baseline),
            "server_lock_absent": True,
            "port_available": True,
            "replay_cache_empty": True,
            "checked_utc": datetime.now(UTC).isoformat(),
        },
    )


def _claim_replay(recovery: RecoveryPaths, request_key: str) -> None:
    recovery.directory.mkdir(parents=True, exist_ok=True)
    value = {"request_key": request_key, "claimed_utc": datetime.now(UTC).isoformat()}
    try:
        descriptor = os.open(recovery.guard, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
    except FileExistsError as error:
        raise RuntimeError("The one-call replay is already claimed.") from error
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        stream.write(json.dumps(value, indent=2) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def _telemetry_counts(path: Path) -> dict[str, int]:
    attempts = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    return {
        "accepted_attempts": sum(row["accepted"] for row in attempts),
        "rejected_attempts": sum(not row["accepted"] for row in attempts),
        "successful_retries": sum(row["accepted"] and row["attempt"] > 1 for row in attempts),
    }


def execute_one_replay(
    paths: Paths, config: Config, recovery: RecoveryPaths, target: dict[str, Any]
) -> dict[str, Any]:
    """Issue at most one local completion, preserving all outputs separately."""
    item: Item = target["item"]
    key = target["request_key"]
    host = config["server"]["host"]
    port = config["server"]["port"]
    arguments = [
        "--model",
        str(target["model_path"]),
        "--host",
        host,
        "--port",
        str(port),
        "--ctx-size",
        str(target["flags"]["context_size"]),
        "--n-gpu-layers",
        str(target["flags"]["gpu_layers"]),
        "--jinja",
        "--reasoning-format",
        target["flags"]["reasoning_format"],
    ]
    write_json(
        recovery.directory / "replay_request_manifest.json",
        {
            "request_key": key,
            "serialized_request": target["serialized_request"],
            "item_id": item.item_id,
            "messages": [message.model_dump() for message in item.messages],
            "model_sha256": target["model_sha256"],
            "server_sha256": target["server_sha256"],
            "server_arguments": [str(target["server_path"]), *arguments],
            "parameters": target["parameters"],
            "provenance": "owner_authorized_independent_call62_replay",
        },
    )
    server = ModelServer(paths, config["server"], [str(target["server_path"])], arguments)
    server_audit: dict[str, Any] = {
        "command": server.command,
        "startup_result": "NOT_STARTED",
        "startup_seconds": None,
        "server_pid": None,
        "server_log_path": None,
        "server_stopped": None,
    }
    result: dict[str, Any] = {"status": "BLOCKED_INFRASTRUCTURE", "request_key": key}
    startup_start = time.perf_counter()
    try:
        with server:
            server_audit.update(
                {
                    "startup_result": "LOADED",
                    "startup_seconds": time.perf_counter() - startup_start,
                    "server_pid": server.process.pid if server.process else None,
                    "server_log_path": str(server.log.name) if server.log else None,
                }
            )
            stop_monitor = threading.Event()
            samples: list[GpuMemorySample] = []
            monitor_errors: list[str] = []

            def monitor() -> None:
                while not stop_monitor.is_set():
                    try:
                        samples.append(sample_gpu_memory(recovery.telemetry_attempts))
                    except Exception as error:
                        monitor_errors.append(str(error))
                        return
                    stop_monitor.wait(0.1)

            with CachedClient(
                recovery.cache,
                f"http://{host}:{port}",
                target["model_sha256"],
                target["flags"],
                timeout=config["server"]["request_seconds"],
            ) as client:
                watcher = threading.Thread(target=monitor, daemon=True)
                request_start_ns = time.monotonic_ns()
                watcher.start()
                completion: Completion | None = None
                request_error: str | None = None
                try:
                    completion = client.complete(item.messages, target["parameters"])
                except Exception as error:
                    request_error = repr(error)
                finally:
                    request_end_ns = time.monotonic_ns()
                    stop_monitor.set()
                    watcher.join(timeout=35)
                result["request_window_monotonic_ns"] = [request_start_ns, request_end_ns]
                result["accepted_poll_samples"] = len(samples)
                result["monitor_errors"] = monitor_errors
                result["monitor_stopped"] = not watcher.is_alive()
                if request_error is not None:
                    result["error"] = request_error
                elif completion is None or completion.cache_hit:
                    result["error"] = "No new live completion was produced."
                else:
                    row = client.db.execute(
                        "SELECT request, response, completion FROM calls WHERE key = ?", (key,)
                    ).fetchone()
                    if row is None or row[0] != target["serialized_request"]:
                        result["status"] = "BLOCKED_INTEGRITY"
                        result["error"] = "Isolated completion was not cached under exact request."
                    else:
                        (recovery.directory / "raw_api_response.json").write_text(
                            row[1], encoding="utf-8"
                        )
                        write_json(recovery.directory / "completion.json", asdict(completion))
                        parsed = parse_result(completion.raw_output, target["n_tests"])
                        raw_sha = _digest_for_text(completion.raw_output)
                        matching_output = (
                            completion.raw_output == target["original_completion"].raw_output
                        )
                        result.update(
                            {
                                "replay_live_request_count": 1,
                                "replay_raw_sha256": raw_sha,
                                "replay_response_sha256": _digest_for_text(row[1]),
                                "output_byte_identical": matching_output,
                                "original_raw_sha256": EXPECTED_RAW_SHA256,
                                "original_response_sha256": EXPECTED_RESPONSE_SHA256,
                                "original_http_latency_s": target["original_completion"].latency_s,
                                "replay_http_latency_s": completion.latency_s,
                                "replay_completion_tokens": completion.completion_tokens,
                                "replay_finish_reason": completion.finish_reason,
                                "replay_parse_status": parsed.parse_status,
                                "original_parse_status": "fail",
                                "replay_cache_hit": completion.cache_hit,
                            }
                        )
                        if watcher.is_alive() or monitor_errors:
                            result["status"] = "REPLAY_TELEMETRY_FAILED"
                        else:
                            try:
                                observed = record_supplemental_measurement(
                                    recovery,
                                    key,
                                    samples,
                                    request_start_ns,
                                    request_end_ns,
                                    completion.latency_s,
                                )
                            except ValueError as error:
                                result["status"] = "REPLAY_TELEMETRY_FAILED"
                                result["error"] = str(error)
                            else:
                                result["status"] = (
                                    "REPLAY_EVIDENCE_COLLECTED"
                                    if matching_output
                                    else "REPLAY_OUTPUT_DIFFERED"
                                )
                                result["replay_peak_vram_mib"] = observed["peak_vram_mib"]
                                result["accepted_live_samples"] = observed["accepted_live_samples"]
                        write_json(recovery.directory / "output_comparison.json", result)
    except Exception as error:
        result["status"] = "BLOCKED_INFRASTRUCTURE"
        result["error"] = repr(error)
        server_audit["startup_result"] = (
            "LOAD_FAILED" if server_audit["startup_result"] == "NOT_STARTED" else "LOADED"
        )
        server_audit["startup_seconds"] = server_audit["startup_seconds"] or (
            time.perf_counter() - startup_start
        )
        server_audit["server_pid"] = server.process.pid if server.process else None
        server_audit["server_log_path"] = str(server.log.name) if server.log else None
    finally:
        server_audit["server_stopped"] = (
            server.process is None or server.process.poll() is not None
        ) and not paths.server_lock.exists()
        server_audit["completed_utc"] = datetime.now(UTC).isoformat()
        write_json(recovery.directory / "server_audit.json", server_audit)
    if recovery.telemetry_attempts.exists():
        result.update(_telemetry_counts(recovery.telemetry_attempts))
    result["server_startup_seconds"] = server_audit["startup_seconds"]
    result["server_stopped"] = server_audit["server_stopped"]
    if recovery.cache.exists():
        with sqlite3.connect(f"file:{recovery.cache.as_posix()}?mode=ro", uri=True) as db:
            keys = [row[0] for row in db.execute("SELECT key FROM calls")]
        result["replay_cache_keys"] = keys
        if keys not in ([], [key]):
            result["status"] = "BLOCKED_INTEGRITY"
            result["error"] = "Isolated cache contains an unexpected request."
    return result


def audit_replay_cache(
    recovery: RecoveryPaths, target: dict[str, Any], result: dict[str, Any]
) -> dict[str, Any]:
    """Independently reconcile the isolated cache, API body and telemetry."""
    with sqlite3.connect(f"file:{recovery.cache.as_posix()}?mode=ro", uri=True) as database:
        database.execute("PRAGMA query_only=ON")
        if database.execute("PRAGMA integrity_check").fetchone() != ("ok",):
            raise StopRequired("Isolated replay cache failed SQLite integrity_check.")
        rows = database.execute("SELECT key, request, response, completion FROM calls").fetchall()
    if len(rows) != 1 or rows[0][0] != target["request_key"]:
        raise StopRequired("Isolated replay cache contains other than the one permitted call.")
    key, request, response, serialized_completion = rows[0]
    if request != target["serialized_request"] or _digest_for_text(request) != key:
        raise StopRequired("Replay request differs from the original identity.")
    saved = Completion(**json.loads(serialized_completion))
    api_raw, api_tokens, api_finish = _api_content(response)
    if (
        saved.cache_hit
        or api_raw != saved.raw_output
        or api_tokens != saved.completion_tokens
        or api_finish != saved.finish_reason
        or _digest_for_text(saved.raw_output) != result["replay_raw_sha256"]
        or _digest_for_text(response) != result["replay_response_sha256"]
        or json.loads((recovery.directory / "completion.json").read_text(encoding="utf-8"))
        != asdict(saved)
        or (recovery.directory / "raw_api_response.json").read_text(encoding="utf-8") != response
    ):
        raise StopRequired("Replay API response and completion evidence disagree.")
    record = None
    if result["status"] in ("REPLAY_EVIDENCE_COLLECTED", "REPLAY_OUTPUT_DIFFERED"):
        record = json.loads(recovery.measurement.read_text(encoding="utf-8"))
        if (
            record.get("provenance") != "independent_replay_not_original_measurement"
            or record.get("request_key") != key
            or record.get("record_sha256")
            != _digest({name: value for name, value in record.items() if name != "record_sha256"})
            or record.get("http_latency_s") != saved.latency_s
            or record.get("accepted_live_samples", 0) <= 0
        ):
            raise StopRequired("Supplemental replay telemetry is invalid or untraceable.")
        lower = record["request_start_monotonic_ns"]
        upper = record["request_end_monotonic_ns"]
        live = [
            sample
            for sample in record["accepted_samples"]
            if sample["start_monotonic_ns"] >= lower and sample["end_monotonic_ns"] <= upper
        ]
        if (
            len(live) != record["accepted_live_samples"]
            or max(sample["mib"] for sample in live) != record["peak_vram_mib"]
        ):
            raise StopRequired("Replay GPU samples do not overlap the live request as recorded.")
    audit = {
        "status": "PASS",
        "request_key": key,
        "cache_rows": len(rows),
        "raw_output_sha256": _digest_for_text(saved.raw_output),
        "api_response_sha256": _digest_for_text(response),
        "output_byte_identical": saved.raw_output == target["original_completion"].raw_output,
        "completion_tokens": saved.completion_tokens,
        "finish_reason": saved.finish_reason,
        "http_latency_s": saved.latency_s,
        "supplemental_live_vram_samples": (
            record["accepted_live_samples"] if record is not None else 0
        ),
    }
    write_json(recovery.directory / "independent_audit.json", audit)
    return audit


def run_replay(paths: Paths, config: Config, logger: logging.Logger) -> dict[str, Any]:
    """Audit originals, claim a one-time slot, and run no more than one replay."""
    recovery = RecoveryPaths(paths)
    target = inspect_original(paths, config)
    snapshot = target.get("snapshot", {})
    if recovery.original_before.exists():
        saved = json.loads(recovery.original_before.read_text(encoding="utf-8"))
        if saved != snapshot:
            raise StopRequired("Original P0 evidence changed since recovery preflight.")
    else:
        write_json(recovery.original_before, snapshot)
    if recovery.guard.exists():
        guard = json.loads(recovery.guard.read_text(encoding="utf-8"))
        if guard.get("request_key") != target["request_key"]:
            raise StopRequired("Existing one-replay guard has a different request key.")
        if recovery.summary.exists():
            return json.loads(recovery.summary.read_text(encoding="utf-8"))
        raise RuntimeError("The one-call replay is already claimed without a final audit.")
    check_replay_preflight(paths, config, recovery)
    _claim_replay(recovery, target["request_key"])
    result = execute_one_replay(paths, config, recovery, target)
    if result.get("replay_live_request_count") == 1:
        try:
            result["independent_audit"] = audit_replay_cache(recovery, target, result)
        except Exception as error:
            logger.exception("Isolated replay cache failed independent audit")
            result["status"] = "BLOCKED_INTEGRITY"
            result["replay_integrity_error"] = repr(error)
    try:
        after = inspect_original(paths, config).get("snapshot", {})
    except Exception as error:
        logger.exception("Original P0 evidence failed post-replay integrity audit")
        result["status"] = "BLOCKED_INTEGRITY"
        result["original_integrity_error"] = repr(error)
    else:
        write_json(recovery.original_after, after)
        result["original_evidence_unchanged"] = after == snapshot
        if after != snapshot:
            result["status"] = "BLOCKED_INTEGRITY"
    result["completed_utc"] = datetime.now(UTC).isoformat()
    write_json(recovery.summary, result)
    return result
