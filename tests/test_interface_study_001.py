"""Offline protocol-preparation and final-answer checks for INERT-INTERFACE-001."""

import hashlib
from pathlib import Path

import pytest

from inert.config import Paths
from inert.interface_study_001 import (
    build,
    canonical,
    choose_pair,
    file_sha,
    finalized_result,
    render_b,
    selected_tasks,
    sha,
)
from inert.render import render_conversation, render_messages
from inert.schemas import Candidate, Task


def _candidate(candidate_id: str, index: int, passed: int) -> Candidate:
    source = "def f(x):\n    return x\n"
    return Candidate.from_source(candidate_id, "mbpp-1", index, "proposer", source).model_copy(
        update={
            "n_tests": 3,
            "n_passed": passed,
            "R_exec": passed / 3,
            "true_pass": passed == 3,
            "harness_output": f"RESULT: {passed}/3\n",
            "in_core_set": True,
        }
    )


def test_selection_is_deterministic_and_excludes_prior_exposure() -> None:
    tasks = [f"mbpp-{number}" for number in range(30)]
    exposed = {"mbpp-0", "mbpp-8", "mbpp-12"}
    first = selected_tasks(exposed, tasks, 18)
    assert first == selected_tasks(exposed, list(reversed(tasks)), 18)
    assert len(first) == len(set(first)) == 18
    assert not set(first) & exposed
    assert not set(first) & {"mbpp-100", "mbpp-101"}


def test_selection_stops_when_heldout_supply_is_too_small() -> None:
    with pytest.raises(ValueError, match="Only 17"):
        selected_tasks({"mbpp-0"}, [f"mbpp-{i}" for i in range(18)], 18)


def test_candidate_pair_requires_recorded_docker_truth() -> None:
    task = Task(
        task_id="mbpp-1",
        source="mbpp",
        prompt="Implement f",
        fn_name="f",
        tests=["assert f(1) == 1"] * 3,
        n_tests=3,
        reference_code="def f(x): return x",
    )
    candidates = [_candidate("fail-late", 3, 2), _candidate("pass", 2, 3), _candidate("fail", 1, 0)]
    executions = {
        candidate.cand_id: {
            "status": "ok",
            "stdout": candidate.harness_output,
            "load_ok": True,
        }
        for candidate in candidates
    }
    passing, failing = choose_pair(task, candidates, executions)
    assert (passing.cand_id, failing.cand_id) == ("pass", "fail")
    executions["fail"]["stdout"] = "RESULT: 3/3\n"
    assert choose_pair(task, candidates, executions)[1].cand_id == "fail-late"
    del executions["fail-late"]
    with pytest.raises(ValueError, match="lacks a Docker-verified core pair"):
        choose_pair(task, candidates, executions)


@pytest.mark.parametrize(
    ("raw", "finish", "status"),
    [
        ("RESULT: 2/3", "stop", "ok"),
        ("<think>RESULT: 3/3</think>\nRESULT: 2/3", "stop", "ok"),
        ("<think>RESULT: 3/3</think>", "stop", "result_only_in_reasoning"),
        ("<think>RESULT: 3/3", "length", "truncated_or_unfinished"),
        ("<think>RESULT: 3/3", "stop", "unclosed_or_multiple_think"),
        ("RESULT: 3/3", "length", "truncated_or_unfinished"),
        ("RESULT: 3/4", "stop", "wrong_denominator"),
        ("RESULT: 4/3", "stop", "out_of_range"),
        ("RESULT: -1/3", "stop", "out_of_range"),
        ("RESULT: 1/3\nRESULT: 2/3", "stop", "multiple_results"),
        ("RESULT: x/3", "stop", "malformed_result"),
        ("prediction RESULT: 1/3", "stop", "result_not_standalone"),
        ("RESULT: 1/3\nmore explanation", "stop", "not_final"),
        ("terminal transcript\nRESULT: 1/3\nroot@host:/app#", "stop", "ok"),
    ],
)
def test_finalized_answer_rejects_reasoning_and_nonfinal_results(
    raw: str, finish: str, status: str
) -> None:
    assert finalized_result(raw, finish, 3)[0] == status


def test_canonical_hash_is_order_independent() -> None:
    left = {"b": 2, "a": ["β", 1]}
    right = {"a": ["β", 1], "b": 2}
    assert canonical(left) == canonical(right)
    assert sha(left) == hashlib.sha256(canonical(right)).hexdigest()


def test_b_template_keeps_code_tests_and_no_answer() -> None:
    paths = Paths.discover()
    task = Task(
        task_id="mbpp-1",
        source="mbpp",
        prompt="Implement f",
        fn_name="f",
        tests=["assert f(1) == 1", "assert f(2) == 2", "assert f(3) == 3"],
        n_tests=3,
        reference_code="def f(x): return x",
    )
    candidate = _candidate("pass", 0, 3)
    for channel in ("C", "D"):
        baseline = render_messages(task, candidate, channel, "T0", "", "vendored", paths)
        proposed = render_b(task, candidate, channel, paths)
        assert "def f(x)" in proposed[1].content
        assert "assert f(1) == 1" in proposed[1].content
        assert "RESULT: 3/3" not in proposed[1].content
        if channel == "C":
            assert baseline[1].content in proposed[1].content
        else:
            assert render_conversation(task, candidate, "") in proposed[1].content
        assert baseline != proposed


@pytest.mark.skipif(
    not Path("data/interface_study_001/manifest.json").is_file(),
    reason="Ignored study preparation data are unavailable in this checkout.",
)
def test_prepared_manifest_and_frozen_pilot_inputs_are_unchanged() -> None:
    root = Paths.discover().root
    protocol = root / "results/pilot/INERT_Interface_Study_Protocol_20261114.md"
    originals = [
        root / "data/p0/selection_manifest.json",
        root / "data/cache/wm_a.sqlite",
        root / "data/items.jsonl",
        root / "configs/pilot.yaml",
        root / "src/inert/render.py",
        root / "src/inert/parse.py",
    ]
    before = {p: file_sha(p) for p in originals}
    result = build(root, protocol)
    assert {p: file_sha(p) for p in originals} == before
    manifest = result["manifest"]
    assert len(manifest["assignments"]) == 192
    assert len({row["assignment_id"] for row in manifest["assignments"]}) == 192
    assert len({row["message_sha256"] for row in manifest["assignments"]}) == 192
    assert manifest["manifest_sha256"] == sha(
        {key: value for key, value in manifest.items() if key != "manifest_sha256"}
    )
    assert len(result["split"]["development_task_ids"]) == 6
    assert len(result["split"]["heldout_task_ids"]) == 18
    assert not set(result["split"]["heldout_task_ids"]) & set(result["registry"]["task_sources"])
    assert len(result["split"]["excluded_exposed_official_task_ids"]) == 9
    assert all(
        len(candidate_ids) == 2
        for candidate_ids in result["split"]["selected_candidate_ids"].values()
    )
    assert "passing" not in result["split"] and "failing" not in result["split"]
    assert len(result["truth"]["candidate_truth"]) == 48
    assert all("n_passed" not in row and "true_pass" not in row for row in manifest["assignments"])
