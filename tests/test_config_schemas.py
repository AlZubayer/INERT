import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from inert.config import Paths, load_config
from inert.schemas import Candidate, Score, Task, read_jsonl, write_jsonl


def test_frozen_design_values() -> None:
    cfg = load_config()
    assert cfg["tasks"] == {"count": 50, "reserves": 10, "seed": 20261111, "max_tokens": 1500}
    assert cfg["sampling"]["wm"] == {
        "temperature": 0.0,
        "top_p": 1.0,
        "max_tokens": 1024,
        "seed": 0,
    }
    assert cfg["statistics"]["bootstrap_resamples"] == 10000
    assert cfg["statistics"]["bootstrap_seed"] == 0
    assert cfg["thresholds"] == {
        "validity_lower": 0.55,
        "validity_upper": 0.95,
        "effect": 0.10,
        "no_effect": 0.05,
        "stripping": 0.03,
        "regret": 0.03,
        "parse_failure": 0.10,
        "p0_truncation": 0.05,
        "p0_full_seconds": 20,
        "p0_reduced_seconds": 50,
        "max_gpu_hours": 60,
    }
    assert cfg["selection"]["pool_sizes"] == [1, 2, 4, 8, 16]
    assert cfg["selection"]["repetitions"] == 1000
    assert cfg["selection"]["assignment_seed_base"] == 777
    assert cfg["server"]["context_size"] == 8192


def test_paths_single_root(tmp_path: Path) -> None:
    paths = Paths(tmp_path)
    assert paths.tasks == tmp_path / "data" / "tasks.jsonl"
    assert paths.summary == tmp_path / "results" / "pilot" / "summary.json"
    assert paths.cache("wm_b") == tmp_path / "data" / "cache" / "wm_b.sqlite"
    with pytest.raises(ValueError):
        paths.cache("../escape")


def test_smoke_profile_isolated_and_frozen_pilot_unchanged(tmp_path: Path) -> None:
    import shutil

    source = Paths.discover()
    shutil.copytree(source.configs, tmp_path / "configs")
    pilot, smoke = Paths(tmp_path), Paths(tmp_path, "smoke")
    assert smoke.data == tmp_path / "data/smoke"
    assert smoke.results == tmp_path / "results/pilot/smoke"
    assert smoke.server_lock == pilot.server_lock
    assert smoke.environment == pilot.environment
    assert load_config(smoke)["tasks"]["count"] == 3
    assert load_config(smoke)["scoring_order"] == ["wm_c"]
    assert load_config(pilot)["tasks"]["count"] == 50
    assert load_config(smoke)["thresholds"] == load_config(pilot)["thresholds"]


def test_jsonl_validation_and_atomic_write(tmp_path: Path) -> None:
    task = Task(
        task_id="t1",
        source="fixture",
        prompt="Return x",
        fn_name="f",
        tests=["assert f(1) == 1"] * 3,
        n_tests=3,
        reference_code="def f(x): return x",
    )
    path = tmp_path / "tasks.jsonl"
    write_jsonl(path, [task], Task)
    assert read_jsonl(path, Task) == [task]
    with pytest.raises(ValidationError):
        Task(**{**task.model_dump(), "n_tests": 4})
    with pytest.raises(ValidationError):
        Task(**{**task.model_dump(), "unexpected": True})
    with pytest.raises(ValidationError):
        Task(**{**task.model_dump(), "n_tests": "3"})
    original = path.read_bytes()
    with pytest.raises((ValidationError, TypeError)):
        write_jsonl(path, [task, {"bad": 1}], Task)
    assert path.read_bytes() == original
    path.write_text(json.dumps({"bad": 1}) + "\n")
    with pytest.raises(ValueError, match="line 1"):
        read_jsonl(path, Task)


def test_candidate_hash_and_reward_validation() -> None:
    cand = Candidate.from_source("c1", "t1", 0, "proposer", "def f(x): return x # note")
    assert cand.natural_text == "note"
    with pytest.raises(ValidationError):
        Candidate(**{**cand.model_dump(), "code_sha256": "0" * 64})
    with pytest.raises(ValidationError):
        Candidate(
            **{
                **cand.model_dump(),
                "n_tests": 3,
                "n_passed": 4,
                "R_exec": 4 / 3,
                "true_pass": False,
                "harness_output": "RESULT: 4/3\n",
            }
        )


def test_score_rejects_imputed_failure() -> None:
    base = dict(
        item_id="i1",
        wm_id="wm_b",
        raw_output="bad",
        parse_status="fail",
        k_pred=None,
        n_pred=None,
        R_sim=None,
        pred_pass=None,
        latency_s=0.1,
        completion_tokens=1,
        cache_hit=False,
        timestamp="2026-11-11T00:00:00+00:00",
    )
    Score(**base)
    with pytest.raises(ValidationError):
        Score(**{**base, "R_sim": 0.0, "pred_pass": False})
