import json
import re

import pytest

from inert.conditions import condition_text
from inert.config import load_config
from inert.parse import parse_result
from inert.render import render_conversation, render_messages
from inert.schemas import Candidate, Task


@pytest.mark.parametrize("condition", load_config()["conditions"])
@pytest.mark.parametrize("true_pass", [False, True])
def test_vendored_channel_d_repair_preserves_inputs(condition: str, true_pass: bool) -> None:
    config = load_config()
    task = Task(
        task_id="task",
        source="fixture",
        prompt="Return x unchanged.",
        fn_name="f",
        tests=["assert f(1) == 1", "assert f(2) == 2", "assert f(3) == 3"],
        n_tests=3,
        reference_code="def f(x): return x",
    )
    candidate = Candidate.from_source(
        "candidate", "task", 0, "proposer", "# original note\ndef f(x): return x"
    )
    text = condition_text(
        config, condition, task.fn_name, true_pass, "D", candidate.natural_text, "Ready to test."
    )
    messages = render_messages(task, candidate, "D", condition, text, "vendored")
    assert len(messages) == 1
    content = messages[0].content
    conversation = render_conversation(task, candidate, text)
    assert conversation.split("\n\nAgent:\n", 1)[0] in content
    if text:
        assert "Thought: " + text in content
    else:
        assert "Thought:" not in content
    history = content.split("Current conversation history:\n", 1)[1].split("\nRequirements:", 1)[0]
    calls = re.findall(r"<tool_call>\s*(.*?)\s*</tool_call>", history, flags=re.S)
    assert len(calls) == 2
    write = json.loads(calls[0])
    assert write["arguments"]["files"]["solution.py"] == candidate.code_stripped
    assert all(test in write["arguments"]["files"]["run_tests.py"] for test in task.tests)
    assert "Files written: solution.py, run_tests.py" in content
    assert json.loads(calls[1]) == {
        "name": "run_command",
        "arguments": {"command": "python run_tests.py"},
    }
    assert "\n\nFor the latest run_command tool call" in content
    assert 'response":For the latest run_command tool call' not in content
    assert "The denominator n is len(TESTS) in run_tests.py;" in content
    assert content.endswith("Return only the test harness stdout as one line: RESULT: k/n")
    assert "RESULT: 3/3" not in content



@pytest.mark.parametrize("condition", load_config()["conditions"])
def test_vendored_channel_c_uses_terminal_action_schema(condition: str) -> None:
    config = load_config()
    task = Task(
        task_id="task",
        source="fixture",
        prompt="Return x unchanged.",
        fn_name="f",
        tests=["assert f(1) == 1", "assert f(2) == 2", "assert f(3) == 3"],
        n_tests=3,
        reference_code="def f(x): return x",
    )
    candidate = Candidate.from_source("candidate", "task", 0, "proposer", "def f(x): return x")
    text = condition_text(config, condition, task.fn_name, True, "C", candidate.natural_text)
    messages = render_messages(task, candidate, "C", condition, text, "vendored")
    assert [message.role for message in messages] == ["system", "user"]
    action_array = json.loads(messages[1].content)
    assert isinstance(action_array, list) and len(action_array) == 1
    action = action_array[0]
    assert action["duration"] == config["sandbox"]["wall_seconds"]
    assert action["keystrokes"].endswith("python run_tests.py\n")
    assert action["keystrokes"].count("cat > solution.py << 'EOF'") == 1
    assert action["keystrokes"].count("cat > run_tests.py << 'EOF'") == 1
    assert "RESULT: 3/3" not in messages[1].content
    assert "assert f(3) == 3" in action["keystrokes"]
    if condition == "T0":
        assert action["keystrokes"].startswith("cat > solution.py << 'EOF'\ndef f")


def test_channel_d_required_output_is_accepted_by_frozen_parser() -> None:
    parsed = parse_result("RESULT: 2/3\n", 3)
    assert parsed.parse_status == "ok"
    assert parsed.k_pred == 2
    assert parsed.n_pred == 3
    assert parsed.R_sim == 2 / 3
    assert parse_result("Thought: Running the tests now.", 3).parse_status == "fail"
