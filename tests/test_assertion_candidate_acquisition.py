"""Frozen acquisition controls; no proposer or candidate code runs here."""

import json

import pytest

from inert.config import Paths
from inert.diagnostic_assertion_acquisition import (
    AcquisitionPaths,
    attempt_plan,
    choose_shortlist,
    classify_result,
    freshness_status,
    has_diverse_pair,
    select_task_ids,
)
from inert.schemas import Candidate
from inert.tasks import normalize_mbpp, task_token_text


def test_task_selection_and_seed_schedule() -> None:
    ids = ["mbpp-4", "mbpp-2", "mbpp-3", "mbpp-1"]
    assert select_task_ids(ids, 3) == select_task_ids(list(reversed(ids)), 3)
    assert len(set(select_task_ids(ids, 3))) == 3
    plan = attempt_plan(["mbpp-125", "mbpp-603"])
    assert len(plan) == 32
    assert [row["seed"] for row in plan[:2]] == [1000, 1001]
    assert [row["seed"] for row in plan[16:18]] == [1100, 1101]
    assert len(attempt_plan([f"mbpp-{i}" for i in range(8)])) == 128
    with pytest.raises(ValueError, match="eight tasks"):
        attempt_plan([f"mbpp-{i}" for i in range(9)])
    with pytest.raises(ValueError, match="Duplicate eligible"):
        select_task_ids(["mbpp-1", "mbpp-1"])
    root = Paths.discover().root
    isolated = AcquisitionPaths(root, "smoke").data
    assert isolated == root / "data/smoke/diagnostics/assertion_candidate_acquisition_20261112"
    assert isolated != Paths(root, "smoke").data
    assert isolated != Paths(root).data


def test_three_original_tests_imports_and_strict_token_text() -> None:
    row = {
        "task_id": 999,
        "prompt": "Return a square root.",
        "code": "def root(x):\n    return x ** 0.5",
        "test_imports": ["import math"],
        "test_list": [
            "assert root(1) == 1",
            "assert root(4) == 2",
            "assert root(9) == 3",
        ],
    }
    task = normalize_mbpp(row)
    assert task.n_tests == 3
    assert task.tests == [f"import math\n{test}" for test in row["test_list"]]
    assert task_token_text(task) == "\n".join([task.prompt, task.reference_code, *task.tests])
    row["test_list"].pop()
    assert normalize_mbpp(row).n_tests == 2


def test_docker_result_classification_and_shortlist_order() -> None:
    assert classify_result("RESULT: 1/3\n", 0) == 1
    assert classify_result("RESULT: 3/3\n", 0) == 3
    assert classify_result("RESULT: 1/2\n", 0) is None
    assert classify_result("RESULT: 1/3\nmore", 0) is None
    assert classify_result("RESULT: 1/3\n", 1) is None
    rows = [
        {"candidate_id": "a-g03", "task_id": "a", "gen_index": 3, "code_sha256": "h3"},
        {"candidate_id": "a-g01", "task_id": "a", "gen_index": 1, "code_sha256": "h1"},
        {"candidate_id": "b-g02", "task_id": "b", "gen_index": 2, "code_sha256": "h2"},
    ]
    assert [x["candidate_id"] for x in choose_shortlist(rows, ["a", "b"])] == [
        "a-g01",
        "b-g02",
    ]
    assert [x["candidate_id"] for x in choose_shortlist(rows[:2], ["a", "b"])] == [
        "a-g01",
        "a-g03",
    ]
    assert not has_diverse_pair(rows[:2])
    assert has_diverse_pair(rows)
    assert not has_diverse_pair(rows[2:])
    assert freshness_status("new", "newhash", {"old"}, {"oldhash"})["fresh"]
    assert not freshness_status("old", "newhash", {"old"}, set())["fresh"]
    assert not freshness_status("new", "oldhash", set(), {"oldhash"})["fresh"]


def test_comment_stripping_deduplicates_equivalent_candidate_code() -> None:
    a = Candidate.from_source("a", "mbpp-1", 0, "proposer", "def f():\n    return 1")
    b = Candidate.from_source("b", "mbpp-1", 1, "proposer", "# comment\ndef f():\n    return 1")
    assert a.code_sha256 == b.code_sha256


def test_local_acquisition_artifacts_reconcile_if_available() -> None:
    """Audit this run's ignored evidence locally; CI without data skips it."""
    base = AcquisitionPaths(Paths.discover().root, "smoke").data
    if not (base / "analysis.json").exists():
        pytest.skip("Ignored local acquisition archive is not present")

    def read(name: str) -> dict:
        return json.loads((base / name).read_text(encoding="utf-8"))

    selection, plan, analysis = (
        read("task_selection_manifest.json"),
        read("generation_attempt_manifest.json"),
        read("analysis.json"),
    )
    ids = [entry["task"]["task_id"] for entry in selection["selected"]]
    assert len(ids) == 8 == len(set(ids))
    assert all(len(entry["task"]["tests"]) == 3 for entry in selection["selected"])
    assert len(plan["attempts"]) == 128
    assert [(row["task_id"], row["gen_index"], row["seed"]) for row in plan["attempts"]] == [
        (row["task_id"], row["gen_index"], row["seed"]) for row in attempt_plan(ids)
    ]
    assert len(list((base / "responses").glob("*.json"))) == analysis["completed_proposer_calls"]
    assert len(list((base / "executions").glob("*.json"))) == analysis["docker_executions"]
    freshness = read("freshness_audit.json")
    assert len(freshness["rows"]) == analysis["accepted_unique_candidates"]
    assert all(row["fresh"] for row in freshness["rows"])
    assert has_diverse_pair(analysis["selected_shortlist"])
    for row in analysis["qualifying_one_of_three"]:
        execution = read(f"executions/{row['candidate_id']}.json")
        assert execution["stdout"] == "RESULT: 1/3\n"
        assert execution["load_ok"] is True
        assert execution["import_probe"] == {
            "stdout": "RESULT: 1/1\n",
            "stderr": "",
            "returncode": 0,
        }
