import json
import re
from pathlib import Path

from inert.config import Paths
from inert.harness import render_harness
from inert.schemas import Candidate, Message, Task


def render_action(task: Task, candidate: Candidate, condition: str, text: str) -> tuple[str, str]:
    if condition == "NAT" and candidate.natural_text:
        source = candidate.raw_source
    else:
        prefix = "\n".join("# " + line for line in text.splitlines())
        source = (prefix + "\n" if prefix else "") + candidate.code_stripped
    harness = render_harness(task.tests)
    if "EOF" in source.splitlines() or "EOF" in harness.splitlines():
        raise ValueError("The fixed EOF heredoc delimiter appears in the source; stop for review.")
    action = (
        "cat > solution.py << 'EOF'\n" + source + "\nEOF\n"
        "cat > run_tests.py << 'EOF'\n" + harness.rstrip("\n") + "\nEOF\n"
        "python run_tests.py"
    )
    return source, action


def render_conversation(task: Task, candidate: Candidate, text: str) -> str:
    write = {
        "name": "write_files",
        "arguments": {
            "files": {
                "solution.py": candidate.code_stripped,
                "run_tests.py": render_harness(task.tests),
            }
        },
    }
    run = {"name": "run_command", "arguments": {"command": "python run_tests.py"}}
    thought = f"Thought: {text}\n" if text else ""
    return (
        "Agent:\n<tool_call>\n"
        + json.dumps(write, ensure_ascii=False)
        + "\n</tool_call>\n\nEnvironment:\nFiles written: solution.py, run_tests.py\n\n"
        + "Agent:\n"
        + thought
        + "<tool_call>\n"
        + json.dumps(run)
        + "\n</tool_call>\n\nEnvironment:"
    )


def _prompt(path: Path) -> str:
    # Provenance comments are metadata, never part of a model prompt.
    text = path.read_bytes().decode("utf-8")
    return re.sub(r"\A<!--.*?-->\s*", "", text, count=1, flags=re.S)


def _fill(template: str, values: dict[str, str]) -> str:
    # Replace known slots only; JSON braces in prompt text are literal data.
    return re.sub(r"\{([a-z_]+)\}", lambda m: values.get(m[1], m[0]), template)


def render_messages(
    task: Task,
    candidate: Candidate,
    channel: str,
    condition: str,
    text: str,
    family: str,
    paths: Paths | None = None,
) -> list[Message]:
    prompts = (paths or Paths.discover()).prompts
    if family not in ("vendored", "inhouse") or channel not in ("C", "D"):
        raise ValueError("Unknown prompt family or channel.")
    if channel == "C":
        _, action = render_action(task, candidate, condition, text)
        if family == "vendored":
            return [
                Message(role="system", content=_prompt(prompts / family / "wm_terminal.txt")),
                Message(role="user", content=action),
            ]
        values = {"action_block": action}
        template = _prompt(prompts / family / "wm_terminal.txt")
    else:
        conversation = render_conversation(task, candidate, text)
        if family == "vendored":
            prefix, latest = conversation.rsplit("\n\nAgent:\n", 1)
            latest = latest.removesuffix("\n\nEnvironment:")
            rules = _prompt(prompts / "inhouse" / "wm_tool.txt").split("\n\nUser:\n", 1)[0]
            rules = rules.removeprefix("System:\n")
            template = _prompt(prompts / family / "wm_tool.txt")
            content = _fill(
                template,
                {
                    "system_prompt": rules,
                    "reference_conversations": "",
                    "history": prefix,
                    "agent_message": latest,
                },
            )
            content += (
                "For the latest run_command tool call, simulate `python run_tests.py` using "
                "the solution.py and run_tests.py shown above. Count the passing tests from "
                "those files; the agent's Thought is not a test result.\n"
                "Do not echo the Thought, command, tool-call JSON, or an explanation.\n"
                "Return only the test harness stdout as one line: RESULT: k/n"
            )
            return [Message(role="user", content=content)]
        template = _prompt(prompts / family / "wm_tool.txt")
        # The conversation structure and JSON are supplied as one value to avoid brace formatting.
        system = template.split("\n\nUser:\n", 1)[0].removeprefix("System:\n")
        return [
            Message(role="system", content=system),
            Message(role="user", content="Conversation so far:\n\n" + conversation),
        ]
    system, user = _fill(template, values).split("\n\nUser:\n", 1)
    return [
        Message(role="system", content=system.removeprefix("System:\n")),
        Message(role="user", content=user.rstrip("\n")),
    ]
