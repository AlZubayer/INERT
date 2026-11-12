"""Fixed direct pass-count diagnostic contract."""

from inert.config import Paths
from inert.diagnostic_direct_pass_count import (
    DIRECT_COUNT,
    FIXED_DENOMINATOR,
    DirectPaths,
    analyze_response,
    build_cases,
)


def test_fixed_matrix_and_messages() -> None:
    cases = build_cases(Paths.discover())
    assert len(cases) == 16
    assert len({case["case_id"] for case in cases}) == 16
    for model in ("wm_c", "wm_b"):
        for passed in range(4):
            pair = [
                case
                for case in cases
                if case["model_role"] == model and case["control"] == f"C{passed}"
            ]
            assert {case["interface"] for case in pair} == {
                "DIRECT_COUNT",
                "FIXED_DENOMINATOR",
            }
            assert pair[0]["source_code"] == pair[1]["source_code"]
            assert pair[0]["tests"] == pair[1]["tests"]
            assert pair[0]["source_code"] == "def f(x):\n    return x"
            assert pair[0]["tests"] == ["assert True"] * passed + ["assert False"] * (3 - passed)
            assert pair[0]["messages"][0] == pair[1]["messages"][0]
            left = pair[0]["messages"][1]["content"]
            right = pair[1]["messages"][1]["content"]
            assert left.removesuffix(DIRECT_COUNT) == right.removesuffix(FIXED_DENOMINATOR)
            assert "RESULT: " not in left.removesuffix(DIRECT_COUNT)
            assert "RESULT: " not in right.removesuffix(FIXED_DENOMINATOR)


def test_artifact_isolation() -> None:
    paths = DirectPaths(Paths.discover().root, "smoke")
    assert "direct_pass_count_20261112" in str(paths.cache("wm_c"))
    assert paths.cache("wm_b") != paths.cache("wm_c")
    assert paths.cache("wm_c") != Paths(paths.root, "smoke").cache("wm_c")


def test_accuracy_and_frozen_parser() -> None:
    correct = analyze_response("RESULT: 2/3", 2, 3, "stop")
    assert correct["strict_format"] and correct["parser_status"] == "ok"
    assert correct["exact_count"] and correct["label_correct"]
    wrong = analyze_response("RESULT: 3/3", 2, 3, "stop")
    assert wrong["parser_status"] == "ok" and not wrong["exact_count"]
    assert not wrong["label_correct"]
    denominator = analyze_response("RESULT: 2/2", 2, 3, "stop")
    assert denominator["strict_format"] and denominator["parser_status"] == "fail"
    assert denominator["wrong_denominator"] and not denominator["exact_count"]
    verbose = analyze_response("Reasoning.\nRESULT: 2/3", 2, 3, "stop")
    assert not verbose["strict_format"] and verbose["parser_status"] == "ok"
    absent = analyze_response("No answer", 2, 3, "length")
    assert absent["parser_status"] == "fail" and not absent["exact_count"]
