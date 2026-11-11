import logging
from pathlib import Path

import pytest

from inert.config import Paths, load_config
from inert.harness import render_harness
from inert.llm_client import Completion
from inert.proposer import Attempt, generate_candidates
from inert.sandbox import DockerSandbox
from inert.schemas import Candidate, read_jsonl, write_jsonl
from inert.tasks import normalize_mbpp, task_token_text, within_token_limit


def imported_row() -> dict:
    return {
        "task_id": 82,
        "prompt": "Return the square root.",
        "code": "import math\ndef f(x): return math.sqrt(x)",
        "test_imports": ["import math"],
        "test_list": ["assert f(4) == math.sqrt(4)", "assert f(9) == 3", "assert f(16) == 4"],
    }


def test_imports_preserve_assertions_and_count_toward_limit() -> None:
    row = imported_row()
    task = normalize_mbpp(row)
    for text, original in zip(task.tests, row["test_list"], strict=True):
        assert text == "import math\n" + original
    counted = []

    def counter(text: str) -> int:
        counted.append(text)
        return 1499

    assert within_token_limit(task, counter, 1500)
    assert counted == [task_token_text(task)]
    assert all(test in counted[0] for test in task.tests)
    assert task.prompt in counted[0] and task.reference_code in counted[0]
    assert not within_token_limit(task, lambda _: 1500, 1500)
    assert not within_token_limit(task, lambda _: 1501, 1500)
    assert load_config()["tokenizer"]["model"] == "Qwen/Qwen2.5-Coder-7B-Instruct"


@pytest.mark.docker
def test_import_dependent_reference_passes_inside_sandbox() -> None:
    task = normalize_mbpp(imported_row())
    result = DockerSandbox(Paths.discover(), load_config()["sandbox"]).run(
        task.reference_code, render_harness(task.tests)
    )
    assert result.stdout == "RESULT: 3/3\n"


def test_proposer_resume_after_candidate_checkpoint(tmp_path: Path) -> None:
    paths = Paths(tmp_path)
    paths.prompts.joinpath("inhouse").mkdir(parents=True)
    paths.prompts.joinpath("inhouse/proposer_code.txt").write_text(
        "System:\nCareful\n\nUser:\n{task_prompt}\n{first_test_assert}"
    )
    task = normalize_mbpp(imported_row())
    candidate = Candidate.from_source(
        f"{task.task_id}-g00", task.task_id, 0, "proposer", task.reference_code
    )
    write_jsonl(paths.candidates, [candidate], Candidate)
    cfg = load_config()
    cfg["candidates"]["per_task"] = 1

    class FixtureClient:
        def complete(self, messages: list, parameters: dict) -> Completion:
            return Completion(
                task.reference_code, 0.0, 1, True, "2026-11-11T00:00:00+00:00", "stop"
            )

    generate_candidates(paths, cfg, FixtureClient(), [task], logging.getLogger("test"))
    assert len(read_jsonl(paths.candidates, Candidate)) == 1
    attempts = read_jsonl(paths.data / "generation_attempts.jsonl", Attempt)
    assert len(attempts) == 1 and attempts[0].status == "accepted"
    assert attempts[0].cand_id == candidate.cand_id
    assert attempts[0].seed == 1000
