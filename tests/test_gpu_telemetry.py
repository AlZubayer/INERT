import json
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

import inert.gpu_telemetry as telemetry
from inert.audit import StopRequired


def recorded(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def result(stdout: str, returncode: int = 0, stderr: str = "") -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess([], returncode, stdout, stderr)


def test_valid_gpu_sample_has_complete_audit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    audit = tmp_path / "samples.jsonl"
    monkeypatch.setattr(telemetry.subprocess, "run", lambda *_a, **_k: result("523\n"))
    sample = telemetry.sample_gpu_memory(audit)
    assert sample.mib == 523
    assert sample.end_monotonic_ns >= sample.start_monotonic_ns
    row = recorded(audit)[0]
    assert row["command"] == list(telemetry.GPU_MEMORY_COMMAND)
    assert row["return_code"] == 0
    assert row["raw_stdout"] == "523\n"
    assert row["raw_stderr"] == ""
    assert row["parse_result"] == "VALID"
    assert row["parsed_mib"] == 523
    assert row["accepted"] is True
    assert row["duration_seconds"] >= 0
    assert row["started_utc"] and row["ended_utc"]


@pytest.mark.parametrize(
    ("first", "reason"),
    [
        (result("bad\n"), "NON_NUMERIC"),
        (result("700\n", 1, "busy"), "RETURN_CODE"),
        (subprocess.TimeoutExpired([], 10, output=b"", stderr=b"slow"), "TIMEOUT"),
    ],
)
def test_rejected_attempt_then_valid_retry_is_audited(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, first: object, reason: str
) -> None:
    audit = tmp_path / "samples.jsonl"
    events = iter([first, result("701\n")])

    def fake_run(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess:
        value = next(events)
        if isinstance(value, Exception):
            raise value
        return value

    monkeypatch.setattr(telemetry.subprocess, "run", fake_run)
    monkeypatch.setattr(telemetry.time, "sleep", lambda _seconds: None)
    assert telemetry.sample_gpu_memory(audit).mib == 701
    rows = recorded(audit)
    assert len(rows) == 2
    assert [row["attempt"] for row in rows] == [1, 2]
    assert rows[0]["parse_result"] == reason
    assert rows[0]["accepted"] is False
    assert rows[1]["accepted"] is True
    if reason == "TIMEOUT":
        assert rows[0]["raw_stderr"] == "slow"


@pytest.mark.parametrize(
    ("stdout", "reason"),
    [
        ("100\n200\n", "MULTI_GPU"),
        ("", "EMPTY"),
        ("unavailable\n", "NON_NUMERIC"),
        ("0\n", "NONPOSITIVE"),
    ],
)
def test_all_retries_fail_without_fabricated_vram(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, stdout: str, reason: str
) -> None:
    audit = tmp_path / "samples.jsonl"
    monkeypatch.setattr(telemetry.subprocess, "run", lambda *_a, **_k: result(stdout))
    monkeypatch.setattr(telemetry.time, "sleep", lambda _seconds: None)
    with pytest.raises(StopRequired, match="no valid single-GPU"):
        telemetry.sample_gpu_memory(audit)
    rows = recorded(audit)
    assert len(rows) == 3
    assert all(row["parse_result"] == reason for row in rows)
    assert all(row["parsed_mib"] is None and row["accepted"] is False for row in rows)


def test_concurrent_polling_serializes_nvidia_smi(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    audit = tmp_path / "samples.jsonl"
    gate = threading.Lock()
    active = 0
    peak_active = 0

    def fake_run(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess:
        nonlocal active, peak_active
        with gate:
            active += 1
            peak_active = max(peak_active, active)
        time.sleep(0.02)
        with gate:
            active -= 1
        return result("811\n")

    monkeypatch.setattr(telemetry.subprocess, "run", fake_run)
    with ThreadPoolExecutor(max_workers=2) as pool:
        values = list(pool.map(lambda _i: telemetry.sample_gpu_memory(audit).mib, range(2)))
    assert values == [811, 811]
    assert peak_active == 1
    assert len(recorded(audit)) == 2
