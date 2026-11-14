import json
import logging
import subprocess
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

import pytest

import inert.gpu_telemetry as telemetry
import inert.p0 as p0
import inert.p0_measurement as measurement
from inert.audit import StopRequired
from inert.config import Paths, load_config
from inert.llm_client import Completion
from inert.schemas import Item, Message, Score, Task


def identity() -> dict:
    return {
        "model_sha256": "model-hash",
        "quantization": "Q4_K_M",
        "gpu_layers": 12,
        "context_length": 8192,
        "server": {"binary_sha256": "server-hash", "arguments": ["--ctx-size", "8192"]},
        "inference_settings": {"temperature": 0.0, "top_p": 1.0, "max_tokens": 1024, "seed": 0},
        "item_manifest_sha256": "manifest-hash",
    }


def score(cache_hit: bool = False) -> Score:
    return Score(
        item_id="i0",
        wm_id="wm_a",
        raw_output="RESULT: 3/3",
        parse_status="ok",
        k_pred=3,
        n_pred=3,
        R_sim=1.0,
        pred_pass=True,
        latency_s=1.0,
        completion_tokens=8,
        cache_hit=cache_hit,
        timestamp=datetime.now(UTC).isoformat(),
    )


def test_live_vram_record_survives_matching_cache_only_restart(tmp_path: Path) -> None:
    paths = Paths(tmp_path)
    expected = identity()
    partial = measurement.record_live_request(paths, expected, "key-0", 600, 3, 1.0, 8, 0.5)
    assert partial["status"] == "INCOMPLETE"
    saved = measurement.finalize_measurement(paths, expected, ["key-0"], [score()], 1.5)
    assert saved["status"] == "COMPLETE"
    assert saved["peak_vram_mib"] == 600
    assert saved["live_requests_completed"] == 1
    assert saved["startup_seconds"] == 0.5
    assert measurement.load_live_measurement(paths, expected) == saved
    replay = measurement.finalize_measurement(paths, expected, ["key-0"], [score(True)], 0.01)
    assert replay["last_run_cache_hits"] == 1
    assert replay["peak_vram_mib"] == 600


@pytest.mark.parametrize("change", ["model", "server", "manifest"])
def test_cache_only_vram_rejects_wrong_trial_identity(tmp_path: Path, change: str) -> None:
    paths = Paths(tmp_path)
    expected = identity()
    measurement.record_live_request(paths, expected, "key-0", 600, 1, 1.0, 8, 0.5)
    measurement.finalize_measurement(paths, expected, ["key-0"], [score()], 1.5)
    changed = json.loads(json.dumps(expected))
    if change == "model":
        changed["model_sha256"] = "different-model"
    elif change == "server":
        changed["server"]["arguments"] = ["--ctx-size", "4096"]
    else:
        changed["item_manifest_sha256"] = "different-manifest"
    with pytest.raises(StopRequired, match="lacks matching completed live"):
        measurement.load_live_measurement(paths, changed)


def test_nvidia_smi_unavailable_or_invalid_stops(monkeypatch: pytest.MonkeyPatch) -> None:
    def missing(*_: object, **__: object) -> None:
        raise FileNotFoundError("nvidia-smi")

    monkeypatch.setattr(telemetry.subprocess, "run", missing)
    with pytest.raises(StopRequired, match="cannot measure"):
        measurement.query_vram_mib()
    monkeypatch.setattr(
        telemetry.subprocess,
        "run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess([], 1, "", "unavailable"),
    )
    with pytest.raises(StopRequired, match="no valid single-GPU"):
        measurement.query_vram_mib()


def test_incomplete_live_trial_cannot_supply_cache_only_peak(tmp_path: Path) -> None:
    paths = Paths(tmp_path)
    expected = identity()
    measurement.record_live_request(paths, expected, "key-0", 600, 1, 1.0, 8, 0.5)
    with pytest.raises(StopRequired, match="lacks matching completed live"):
        measurement.load_live_measurement(paths, expected)
    with pytest.raises(StopRequired, match="lack matching live measurement"):
        measurement.finalize_measurement(
            paths, expected, ["key-0", "key-1"], [score(), score(True)], 1.5
        )
    assert (
        json.loads(measurement.measurement_path(paths, expected).read_text())["status"]
        == "INCOMPLETE"
    )


def test_conflicting_or_tampered_live_provenance_stops(tmp_path: Path) -> None:
    paths = Paths(tmp_path)
    expected = identity()
    measurement.record_live_request(paths, expected, "key-0", 600, 1, 1.0, 8, 0.5)
    with pytest.raises(StopRequired, match="conflicts"):
        measurement.record_live_request(paths, expected, "key-0", 650, 1, 2.0, 8, None)
    path = measurement.measurement_path(paths, expected)
    record = json.loads(path.read_text(encoding="utf-8"))
    record["peak_vram_mib"] = 1
    path.write_text(json.dumps(record), encoding="utf-8")
    with pytest.raises(StopRequired, match="provenance"):
        measurement.load_live_measurement(paths, expected)


