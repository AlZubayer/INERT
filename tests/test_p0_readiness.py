import json
import logging
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest

import inert.p0 as p0
from inert.audit import StopRequired
from inert.config import Paths, load_config
from inert.p0 import (
    oom_from_load_error,
    p0_quantizations,
    truncated_before_result,
)
from inert.parse import parse_result
from inert.schemas import Item, Message, Task
from inert.server import ServerError


def test_p0_skips_unavailable_q3_but_uses_it_when_present(tmp_path: Path) -> None:
    paths = Paths(tmp_path)
    q3 = paths.root / "data/models/wm_a/test.Q3_K_M.gguf"
    registry = {
        "models": {
            "wm_a": {"files": [{"filename": q3.name, "path": str(q3.relative_to(paths.root))}]}
        }
    }
    assert p0_quantizations(paths, registry) == ["Q4_K_M"]
    q3.parent.mkdir(parents=True)
    q3.write_bytes(b"fixture")
    assert p0_quantizations(paths, registry) == ["Q4_K_M", "Q3_K_M"]


def test_p0_escalates_only_if_truncated_before_result() -> None:
    assert truncated_before_result("length", parse_result("no result", 3))
    assert not truncated_before_result("length", parse_result("RESULT: 2/4", 3))
    assert not truncated_before_result("stop", parse_result("no result", 3))


def test_p0_oom_detection_uses_only_current_server_log(tmp_path: Path) -> None:
    stale = tmp_path / "server-stale.log"
    stale.write_text("CUDA out of memory", encoding="utf-8")
    assert not oom_from_load_error(ServerError("The inference port is already in use."))
    current = tmp_path / "server-current.log"
    current.write_text("Port binding failed", encoding="utf-8")
    assert not oom_from_load_error(ServerError(f"llama-server exited; see {current}."))
    current.write_text("CUDA out of memory", encoding="utf-8")
    assert oom_from_load_error(ServerError(f"llama-server exited; see {current}."))


def test_p0_missing_q4_stops_without_writing_a_decision(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = Paths(tmp_path)
    config = load_config()
    tasks = [Task.model_construct(task_id=f"t{i}") for i in range(12)]
    items = [Item.model_construct(task_id="t0") for _ in range(100)]
    registry = {"models": {"wm_a": {"files": [], "layer_count": 40}}}
    monkeypatch.setattr(p0, "load_models", lambda _: registry)
    monkeypatch.setattr(
        p0,
        "load_p0_manifest",
        lambda _paths, _config: (
            {"manifest_sha256": "fixture"},
            {t.task_id: t for t in tasks},
            items,
        ),
    )

    def missing_file(*_: object) -> None:
        raise FileNotFoundError("Q4 file is missing")

    monkeypatch.setattr(p0, "model_session", missing_file)
    with pytest.raises(StopRequired, match="Q4_K_M model file is unavailable"):
        p0.run_p0(paths, config, logging.getLogger("test-p0"))
    assert not (paths.results / "p0.json").exists()


def test_p0_records_each_failed_q4_load_without_claiming_q3_failed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = Paths(tmp_path)
    config = load_config()
    task = Task.model_construct(task_id="t0", n_tests=3)
    items = [
        Item.model_construct(
            item_id=f"i{i}", task_id="t0", messages=[Message(role="user", content=f"i{i}")]
        )
        for i in range(100)
    ]
    registry = {"models": {"wm_a": {"files": [], "layer_count": 0}}}
    monkeypatch.setattr(p0, "load_models", lambda _paths: registry)
    monkeypatch.setattr(
        p0,
        "load_p0_manifest",
        lambda _paths, _config: ({"manifest_sha256": "fixture"}, {"t0": task}, items),
    )
    monkeypatch.setattr(
        p0,
        "trial_identity",
        lambda *_args: {"server": {"arguments": ["--ctx-size", "8192"]}},
    )
    monkeypatch.setattr(p0, "query_vram_mib", lambda *_args: 600)
    log = tmp_path / "current-server.log"
    log.write_text("CUDA out of memory", encoding="utf-8")

    class FakeClient:
        model_hash = "fixture-model"
        flags = {"gpu_layers": 1}
        server_startup_seconds = None
        server_log_path = str(log)
        server_pid = 123
        server_shutdown_ok = True

        def complete(self, _messages: object, _parameters: object) -> None:
            error = ServerError(f"llama-server exited during startup; see {log}.")
            error.startup_seconds = 1.25
            error.log_path = str(log)
            raise error

    @contextmanager
    def fake_session(*_: object) -> Iterator[FakeClient]:
        yield FakeClient()

    monkeypatch.setattr(p0, "model_session", fake_session)
    with pytest.raises(StopRequired, match="Q4 could not load"):
        p0.run_p0(paths, config, logging.getLogger("test-p0-load-audit"))
    rows = json.loads(paths.p0_load_attempts.read_text(encoding="utf-8"))
    assert [row["gpu_layers"] for row in rows] == [1, 0]
    assert all(row["startup_result"] == "OOM" for row in rows)
    assert all(row["startup_seconds"] == 1.25 for row in rows)
    assert all(row["server_log_path"] == str(log) for row in rows)
    assert all(row["server_stopped"] is True for row in rows)
    assert all(row["gpu_memory_peak_mib"] == 600 for row in rows)
    assert all(row["server_arguments"] == ["--ctx-size", "8192"] for row in rows)
    assert not (paths.results / "p0.json").exists()
