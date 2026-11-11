import copy

from test_analysis_report import records

from inert.analyze import analyze_records
from inert.config import load_config
from inert.decide import kt_a
from inert.planning import model_items
from inert.schemas import Candidate, Item, Message, Task


def test_invalid_strong_cells_override_weak_effect() -> None:
    assert kt_a({"wm_a": ["INVALID"], "wm_b": ["INVALID"], "wm_c": ["EFFECT"]}) == "INCONCLUSIVE"


def test_missing_strong_cells_cannot_resolve_pass_tier() -> None:
    assert kt_a({"wm_a": ["UNAVAILABLE"], "wm_b": ["EFFECT"]}) == "UNAVAILABLE"
    assert kt_a({"wm_b": ["UNAVAILABLE"], "wm_c": ["EFFECT"]}) == "UNAVAILABLE"


def test_partial_cell_retains_endpoints_but_no_completed_verdict() -> None:
    cfg = copy.deepcopy(load_config())
    cfg["statistics"]["bootstrap_resamples"] = 10
    tasks, candidates, items, scores = records()
    result = analyze_records(
        tasks, candidates, items, scores[:-1], cfg, {"wm_a": "DROPPED", "wm_c": "DROPPED"}
    )
    assert result["cells"]["wm_b"]["C"]["status"] == "UNAVAILABLE"
    assert result["cells"]["wm_b"]["C"]["missing_scores"] == 1
    assert result["kt_a"] == "UNAVAILABLE"


def test_emergence_is_unavailable_before_selection_runs() -> None:
    tasks, candidates, items, _ = records()
    assert (
        analyze_records(tasks, candidates, items, [], load_config())["emergence"] == "UNAVAILABLE"
    )


def test_reduced_plan_applies_only_to_wm_a() -> None:
    config = load_config()
    tasks, candidates, items = [], [], []
    for n in range(50):
        task = Task(
            task_id=f"t{n}",
            source="fixture",
            prompt="Identity",
            fn_name="f",
            tests=["assert f(1) == 1"] * 3,
            n_tests=3,
            reference_code="def f(x): return x",
        )
        tasks.append(task)
        for k in range(16):
            candidate = Candidate.from_source(
                f"c{n}_{k}", task.task_id, k, "proposer", f"def f(x): return x + {k}"
            )
            candidates.append(candidate)
            for block, conditions, channels in [
                ("kt_ab", config["conditions"], config["channels"]),
                ("kt_c_b", ["CLAIM_POS", "NEU_A"], ["C"]),
            ]:
                for channel in channels:
                    for condition in conditions:
                        items.append(
                            Item(
                                item_id=f"{candidate.cand_id}_{block}_{channel}_{condition}",
                                task_id=task.task_id,
                                cand_id=candidate.cand_id,
                                channel=channel,
                                condition=condition,
                                block=block,
                                text="",
                                messages=[Message(role="user", content="fixture")],
                                prompt_family="inhouse",
                            )
                        )
    selected = model_items(items, tasks, candidates, config, "wm_a", "reduced")
    assert {i.task_id for i in selected} == {t.task_id for t in tasks[:30]}
    assert all(i.channel == "C" for i in selected)
    assert {i.condition for i in selected if i.block == "kt_ab"} == set(
        config["reduced"]["conditions"]
    )
    assert len({i.cand_id for i in selected if i.block == "kt_c_b" and i.task_id == "t0"}) == 8
    assert model_items(items, tasks, candidates, config, "wm_b", "reduced") == items
