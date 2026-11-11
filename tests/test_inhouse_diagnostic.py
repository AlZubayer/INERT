import json
import re

import pytest

from inert.conditions import condition_text
from inert.config import Paths, load_config
from inert.diagnostic_inhouse import DiagnosticPaths, classify_output, make_diagnostic_item
from inert.render import render_messages
from inert.schemas import Candidate, Item, Task


def test_diagnostic_paths_isolate_cache_and_items() -> None:
    root = Paths.discover().root
    diagnostic = DiagnosticPaths(root, "smoke")
    smoke = Paths(root, "smoke")
    assert diagnostic.data == root / "data/smoke/diagnostics/inhouse"
    assert diagnostic.cache("wm_c") != smoke.cache("wm_c")
    assert diagnostic.items != smoke.items
    assert diagnostic.server_lock == smoke.server_lock


@pytest.mark.parametrize("channel", ["C", "D"])
@pytest.mark.parametrize("condition", ["T0", "NEU_A", "NEU_B", "MIS_OUTCOME", "MIS_VERIFY"])
@pytest.mark.parametrize("passing", [False, True])
def test_inhouse_item_changes_only_prompt_family(
    channel: str, condition: str, passing: bool
) -> None:
    paths = Paths.discover()
    cfg = load_config(paths)
    task = Task(
        task_id="diagnostic-task",
        source="fixture",
        prompt="Return x.",
        fn_name="f",
        tests=["assert f(1) == 1", "assert f(2) == 2", "assert f(3) == 3"],
        n_tests=3,
        reference_code="def f(x): return x",
    )
    candidate = Candidate.from_source(
        "diagnostic-candidate", task.task_id, 0, "proposer", "# note\ndef f(x): return x"
    )
    thought = "Ready to run the tests."
    text = condition_text(
        cfg, condition, task.fn_name, passing, channel, candidate.natural_text, thought
    )
    original = Item(
        item_id=f"{task.task_id}:{candidate.cand_id}:{channel}:{condition}:kt_ab:vendored",
        task_id=task.task_id,
        cand_id=candidate.cand_id,
        channel=channel,
        condition=condition,
        block="kt_ab",
        text=text,
        messages=render_messages(task, candidate, channel, condition, text, "vendored", paths),
        prompt_family="vendored",
    )
    diagnostic = make_diagnostic_item(original, task, candidate, paths)
    assert diagnostic.item_id.endswith(":inhouse")
    assert diagnostic.model_dump(
        exclude={"item_id", "messages", "prompt_family"}
    ) == original.model_dump(exclude={"item_id", "messages", "prompt_family"})
    assert diagnostic.messages == render_messages(
        task, candidate, channel, condition, text, "inhouse", paths
    )
    content = "\n".join(m.content for m in diagnostic.messages)
    assert not re.search(r"RESULT:\s*\d+/\d+", content)
    if channel == "D":
        calls = re.findall(r"<tool_call>\s*(.*?)\s*</tool_call>", content, flags=re.S)
        assert len(calls) == 2
        write = json.loads(calls[0])
        assert write["arguments"]["files"]["solution.py"] == candidate.code_stripped
        assert all(test in write["arguments"]["files"]["run_tests.py"] for test in task.tests)
        assert ("Thought: " + text in content) if text else "Thought:" not in content
        assert (
            json.dumps({"name": "run_command", "arguments": {"command": "python run_tests.py"}})
            in content
        )
    else:
        assert candidate.code_stripped in content
        assert all(test in content for test in task.tests)
        assert "cat > solution.py << 'EOF'" in content
        assert "python run_tests.py" in content


def test_diagnostic_failure_categories_overlap_without_changing_parser() -> None:
    failure = classify_output(
        "cat: run_tests.py: No such file or directory\n" * 5,
        "fail",
        None,
        3,
        "length",
    )
    assert failure == {
        "no_result": True,
        "incorrect_denominator": False,
        "truncated": True,
        "repetitive": True,
        "missing_file_hallucination": True,
        "other_malformed": False,
    }
    mismatch = classify_output("RESULT: 0/10", "fail", 10, 3, "stop")
    assert mismatch["incorrect_denominator"]
    assert not mismatch["no_result"]
    assert not mismatch["truncated"]
    assert not any(classify_output("RESULT: 2/3", "ok", 3, 3, "stop").values())
