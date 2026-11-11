import ast
import json
import re

from inert.sandbox import DockerSandbox
from inert.strip import strip_text


class InertnessError(RuntimeError):
    """A rendered action changed execution. Stop the stage."""


def check_static(rendered_source: str, code_stripped: str) -> None:
    try:
        same = ast.dump(ast.parse(strip_text(rendered_source))) == ast.dump(
            ast.parse(code_stripped)
        )
    except SyntaxError as exc:
        raise InertnessError("Rendered code is not valid Python.") from exc
    if not same:
        raise InertnessError("Static inertness check failed.")


def check_channel_d(rendered: str, baseline: str) -> None:
    def calls(value: str) -> list[dict]:
        return [
            json.loads(x) for x in re.findall(r"<tool_call>\s*(.*?)\s*</tool_call>", value, re.S)
        ]

    try:
        current, original = calls(rendered), calls(baseline)
    except ValueError as exc:
        raise InertnessError("Invalid tool-call JSON.") from exc
    if len(original) != 2 or current != original:
        raise InertnessError("Channel D tool calls changed.")


def check_dynamic(sandbox: DockerSandbox, rendered: str, harness: str, baseline: str) -> None:
    result = sandbox.run(rendered, harness)
    if result.stdout != baseline or result.returncode != 0:
        raise InertnessError("Dynamic inertness check failed.")
