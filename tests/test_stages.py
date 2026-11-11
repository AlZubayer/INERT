import logging
import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner

from inert.cli import app
from inert.config import Paths, load_config
from inert.llm_client import Completion
from inert.pipeline import build_items, choose_core, execute_candidates
from inert.sandbox import DockerSandbox
from inert.schemas import Candidate, Item, Score, Task, read_jsonl, write_jsonl
from inert.score import check_model_validity, score_items


def project(tmp_path: Path) -> tuple[Paths, dict, list[Task], list[Candidate]]:
    paths = Paths(tmp_path)
    source = Paths.discover()
    shutil.copytree(source.configs, paths.configs)
    shutil.copytree(source.prompts, paths.prompts)
    (paths.root / "Pilot_Experimental_Design.md").write_text("test fixture root")
    task = Task(
        task_id="t1",
        source="handwritten_test_fixture",
        prompt="Identity",
        fn_name="f",
        tests=["assert f(0) == 0", "assert f(1) == 1", "assert f(-1) == -1"],
        n_tests=3,
        reference_code="def f(x): return x",
    )
    candidates = [
        Candidate.from_source(f"c{i}", "t1", i, "proposer", code)
        for i, code in enumerate(
            [
                "# identity\ndef f(x): return x",
                "# addition\ndef f(x): return x + 0",
                "# constant\ndef f(x): return 0",
                "# off by one\ndef f(x): return x + 1",
            ]
        )
    ]
    write_jsonl(paths.tasks, [task], Task)
    write_jsonl(paths.candidates, candidates, Candidate)
    return paths, load_config(paths), [task], candidates


@pytest.mark.docker
def test_execution_core_items_and_resume(tmp_path: Path) -> None:
    paths, config, tasks, _ = project(tmp_path)
    logger = logging.getLogger("stage-test")
    sandbox = DockerSandbox(paths, config["sandbox"])
    execute_candidates(paths, config, sandbox, logger)
    choose_core(paths, config, sandbox, logger)
    assert all(c.in_core_set for c in read_jsonl(paths.candidates, Candidate))
    # Thoughts are required when NAT has text. Supply explicit handwritten test fixtures.
    from inert.schemas import Thought

    write_jsonl(
        paths.thoughts,
        [
            Thought(cand_id=f"c{i}", text="Identity implementation.", seed=5000 + i)
            for i in range(4)
        ],
        Thought,
    )
    build_items(paths, config, sandbox, logger)
    items = read_jsonl(paths.items, Item)
    assert len([i for i in items if i.block == "kt_ab"]) == 4 * 9 * 2
    assert len([i for i in items if i.block == "kt_c_a"]) == 8
    assert len([i for i in items if i.block == "kt_c_b"]) == 8
    original = paths.items.read_bytes()
    execute_candidates(paths, config, sandbox, logger)
    build_items(paths, config, sandbox, logger)
    assert paths.items.read_bytes() == original


def test_scoring_resume_and_parse_failure_gate(tmp_path: Path) -> None:
    paths, config, _, candidates = project(tmp_path)
    from inert.schemas import Message

    items = [
        Item(
            item_id=f"i{i}",
            task_id="t1",
            cand_id=candidates[0].cand_id,
            channel="C",
            condition="T0",
            block="kt_ab",
            text="",
            messages=[Message(role="user", content=f"fixture {i}")],
            prompt_family="inhouse",
        )
        for i in range(4)
    ]

    class FixtureClient:
        def __init__(self) -> None:
            self.calls = 0

        def complete(self, messages: list, parameters: dict) -> Completion:
            self.calls += 1
            return Completion("RESULT: 2/3", 0.01, 5, False, "2026-11-11T00:00:00+00:00", "stop")

    client = FixtureClient()
    score_items(paths, config, "wm_c", items, client, logging.getLogger("score-test"))
    score_items(paths, config, "wm_c", items, client, logging.getLogger("score-test"))
    assert client.calls == 4
    scores = read_jsonl(paths.scores("wm_c"), Score)
    assert len(scores) == 4 and all(s.R_sim == 2 / 3 for s in scores)


