"""Serialized, auditable GPU-memory polling for local WM-A inference."""

import json
import os
import subprocess
import threading
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from inert.audit import StopRequired

GPU_MEMORY_COMMAND = (
    "nvidia-smi",
    "--query-gpu=memory.used",
    "--format=csv,noheader,nounits",
)
MAX_ATTEMPTS = 3
RETRY_DELAY_SECONDS = 0.1
_POLL_LOCK = threading.Lock()


@dataclass(frozen=True)
class GpuMemorySample:
    mib: int
    started_utc: str
    ended_utc: str
    start_monotonic_ns: int
    end_monotonic_ns: int


def _decode(value: str | bytes | None) -> str:
    if value is None:
        return ""
    return value.decode("utf-8", errors="replace") if isinstance(value, bytes) else value


def _parse_memory(stdout: str, return_code: int | None) -> tuple[int | None, str]:
    if return_code != 0:
        return None, "RETURN_CODE"
    lines = stdout.strip().splitlines()
    if not lines:
        return None, "EMPTY"
    if len(lines) != 1:
        return None, "MULTI_GPU"
    value = lines[0].strip()
    if not value.isdigit():
        return None, "NON_NUMERIC"
    mib = int(value)
    if mib <= 0:
        return None, "NONPOSITIVE"
    return mib, "VALID"


def _append_attempt(audit_path: Path, record: dict) -> None:
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    with audit_path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(record, ensure_ascii=False, allow_nan=False) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def sample_gpu_memory(audit_path: Path | None) -> GpuMemorySample:
    """Return one valid single-GPU sample after at most three audited tries."""
    saw_missing_executable = False
    with _POLL_LOCK:
        query_id = time.monotonic_ns()
        for attempt in range(1, MAX_ATTEMPTS + 1):
            start_ns = time.monotonic_ns()
            started_utc = datetime.now(UTC).isoformat()
            stdout = ""
            stderr = ""
            return_code: int | None = None
            forced_reason: str | None = None
            try:
                result = subprocess.run(
                    list(GPU_MEMORY_COMMAND),
                    capture_output=True,
                    text=True,
                    errors="replace",
                    timeout=10,
                )
                stdout = result.stdout
                stderr = result.stderr
                return_code = result.returncode
            except subprocess.TimeoutExpired as error:
                stdout = _decode(error.stdout)
                stderr = _decode(error.stderr)
                forced_reason = "TIMEOUT"
            except FileNotFoundError as error:
                stderr = str(error)
                forced_reason = "MISSING_EXECUTABLE"
                saw_missing_executable = True
            except OSError as error:
                stderr = str(error)
                forced_reason = "OS_ERROR"
            end_ns = time.monotonic_ns()
            ended_utc = datetime.now(UTC).isoformat()
            mib, reason = (
                (None, forced_reason)
                if forced_reason is not None
                else _parse_memory(stdout, return_code)
            )
            row = {
                "query_id": query_id,
                "attempt": attempt,
                "started_utc": started_utc,
                "ended_utc": ended_utc,
                "start_monotonic_ns": start_ns,
                "end_monotonic_ns": end_ns,
                "command": list(GPU_MEMORY_COMMAND),
                "return_code": return_code,
                "raw_stdout": stdout,
                "raw_stderr": stderr,
                "duration_seconds": (end_ns - start_ns) / 1e9,
                "parse_result": reason,
                "parsed_mib": mib,
                "accepted": mib is not None,
            }
            if audit_path is not None:
                _append_attempt(audit_path, row)
            if mib is not None:
                return GpuMemorySample(mib, started_utc, ended_utc, start_ns, end_ns)
            if attempt < MAX_ATTEMPTS:
                time.sleep(RETRY_DELAY_SECONDS)
    if saw_missing_executable:
        raise StopRequired("P0 cannot measure GPU memory with nvidia-smi.")
    raise StopRequired("P0 received no valid single-GPU memory reading from nvidia-smi.")
