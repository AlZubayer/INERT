"""Fixed real-candidate direct diagnostic controls."""

import hashlib
import json
from collections import Counter

from inert.config import Paths
from inert.diagnostic_direct_pass_count import (
    DIRECT_COUNT,
    FIXED_DENOMINATOR,
    analyze_response,
    input_hash,
)
from inert.diagnostic_direct_real import RealPaths, build_cases, historical_t0
from inert.schemas import Candidate, Message, Task, read_jsonl


def test_fixed_matrix_preserves_code_tests_and_direct_structure() -> None:
    paths = Paths.discover()
    cases = build_cases(paths)
    assert len(cases) == 16
    assert len({case["case_id"] for case in cases}) == 16
    assert {case["candidate_id"] for case in cases} == {
        "mbpp-440-g00",
        "mbpp-310-g00",
        "mbpp-440-g04",
        "mbpp-265-g01",
    }
    source = Paths(paths.root, "smoke")
    candidates = {c.cand_id: c for c in read_jsonl(source.candidates, Candidate)}
    tasks = {t.task_id: t for t in read_jsonl(source.tasks, Task)}
    for case in cases:
        candidate = candidates[case["candidate_id"]]
        task = tasks[candidate.task_id]
        assert case["source_code"] == candidate.code_stripped
        assert case["tests"] == task.tests
        assert case["code_sha256"] == candidate.code_sha256
        assert (
            case["test_sha256"]
            == hashlib.sha256(json.dumps(task.tests, ensure_ascii=False).encode()).hexdigest()
        )
        messages = [Message.model_validate(m) for m in case["messages"]]
        assert case["input_sha256"] == input_hash(messages)
        assert f"RESULT: {candidate.n_passed}/3" not in messages[1].content
    for model in ("wm_c", "wm_b"):
        for candidate_id in ("mbpp-440-g00", "mbpp-310-g00", "mbpp-440-g04", "mbpp-265-g01"):
            pair = [
                c for c in cases if c["model_role"] == model and c["candidate_id"] == candidate_id
            ]
            assert {c["interface"] for c in pair} == {"DIRECT_COUNT", "FIXED_DENOMINATOR"}
            assert pair[0]["source_code"] == pair[1]["source_code"]
            assert pair[0]["tests"] == pair[1]["tests"]
            assert pair[0]["messages"][0] == pair[1]["messages"][0]
            users = {case["interface"]: case["messages"][1]["content"] for case in pair}
            assert users["DIRECT_COUNT"].removesuffix(DIRECT_COUNT) == users[
                "FIXED_DENOMINATOR"
            ].removesuffix(FIXED_DENOMINATOR)
            assert pair[0]["source_code"] in users["DIRECT_COUNT"]
            assert all(test in users["DIRECT_COUNT"] for test in pair[0]["tests"])


def test_historical_t0_pairing_and_isolation() -> None:
    paths = RealPaths(Paths.discover().root, "smoke")
    historical = historical_t0(paths)
    assert len(historical) == 32
    assert len({row["case_id"] for row in historical}) == 32
    assert all(row["condition"] == "T0" for row in historical)
    assert {row["model_role"] for row in historical} == {"wm_c", "wm_b"}
    assert set(
        Counter((row["model_role"], row["candidate_id"]) for row in historical).values()
    ) == {4}
    assert "direct_real_candidates_20261112" in str(paths.cache("wm_c"))
    assert paths.cache("wm_b") != paths.cache("wm_c")
    assert paths.cache("wm_c") != Paths(paths.root, "smoke").cache("wm_c")


def test_frozen_parser_and_coverage_adjusted_accuracy() -> None:
    assert analyze_response("RESULT: 2/3", 2, 3, "stop")["exact_count"]
    wrong = analyze_response("RESULT: 3/3", 2, 3, "stop")
    assert wrong["parser_status"] == "ok" and not wrong["exact_count"]
    invalid = analyze_response("RESULT: 2/2", 2, 3, "stop")
    assert invalid["parser_status"] == "fail" and not invalid["exact_count"]
