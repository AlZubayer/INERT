import copy
from pathlib import Path

from inert.analyze import analyze_records
from inert.config import Paths, load_config
from inert.report import write_report
from inert.schemas import Candidate, Item, Message, Score, Task


def records() -> tuple[list[Task], list[Candidate], list[Item], list[Score]]:
    tasks, candidates, items, scores = [], [], [], []
    for ti in range(3):
        task = Task(
            task_id=f"t{ti}",
            source="handwritten_test_fixture",
            prompt="Identity",
            fn_name="f",
            tests=["assert f(1) == 1"] * 3,
            n_tests=3,
            reference_code="def f(x): return x",
        )
        tasks.append(task)
        for ci, passing in enumerate([True, True, False, False]):
            source = f"# explanation\ndef f(x): return {'x' if passing else '0'}"
            cand = Candidate.from_source(f"c{ti}_{ci}", task.task_id, ci, "proposer", source)
            data = cand.model_dump()
            data.update(
                n_tests=3,
                n_passed=3 if passing else 0,
                R_exec=1.0 if passing else 0.0,
                true_pass=passing,
                harness_output=f"RESULT: {3 if passing else 0}/3\n",
                in_core_set=True,
            )
            cand = Candidate(**data)
            candidates.append(cand)
            for condition in load_config()["conditions"]:
                item = Item(
                    item_id=f"{cand.cand_id}_{condition}",
                    task_id=task.task_id,
                    cand_id=cand.cand_id,
                    channel="C",
                    condition=condition,
                    block="kt_ab",
                    text="",
                    messages=[Message(role="user", content="fixture")],
                    prompt_family="inhouse",
                )
                items.append(item)
                # T0 balanced accuracy = 0.75. MIS_OUTCOME changes failing predictions.
                predicted = passing or (ci == 2) or condition == "MIS_OUTCOME"
                scores.append(
                    Score(
                        item_id=item.item_id,
                        wm_id="wm_b",
                        raw_output=f"RESULT: {3 if predicted else 0}/3",
                        parse_status="ok",
                        k_pred=3 if predicted else 0,
                        n_pred=3,
                        R_sim=1.0 if predicted else 0.0,
                        pred_pass=predicted,
                        latency_s=0.01,
                        completion_tokens=5,
                        cache_hit=False,
                        timestamp="2026-11-11T00:00:00+00:00",
                    )
                )
    return tasks, candidates, items, scores


def test_paired_analysis_and_report_traceability(tmp_path: Path) -> None:
    cfg = copy.deepcopy(load_config())
    cfg["statistics"]["bootstrap_resamples"] = 50
    task_rows, candidates, items, scores = records()
    summary = analyze_records(
        task_rows,
        candidates,
        items,
        scores,
        cfg,
        model_status={"wm_a": "DROPPED", "wm_c": "DROPPED"},
    )
    cell = summary["cells"]["wm_b"]["C"]
    assert cell["baseline_ba"] == 0.75
    assert cell["effect"]["estimate"] == 0.5
    assert cell["misleading_change"]["estimate"] == 0.5
    assert cell["neutral_change"]["estimate"] == 0
    assert cell["effect"]["n_pairs"] == 6
    # A missing D cell prevents a completed pilot decision.
    assert summary["cells"]["wm_b"]["D"]["status"] == "UNAVAILABLE"
    paths = Paths(tmp_path)
    write_report(paths, summary, {"fixture": True}, items, scores)
    report = paths.report.read_text(encoding="utf-8")
    assert report.splitlines()[0] == summary["decision"]
    assert "P0: NOT_RUN" in report
    assert "UNAVAILABLE" in report
    assert "RESULT:" in report
    assert "c0_0_MIS_OUTCOME" in report
    assert scores[0].item_id in summary["source_item_ids"]
    assert summary["source_score_count"] == len(scores)


def test_parse_failures_drop_complete_pair_without_imputation() -> None:
    cfg = copy.deepcopy(load_config())
    cfg["statistics"]["bootstrap_resamples"] = 20
    tasks, candidates, items, scores = records()
    target = next(i for i, s in enumerate(scores) if s.item_id == "c0_3_MIS_OUTCOME")
    original = scores[target]
    scores[target] = Score(
        **{
            **original.model_dump(),
            "parse_status": "fail",
            "k_pred": None,
            "n_pred": None,
            "R_sim": None,
            "pred_pass": None,
            "raw_output": "bad",
        }
    )
    result = analyze_records(
        tasks, candidates, items, scores, cfg, model_status={"wm_a": "DROPPED", "wm_c": "DROPPED"}
    )
    cell = result["cells"]["wm_b"]["C"]
    assert cell["effect"]["n_pairs"] == 5
    assert cell["parse_failures"] == 1
    assert cell["effect"]["estimate"] == 0.4


def test_missing_scores_never_become_negative_results() -> None:
    tasks, candidates, items, _ = records()
    result = analyze_records(tasks, candidates, items, [], load_config())
    assert result["kt_a"] == "UNAVAILABLE"
    assert result["decision"].startswith("Unavailable")
