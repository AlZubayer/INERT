import hashlib
import json
import logging
import sqlite3
from pathlib import Path

import pytest

import inert.p0_recovery as recovery
from inert.audit import StopRequired
from inert.config import Paths, load_config
from inert.gpu_telemetry import GpuMemorySample
from inert.llm_client import Completion


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_recovery_paths_keep_replay_cache_outside_original_cache(tmp_path: Path) -> None:
    paths = Paths(tmp_path)
    isolated = recovery.RecoveryPaths(paths)
    assert isolated.cache != paths.cache("wm_a")
    assert isolated.cache.is_relative_to(paths.data / "p0" / "telemetry_recovery_20261114")
    assert isolated.measurement.parent == isolated.cache.parent


def test_replay_measurement_is_supplemental_and_original_is_immutable(tmp_path: Path) -> None:
    paths = Paths(tmp_path)
    isolated = recovery.RecoveryPaths(paths)
    original = paths.p0_measurements / "original.json"
    original.parent.mkdir(parents=True)
    original.write_text('{"live_observations":{"other-key":{"peak_vram_mib":700}}}')
    before = digest(original)
    sample = GpuMemorySample(
        mib=801,
        started_utc="2026-11-14T10:00:00+00:00",
        ended_utc="2026-11-14T10:00:00.1+00:00",
        start_monotonic_ns=200,
        end_monotonic_ns=300,
    )
    record = recovery.record_supplemental_measurement(
        isolated, "request-key", [sample], 100, 400, 1.5
    )
    assert digest(original) == before
    assert record["provenance"] == "independent_replay_not_original_measurement"
    assert record["request_key"] == "request-key"
    assert record["accepted_live_samples"] == 1
    assert record["peak_vram_mib"] == 801
    assert isolated.measurement.exists()
    assert not (paths.p0_measurements / "request-key.json").exists()


def test_replay_measurement_rejects_samples_outside_live_request(tmp_path: Path) -> None:
    isolated = recovery.RecoveryPaths(Paths(tmp_path))
    before = GpuMemorySample(
        mib=800,
        started_utc="2026-11-14T10:00:00+00:00",
        ended_utc="2026-11-14T10:00:00.1+00:00",
        start_monotonic_ns=20,
        end_monotonic_ns=30,
    )
    with pytest.raises(ValueError, match="live inference"):
        recovery.record_supplemental_measurement(isolated, "request-key", [before], 100, 400, 1.5)
    assert not isolated.measurement.exists()


def test_recovery_command_is_idempotent_after_claim(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = Paths(tmp_path)
    calls = 0

    def fake_execute(*_args: object) -> dict:
        nonlocal calls
        calls += 1
        return {"status": "REPLAY_EVIDENCE_COLLECTED", "request_key": "request-key"}

    monkeypatch.setattr(recovery, "inspect_original", lambda *_args: {"request_key": "request-key"})
    monkeypatch.setattr(recovery, "check_replay_preflight", lambda *_args: None)
    monkeypatch.setattr(recovery, "execute_one_replay", fake_execute)
    first = recovery.run_replay(paths, load_config(), logging.getLogger("replay-test"))
    second = recovery.run_replay(paths, load_config(), logging.getLogger("replay-test"))
    assert first == second
    assert calls == 1
    assert json.loads(recovery.RecoveryPaths(paths).guard.read_text())["request_key"] == (
        "request-key"
    )


def test_existing_guard_without_summary_never_starts_second_request(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = Paths(tmp_path)
    isolated = recovery.RecoveryPaths(paths)
    isolated.directory.mkdir(parents=True)
    isolated.guard.write_text('{"request_key":"request-key"}')
    monkeypatch.setattr(recovery, "inspect_original", lambda *_args: {"request_key": "request-key"})
    monkeypatch.setattr(recovery, "execute_one_replay", lambda *_args: pytest.fail("replayed"))
    with pytest.raises(RuntimeError, match="already claimed"):
        recovery.run_replay(paths, load_config(), logging.getLogger("replay-test"))


def test_independent_replay_audit_accepts_only_exact_cached_request(tmp_path: Path) -> None:
    isolated = recovery.RecoveryPaths(Paths(tmp_path))
    isolated.directory.mkdir(parents=True)
    request = '{"messages":[]}'
    key = hashlib.sha256(request.encode()).hexdigest()
    response = json.dumps(
        {
            "choices": [{"message": {"content": "RESULT: 1/2"}, "finish_reason": "stop"}],
            "usage": {"completion_tokens": 8},
        }
    )
    completion = Completion("RESULT: 1/2", 1.5, 8, False, "2026-11-14T10:00:00+00:00", "stop")
    with sqlite3.connect(isolated.cache) as database:
        database.execute(
            "CREATE TABLE calls (key TEXT PRIMARY KEY, request TEXT, "
            "response TEXT, completion TEXT)"
        )
        database.execute(
            "INSERT INTO calls VALUES (?, ?, ?, ?)",
            (key, request, response, json.dumps(completion.__dict__)),
        )
    (isolated.directory / "raw_api_response.json").write_text(response, encoding="utf-8")
    (isolated.directory / "completion.json").write_text(json.dumps(completion.__dict__))
    target = {
        "request_key": key,
        "serialized_request": request,
        "original_completion": completion,
    }
    result = {
        "status": "REPLAY_TELEMETRY_FAILED",
        "replay_raw_sha256": hashlib.sha256(completion.raw_output.encode()).hexdigest(),
        "replay_response_sha256": hashlib.sha256(response.encode()).hexdigest(),
    }
    assert recovery.audit_replay_cache(isolated, target, result)["cache_rows"] == 1
    with sqlite3.connect(isolated.cache) as database:
        database.execute(
            "INSERT INTO calls VALUES (?, ?, ?, ?)",
            ("other", request, response, json.dumps(completion.__dict__)),
        )
    with pytest.raises(StopRequired, match="one permitted call"):
        recovery.audit_replay_cache(isolated, target, result)
