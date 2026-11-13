"""The assertion diagnostic must keep prompts truth-free and Docker semantics exact."""

import json
import shutil

import pytest

from inert.config import Paths, load_config
from inert.diagnostic_assertion_analysis import (
    analyze,
    parse_aggregate,
    parse_extraction,
    parse_individual,
)
from inert.diagnostic_assertion_run import (
    SELECTED_IDS,
    RunPaths,
    _messages,
    _selection,
    build_cases,
    oracle_harness,
    parse_oracle,
    response_path,
)
from inert.diagnostic_direct_pass_count import DIRECT_COUNT, SYSTEM
from inert.diagnostic_failure_isolation import input_hash
from inert.parse import parse_result
from inert.sandbox import DockerSandbox
from inert.schemas import Message


def test_frozen_source_builds_48_independent_truth_free_requests() -> None:
    paths = RunPaths(Paths.discover().root, "smoke")
    archive = paths.data.parent / "selection_resume" / "source_archive.json"
    if not archive.exists():
        pytest.skip("Frozen local selection archive is absent.")
    rows, _, frozen_aggregate = _selection(paths)
    source = json.loads(archive.read_text(encoding="utf-8"))["rows"]
    assert rows == source
    detailed = paths.data / "per_assertion_oracle.json"
    if detailed.exists():
        oracle = json.loads(detailed.read_text(encoding="utf-8"))["rows"]
        for row, aggregate in zip(oracle, frozen_aggregate["rows"], strict=True):
            assert row["candidate_id"] == aggregate["candidate_id"]
            assert row["vector"].count("P") == aggregate["n_passed"]
            assert row["aggregate_stdout"] == aggregate["recorded_stdout"]
    cases = build_cases(source)
    assert len(cases) == 48
    assert len({case["case_id"] for case in cases}) == 48
    assert len({case["input_sha256"] for case in cases}) == 24
    assert [case["candidate_id"] for case in cases[:8]] == list(SELECTED_IDS)
    assert [(case["stage"], case["model_role"]) for case in cases[::8]] == [
        ("A", "wm_b"),
        ("A", "wm_c"),
        ("B", "wm_b"),
        ("B", "wm_c"),
        ("C", "wm_b"),
        ("C", "wm_c"),
    ]
    for case in cases:
        payload = json.dumps(case)
        assert all(marker not in payload for marker in ('"n_passed"', '"outcome_stratum"'))
        if case["stage"] != "B":
            assert "TEST_RESULTS:" not in payload
        assert case["input_sha256"] == input_hash(
            [Message.model_validate(message) for message in case["messages"]]
        )
        assert response_path(paths, case).is_relative_to(paths.data / "responses")
    assert not (paths.root / "results/pilot").is_relative_to(paths.data)


def test_stage_c_reuses_exact_direct_count_structure() -> None:
    code = "def f(x):\n    return x"
    tests = ["assert f(1) == 1", "assert f(2) == 2", "assert f(3) == 3"]
    messages = _messages("C", code, tests)
    assert messages[0].content == SYSTEM
    assert messages[1].content == (
        "solution.py:\n```python\n"
        + code
        + "\n```\n\nTest assertions:\n"
        + "\n".join(f"{index}. {test}" for index, test in enumerate(tests, 1))
        + "\n\n"
        + DIRECT_COUNT
    )
    assert _messages("A", code, tests) != _messages("B", code, tests)
    assert _messages("B", code, tests) != messages


def test_instrumented_oracle_matches_harness_exception_semantics_in_docker(tmp_path) -> None:
    if not shutil.which("docker"):
        pytest.skip("Docker is unavailable.")
    # This test makes fresh Docker calls. Keep its cache out of frozen diagnostic data.
    sandbox = DockerSandbox(Paths(tmp_path), load_config(Paths.discover())["sandbox"])
    code = "def f(x):\n    if x == 0:\n        while True: pass\n    return x"
    tests = ["assert f(1) == 1", "assert f(2) == 3", "assert f(0) == 0"]
    result = sandbox.run(code, oracle_harness(tests, 1), use_cache=False)
    parsed = parse_oracle(result.stdout, result.returncode, result.stderr)
    assert parsed["load_status"] == "ok"
    assert [row["status"] for row in parsed["test_results"]] == [
        "PASS",
        "ASSERTION_FAIL",
        "TIMEOUT",
    ]
    assert parsed["harness_equivalent_vector"] == ["P", "F", "F"]
    failing = sandbox.run("raise RuntimeError('load')", oracle_harness(tests, 1), use_cache=False)
    parsed_fail = parse_oracle(failing.stdout, failing.returncode, failing.stderr)
    assert parsed_fail["load_status"] == "import_failure"
    assert parsed_fail["import_exception"] == "RuntimeError"
    assert parsed_fail["test_results"] == []
    assert parsed_fail["harness_equivalent_vector"] == ["F", "F", "F"]


def test_strict_stage_parsers_and_frozen_count_parser() -> None:
    expected = ["assert f(1) == 1", "assert f(2) == 2", "assert f(3) == 3"]
    assert parse_extraction(json.dumps(expected), expected)["exact"]
    reordered = parse_extraction(json.dumps(expected[::-1]), expected)
    assert reordered["valid_structure"] and reordered["reordered"]
    assert not reordered["exact"]
    changed = parse_extraction(
        json.dumps([expected[0], expected[1], "assert source_only"]), expected
    )
    assert changed["missing"] == [expected[2]]
    assert changed["invented"] == ["assert source_only"]
    assert not parse_extraction("```json\n" + json.dumps(expected) + "\n```", expected)[
        "valid_json"
    ]
    assert parse_individual("TEST_RESULTS: P,F,P")["vector"] == ["P", "F", "P"]
    assert parse_individual("P,F,P")["vector"] is None
    assert parse_individual("TEST_RESULTS:PPP")["vector"] is None
    assert parse_individual("TEST_RESULTS: P,F,P\nextra")["vector"] is None
    for raw in ("RESULT: 2/3", "RESULT: 2/4", "RESULT: 3/3\nextra", "nonsense"):
        parsed = parse_aggregate(raw)
        frozen = parse_result(raw, 3)
        assert parsed["parser_status"] == frozen.parse_status
        assert parsed["k_pred"] == frozen.k_pred
        assert parsed["n_pred"] == frozen.n_pred


def test_frozen_48_call_analysis_when_local_run_is_available() -> None:
    paths = RunPaths(Paths.discover().root, "smoke")
    if not (paths.data / "responses" / "C-wm_c-acq-mbpp-125-g01.json").exists():
        pytest.skip("Local diagnostic responses are absent.")
    result = analyze(paths)
    assert len(result["responses"]) == 48
    assert len(result["pairs"]) == 16
    assert all(not row["cache_hit"] for row in result["responses"])
    assert result["summary"]["wm_b"]["a_exact"] == 4
    assert result["summary"]["wm_b"]["b_valid_format"] == 0
    assert result["summary"]["wm_c"]["b_valid_format"] == 8
    assert result["summary"]["wm_c"]["b_correct_tests"] == 12
    assert result["summary"]["wm_c"]["b_exact_vectors"] == 0
    assert result["summary"]["wm_b"]["c_exact_count"] == 2
    assert result["summary"]["wm_c"]["c_exact_count"] == 2
    assert result["summary"]["wm_c"]["type_counts"]["type_4"] == 2
    assert result["summary"]["wm_c"]["type_counts"]["type_6"] == 8