def test_cli_commands_and_no_results_fabricated(tmp_path: Path) -> None:
    runner = CliRunner()
    help_result = runner.invoke(app, ["--help"])
    assert help_result.exit_code == 0
    for name in [
        "verify-env",
        "tasks",
        "propose",
        "execute",
        "core-set",
        "thoughts",
        "build-items",
        "p0",
        "score",
        "analyze",
        "report",
    ]:
        assert name in help_result.stdout
    paths, _, _, _ = project(tmp_path)
    result = runner.invoke(app, ["--root", str(tmp_path), "analyze"])
    assert result.exit_code != 0
    assert not paths.summary.exists()
    assert not paths.report.exists()


@pytest.mark.docker
def test_reference_added_without_natural_text(tmp_path: Path) -> None:
    paths, config, tasks, candidates = project(tmp_path)
    task = Task(
        **{**tasks[0].model_dump(), "reference_code": "# reference note\ndef f(x): return x"}
    )
    write_jsonl(paths.tasks, [task], Task)
    write_jsonl(paths.candidates, [candidates[-1]], Candidate)
    sandbox = DockerSandbox(paths, config["sandbox"])
    logger = logging.getLogger("reference-test")
    execute_candidates(paths, config, sandbox, logger)
    choose_core(paths, config, sandbox, logger)
    reference = next(c for c in read_jsonl(paths.candidates, Candidate) if c.origin == "reference")
    assert reference.true_pass and reference.in_core_set
    assert reference.natural_text == ""
    assert "# reference" not in reference.raw_source


@pytest.mark.parametrize(("failures", "should_stop"), [(20, False), (21, True)])
def test_first_200_parse_gate(tmp_path: Path, failures: int, should_stop: bool) -> None:
    from inert.audit import StopRequired
    from inert.schemas import Message

    paths, config, _, _ = project(tmp_path)
    items = [
        Item(
            item_id=f"i{i}",
            task_id="t1",
            cand_id=f"c{i}",
            channel="C",
            condition="T0",
            block="kt_ab",
            text="",
            messages=[Message(role="user", content=str(i))],
            prompt_family="inhouse",
        )
        for i in range(200)
    ]

    class FixtureClient:
        def __init__(self) -> None:
            self.calls = 0

        def complete(self, messages: list, parameters: dict) -> Completion:
            self.calls += 1
            return Completion(
                "bad" if self.calls <= failures else "RESULT: 3/3",
                0.001,
                5,
                False,
                "2026-11-11T00:00:00+00:00",
                "stop",
            )

    if should_stop:
        with pytest.raises(StopRequired, match="10%"):
            score_items(
                paths, config, "wm_c", items, FixtureClient(), logging.getLogger("gate-test")
            )
    else:
        score_items(paths, config, "wm_c", items, FixtureClient(), logging.getLogger("gate-test"))
    rows = read_jsonl(paths.scores("wm_c"), Score)
    assert len(rows) == 200
    assert sum(row.parse_status == "fail" for row in rows) == failures
    assert all(row.R_sim is None for row in rows if row.parse_status == "fail")


def test_all_invalid_cells_stop_with_evidence(tmp_path: Path) -> None:
    from test_analysis_report import records

    from inert.audit import StopRequired

    tasks, candidates, items, scores = records()
    paths = Paths(tmp_path)
    write_jsonl(paths.tasks, tasks, Task)
    write_jsonl(paths.candidates, candidates, Candidate)
    write_jsonl(paths.items, items, Item)
    wrong = [
        Score(**{**s.model_dump(), "k_pred": 3, "R_sim": 1.0, "pred_pass": True}) for s in scores
    ]
    write_jsonl(paths.scores("wm_b"), wrong, Score)
    cfg = load_config()
    cfg["channels"] = ["C"]
    with pytest.raises(StopRequired, match="INVALID"):
        check_model_validity(paths, cfg, "wm_b")
    assert (paths.results / "wm_b_validity.json").exists()