def test_p0_cache_only_without_evidence_cannot_write_decision(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = Paths(tmp_path)
    config = load_config()
    task = Task.model_construct(task_id="t0", n_tests=3)
    items = [
        Item.model_construct(
            item_id=f"i{i}", task_id="t0", messages=[Message(role="user", content=f"fixture-{i}")]
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
    monkeypatch.setattr(p0, "trial_identity", lambda *_args: identity())
    monkeypatch.setattr(p0, "query_vram_mib", lambda *_args: 100)

    class FakeClient:
        model_hash = "fixture-model"
        flags = {"gpu_layers": 1}
        server_startup_seconds = 0.5

        def complete(self, _messages: object, _parameters: object) -> Completion:
            return Completion("RESULT: 3/3", 1.0, 8, True, datetime.now(UTC).isoformat(), "stop")

    @contextmanager
    def fake_session(*_: object) -> Iterator[FakeClient]:
        yield FakeClient()

    monkeypatch.setattr(p0, "model_session", fake_session)
    with pytest.raises(StopRequired, match="lacks matching live VRAM"):
        p0.run_p0(paths, config, logging.getLogger("test-p0-cache-only"))
    assert not (paths.results / "p0.json").exists()


def test_p0_live_mock_persists_vram_then_reuses_it_on_restart(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = Paths(tmp_path)
    config = load_config()
    task = Task.model_construct(task_id="t0", n_tests=3)
    items = [
        Item.model_construct(
            item_id=f"i{i}", task_id="t0", messages=[Message(role="user", content=f"fixture-{i}")]
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
    monkeypatch.setattr(p0, "trial_identity", lambda *_args: identity())
    monkeypatch.setattr(p0, "query_vram_mib", lambda *_args: 600)
    is_cached = False

    class FakeClient:
        model_hash = "fixture-model"
        flags = {"gpu_layers": 1}
        server_startup_seconds = 0.5

        def complete(self, _messages: object, _parameters: object) -> Completion:
            return Completion(
                "RESULT: 3/3", 1.0, 8, is_cached, datetime.now(UTC).isoformat(), "stop"
            )

    @contextmanager
    def fake_session(*_: object) -> Iterator[FakeClient]:
        yield FakeClient()

    monkeypatch.setattr(p0, "model_session", fake_session)
    first = p0.run_p0(paths, config, logging.getLogger("test-p0-live"))
    assert first["peak_vram_mib"] == 600
    assert first["vram_live_requests"] == 100
    is_cached = True
    second = p0.run_p0(paths, config, logging.getLogger("test-p0-restart"))
    assert second["peak_vram_mib"] == 600
    assert second["vram_live_requests"] == 100


def test_interrupted_p0_combines_only_matching_live_measurements(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = Paths(tmp_path)
    config = load_config()
    task = Task.model_construct(task_id="t0", n_tests=3)
    items = [
        Item.model_construct(
            item_id=f"i{i}", task_id="t0", messages=[Message(role="user", content=f"fixture-{i}")]
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
    monkeypatch.setattr(p0, "trial_identity", lambda *_args: identity())
    phase = ["first"]
    monkeypatch.setattr(p0, "query_vram_mib", lambda *_args: 700 if phase[0] == "first" else 500)

    class FakeClient:
        model_hash = "fixture-model"
        flags = {"gpu_layers": 1}
        server_startup_seconds = 0.5

        def complete(self, messages: list[Message], _parameters: object) -> Completion:
            index = int(messages[0].content.rsplit("-", 1)[1])
            if phase[0] == "first" and index == 50:
                raise RuntimeError("interrupted after 50 live calls")
            cached = phase[0] == "resume" and index < 50
            return Completion("RESULT: 3/3", 1.0, 8, cached, datetime.now(UTC).isoformat(), "stop")

    @contextmanager
    def fake_session(*_: object) -> Iterator[FakeClient]:
        yield FakeClient()

    monkeypatch.setattr(p0, "model_session", fake_session)
    with pytest.raises(RuntimeError, match="interrupted"):
        p0.run_p0(paths, config, logging.getLogger("test-p0-interrupted"))
    assert not (paths.results / "p0.json").exists()
    assert (
        json.loads(measurement.measurement_path(paths, identity()).read_text())["status"]
        == "INCOMPLETE"
    )
    phase[0] = "resume"
    resumed = p0.run_p0(paths, config, logging.getLogger("test-p0-resume"))
    assert resumed["peak_vram_mib"] == 700
    assert resumed["vram_live_requests"] == 100
    assert resumed["live_requests_this_run"] == 50
    assert resumed["cache_hits_this_run"] == 50
