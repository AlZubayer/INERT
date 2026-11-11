import json

from inert.config import Paths
from inert.diagnostic_failure_isolation import (
    FailurePaths,
    a_cases,
    b_cases,
    c_cases,
    classify_count,
    input_hash,
)
from inert.schemas import Task


def _task(task_id: str) -> Task:
    return Task(
        task_id=task_id,
        source="fixture",
        prompt="Return x.",
        fn_name="f",
        tests=["assert f(1) == 1", "assert f(2) == 2", "assert f(3) == 3"],
        n_tests=3,
        reference_code="def f(x): return x",
    )


def test_failure_paths_separate_all_existing_caches() -> None:
    root = Paths.discover().root
    paths = FailurePaths(root, "smoke", "c_inhouse")
    assert paths.data == root / "data/smoke/diagnostics/failure_isolation_20261112"
    assert paths.cache("wm_c") != Paths(root, "smoke").cache("wm_c")
    assert paths.cache("wm_c") != FailurePaths(root, "smoke", "c_vendored").cache("wm_c")
    assert paths.server_lock == Paths(root, "smoke").server_lock


def test_a_cases_are_fixed_pairs_with_same_user_input() -> None:
    cases = a_cases()
    assert len(cases) == 8
    assert len({case.case_id for case in cases}) == 8
    for identifier, answer in [("A1", "READY"), ("A2", "2"), ("A3", "3"), ("A4", "RESULT: 1/3")]:
        pair = [case for case in cases if case.task_id == identifier]
        assert len(pair) == 2
        assert pair[0].messages[-1] == pair[1].messages[-1]
        assert {len(case.messages) for case in pair} == {1, 2}
        assert all(case.expected_text == answer for case in pair)


def test_b_cases_have_all_count_representations() -> None:
    tasks = {name: _task(name) for name in ("mbpp-440", "mbpp-310", "mbpp-265")}
    cases = b_cases(tasks)
    assert len(cases) == 20
    assert len({case.case_id for case in cases}) == 20
    assert {case.expected_text for case in cases} == {"2", "3", "4"}
    for case in cases:
        assert "Do not execute any test" in case.messages[0].content
        assert case.representation in ("B1", "B2", "B3", "B4")
        if case.representation == "B4":
            blob = case.messages[0].content.split("\n\n", 1)[1]
            call = json.loads(blob)
            assert call["name"] == "write_files"
            assert "TESTS = " in call["arguments"]["files"]["run_tests.py"]


def test_c_cases_keep_truth_out_of_messages_and_cover_all_cells() -> None:
    cases = c_cases(Paths.discover())
    assert len(cases) == 16
    assert len({case.case_id for case in cases}) == 16
    assert {case.expected_k for case in cases} == {0, 1, 2, 3}
    assert {(case.channel, case.family) for case in cases} == {
        ("C", "vendored"),
        ("C", "inhouse"),
        ("D", "vendored"),
        ("D", "inhouse"),
    }
    for case in cases:
        assert case.expected_n == 3
        assert case.source_code == "def f(x):\n    return x"
        assert len(case.tests) == 3
        assert case.messages
        assert case.input_sha256 == input_hash(case.messages)
        assert "RESULT: 0/3" not in "\n".join(message.content for message in case.messages)


def test_count_only_parser_is_strict() -> None:
    assert classify_count(" 3\n", 3) == (True, 3)
    assert classify_count("3 tests", 3) == (False, None)
    assert classify_count("10", 3) == (False, 10)
