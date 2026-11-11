import copy
from pathlib import Path

import numpy as np
import pytest

from inert.config import load_config
from inert.decide import cell_a, cell_c, kt_a, kt_b, kt_c, overall, validity
from inert.schemas import Endpoint
from inert.selection import SelectionCandidate, selection_bootstrap, selection_metrics
from inert.stats import balanced_accuracy, bootstrap


def endpoint(value: float | None, lower: float | None, upper: float | None) -> Endpoint:
    return Endpoint(
        estimate=value,
        lower=lower,
        upper=upper,
        n_pairs=4,
        n_tasks=2,
        n_resamples=10,
        n_valid_resamples=10 if value is not None else 0,
        reason=None if value is not None else "No paired data",
    )


@pytest.mark.parametrize(
    ("ba", "expected_a", "expected_b"),
    [
        (0.54, "INVALID", "INVALID"),
        (0.55, "VALID", "VALID"),
        (0.95, "VALID", "VALID"),
        (0.96, "VALID", "INVALID"),
        (None, "UNAVAILABLE", "UNAVAILABLE"),
    ],
)
def test_validity_boundaries(ba: float | None, expected_a: str, expected_b: str) -> None:
    result = validity(ba, load_config()["thresholds"])
    assert (result["kt_a"], result["kt_b"]) == (expected_a, expected_b)


@pytest.mark.parametrize(
    ("estimate", "lower", "upper", "expected"),
    [
        (0.10, 0.01, 0.2, "EFFECT"),
        (0.10, 0.0, 0.2, "MARGINAL"),
        (0.049, -0.01, 0.2, "NO_EFFECT"),
        (0.07, 0.01, 0.099, "NO_EFFECT"),
        (0.05, -0.01, 0.10, "MARGINAL"),
        (None, None, None, "UNAVAILABLE"),
    ],
)
def test_effect_rules(
    estimate: float | None, lower: float | None, upper: float | None, expected: str
) -> None:
    assert cell_a(endpoint(estimate, lower, upper), load_config()["thresholds"]) == expected


@pytest.mark.parametrize(
    ("cells", "expected"),
    [
        ({"wm_a": ["EFFECT"], "wm_b": ["NO_EFFECT"]}, "STRONG_PASS"),
        ({"wm_b": ["EFFECT"], "wm_c": ["EFFECT"]}, "PASS"),
        ({"wm_b": ["NO_EFFECT"], "wm_c": ["EFFECT"]}, "WEAK_ONLY"),
        ({"wm_a": ["NO_EFFECT"], "wm_b": ["NO_EFFECT"]}, "KILL"),
        ({"wm_b": ["MARGINAL"]}, "MARGINAL"),
        ({"wm_a": ["INVALID"], "wm_b": ["INVALID"]}, "INCONCLUSIVE"),
        ({"wm_b": ["UNAVAILABLE"]}, "UNAVAILABLE"),
    ],
)
def test_kt_a_verdicts(cells: dict[str, list[str]], expected: str) -> None:
    assert kt_a(cells) == expected


def test_kt_b_verdicts() -> None:
    thresholds = load_config()["thresholds"]
    helps, no = endpoint(0.03, 0.001, 0.05), endpoint(0.029, 0, 0.05)
    assert kt_b([(helps, no)], thresholds) == "TRADE_OFF"
    assert kt_b([(no, helps)], thresholds) == "CLAIMS_ONLY"
    assert kt_b([(no, no)], thresholds) == "STRIP_IS_FREE"
    assert kt_b([], thresholds) == "UNAVAILABLE"


def test_kt_c_rules_and_missing_data() -> None:
    th = load_config()["thresholds"]
    amp, zero, negative = (
        endpoint(0.1, 0.01, 0.2),
        endpoint(0, -0.1, 0.1),
        endpoint(-0.1, -0.2, -0.01),
    )
    harm, no = endpoint(0.03, 0.001, 0.05), endpoint(0.03, 0, 0.05)
    assert cell_c(amp, harm, th) == "AMPLIFIES_AND_HARMS"
    assert cell_c(amp, no, th) == "AMPLIFIES_ONLY"
    assert cell_c(zero, harm, th) == "NO_AMPLIFICATION"
    assert cell_c(negative, harm, th) == "NO_AMPLIFICATION"
    assert cell_c(endpoint(None, None, None), harm, th) == "UNAVAILABLE"
    assert kt_c(["AMPLIFIES_AND_HARMS"]) == "PASS"
    assert kt_c(["NO_AMPLIFICATION", "AMPLIFIES_ONLY"]) == "PARTIAL"
    assert kt_c(["NO_AMPLIFICATION"]) == "KILL"
    assert kt_c([]) == "UNAVAILABLE"


@pytest.mark.parametrize(
    ("a", "c", "b", "decision"),
    [
        ("KILL", "NOT_RUN", "STRIP_IS_FREE", "Stop the project."),
        ("WEAK_ONLY", "NOT_RUN", "STRIP_IS_FREE", "Stop or pivot."),
        ("PASS", "PASS", "TRADE_OFF", "Build the full project"),
        ("STRONG_PASS", "PASS", "CLAIMS_ONLY", "Build the full project"),
        ("PASS", "PASS", "STRIP_IS_FREE", "Build a reduced project"),
        ("PASS", "PARTIAL", "STRIP_IS_FREE", "Borderline."),
        ("PASS", "KILL", "TRADE_OFF", "Drop RQ2."),
        ("MARGINAL", "NOT_RUN", "UNAVAILABLE", "Extend the pilot"),
        ("INCONCLUSIVE", "NOT_RUN", "UNAVAILABLE", "Inconclusive"),
        ("UNAVAILABLE", "NOT_RUN", "UNAVAILABLE", "Unavailable"),
    ],
)
def test_overall_rows(a: str, c: str, b: str, decision: str) -> None:
    assert overall(a, c, b).startswith(decision)


def test_bootstrap_task_clusters_and_reproducibility() -> None:
    cfg = load_config()["statistics"]
    rows = [("a", 0.0), ("a", 0.0), ("b", 1.0), ("b", 1.0)]
    first = bootstrap(rows, lambda data: float(np.mean([x[1] for x in data])), cfg)
    assert first == bootstrap(rows, lambda data: float(np.mean([x[1] for x in data])), cfg)
    assert first.estimate == 0.5 and first.n_tasks == 2
    assert first.lower == 0.0 and first.upper == 1.0
    assert bootstrap([], lambda data: None, cfg).estimate is None
    assert balanced_accuracy([True, False], [True, True]) == 0.5
    assert balanced_accuracy([True], [True]) is None


def test_selection_known_four_candidate_pool() -> None:
    pool = [
        SelectionCandidate("a", 0.0, 1.0, 0.0, True),
        SelectionCandidate("b", 1.0, 0.8, 0.9, False),
        SelectionCandidate("c", 0.5, 0.5, 0.5, False),
        SelectionCandidate("d", 0.2, 0.2, 0.2, False),
    ]
    cfg = load_config()["selection"]
    result = selection_metrics(pool, cfg, np.random.default_rng(cfg["seed"]))
    assert result[4]["A"] == 1.0
    assert result[4]["Regret"] == 1.0
    assert result[4]["Gap_full"] == 1.0
    assert result[4]["Gap_neutral"] == pytest.approx(-0.1)
    assert result[4]["Enrich"] == 4.0
    assert result[16] == result[4]


def test_selection_no_effect_ties_and_reproducible_nested_bootstrap() -> None:
    cfg = copy.deepcopy(load_config())
    cfg["selection"]["repetitions"] = 20
    cfg["statistics"]["bootstrap_resamples"] = 20
    pool = [SelectionCandidate(str(i), i / 3, 0.5, 0.5, False) for i in range(4)]
    result = selection_metrics(pool, cfg["selection"], np.random.default_rng(0))
    assert all(x["A"] == 0 and x["Regret"] == 0 and x["Enrich"] is None for x in result.values())
    tasks = {"t1": pool, "t2": pool}
    first = selection_bootstrap(tasks, cfg, rung="A")
    assert first == selection_bootstrap(tasks, cfg, rung="A")
    assert first["amplification"].estimate == 0
    assert first["regret"].estimate == 0


def test_selection_resumes_exact_rng_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from inert.audit import Progress

    cfg = copy.deepcopy(load_config())
    cfg["statistics"]["bootstrap_resamples"] = 12
    cfg["statistics"]["checkpoint_every"] = 5
    cfg["selection"]["repetitions"] = 20
    pool = [SelectionCandidate(str(i), i / 3, (3 - i) / 3, i / 3, i == 0) for i in range(4)]
    pools = {"task1": pool, "task2": pool}
    expected = selection_bootstrap(pools, cfg, "B")
    checkpoint = tmp_path / "selection.json"
    original = Progress.advance
    calls = 0

    def interrupt(self: Progress) -> None:
        nonlocal calls
        calls += 1
        if calls == 6:
            raise RuntimeError("simulated interruption")
        original(self)

    monkeypatch.setattr(Progress, "advance", interrupt)
    with pytest.raises(RuntimeError, match="simulated"):
        selection_bootstrap(pools, cfg, "B", checkpoint=checkpoint)
    monkeypatch.setattr(Progress, "advance", original)
    assert selection_bootstrap(pools, cfg, "B", checkpoint=checkpoint) == expected


def test_enrichment_equal_task_weight_with_unequal_and_zero_claim_pools() -> None:
    cfg = copy.deepcopy(load_config())
    cfg["statistics"]["bootstrap_resamples"] = 20
    cfg["selection"]["repetitions"] = 30
    one_claim = [SelectionCandidate("a", 0, 1, 0, True)]
    no_claims = [SelectionCandidate(str(i), 0, 0, 0, False) for i in range(3)]
    result = selection_bootstrap({"one": one_claim, "three": no_claims}, cfg, "A")
    assert result["by_n"][16]["Enrich"].estimate == 1.0
    mixed = [SelectionCandidate(str(i), 0, 1 if i == 0 else 0, 0, i == 0) for i in range(4)]
    all_claims = [SelectionCandidate("b", 0, 1, 0, True)]
    result = selection_bootstrap({"mixed": mixed, "all": all_claims}, cfg, "A")
    assert result["by_n"][16]["Enrich"].estimate == 1.6
    zero = selection_bootstrap({"zero1": no_claims, "zero2": no_claims[:1]}, cfg, "A")
    assert zero["by_n"][16]["Enrich"].estimate is None
    assert zero["by_n"][16]["Enrich"].n_valid_resamples == 0
