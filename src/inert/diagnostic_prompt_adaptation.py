"""Isolated prompt-adaptation diagnostic for the vendored channels; never pilot scoring.

Compares the current vendored message assembly with assemblies that follow the
upstream pipelines more closely. Text conditions, candidates, tests, sampling
parameters and the frozen parser are unchanged. Outputs stay under
``data/smoke/diagnostics/prompt_adaptation_20261113/``.
"""

import argparse
import hashlib
import json
import logging
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path

from inert.audit import Progress, stage_log
from inert.config import Paths, load_config
from inert.harness import render_harness
from inert.models import model_session
from inert.parse import parse_result
from inert.render import _fill, _prompt, render_messages
from inert.schemas import Candidate, Item, Message, Record, Task, read_jsonl, write_json
from inert.stats import balanced_accuracy

VARIANTS = ("C0", "C1", "C2", "D0", "D1", "D2")
INITIAL_STATE = "root@5c1e9a7d3b20:/app#"
OUTPUT_RULES = (
    "\n\n"
    "For the latest run_command tool call, simulate `python run_tests.py` using "
    "the solution.py and run_tests.py shown above. Count the passing tests from "
    "those files; the agent's Thought is not a test result.\n"
    "The denominator n is len(TESTS) in run_tests.py; count every test entry "
    "whether it passes or fails.\n"
    "Do not echo the Thought, command, tool-call JSON, or an explanation.\n"
    "Return only the test harness stdout as one line: RESULT: k/n"
)


@dataclass(frozen=True)
class DiagnosticPaths(Paths):
    @property
    def data(self) -> Path:
        return self.root / "data" / "smoke" / "diagnostics" / "prompt_adaptation_20261113"


class Case(Record):
    case_id: str
    variant: str
    task_id: str
    cand_id: str
    channel: str
    condition: str
    messages: list[Message]


class Response(Record):
    case_id: str
    model: str
    raw_output: str
    finish_reason: str | None
    completion_tokens: int | None
    latency_s: float
    cache_hit: bool
    timestamp: str


def multiline_harness(tests: list[str], seconds: int) -> str:
    """Same harness with one test string per line, as laid out in design section 6.6."""
    single = f"TESTS = {tests!r}\n"
    base = render_harness(tests, seconds)
    if base.count(single) != 1:
        raise ValueError("Unexpected harness layout.")
    listing = "TESTS = [\n" + "".join(f"    {test!r},\n" for test in tests) + "]\n"
    return base.replace(single, listing)


def _source(candidate: Candidate, condition: str, text: str) -> str:
    if condition == "NAT" and candidate.natural_text:
        return candidate.raw_source
    prefix = "\n".join("# " + line for line in text.splitlines())
    return (prefix + "\n" if prefix else "") + candidate.code_stripped


def render_c_upstream(
    task: Task,
    candidate: Candidate,
    condition: str,
    text: str,
    harness: str,
    paths: Paths,
    duration: float,
) -> list[Message]:
    action = (
        "cat > solution.py << 'EOF'\n" + _source(candidate, condition, text) + "\nEOF\n"
        "cat > run_tests.py << 'EOF'\n" + harness.rstrip("\n") + "\nEOF\n"
        "python run_tests.py\n"
    )
    payload = json.dumps(
        [{"keystrokes": action, "duration": duration}], indent=2, ensure_ascii=False
    )
    turn_template = _prompt(paths.prompts / "vendored" / "wm_terminal_turn.txt").replace(
        "\r\n", "\n"
    )
    user = _fill(
        turn_template,
        {"current_state": INITIAL_STATE, "action_json": payload},
    )
    return [
        Message(role="system", content=_prompt(paths.prompts / "vendored" / "wm_terminal.txt")),
        Message(role="user", content=user),
    ]


def render_d_upstream(candidate: Candidate, text: str, harness: str, paths: Paths) -> list[Message]:
    write = {
        "name": "write_files",
        "arguments": {"files": {"solution.py": candidate.code_stripped, "run_tests.py": harness}},
    }
    run = {"name": "run_command", "arguments": {"command": "python run_tests.py"}}
    # Role labels follow Simia's _format_history_for_prompt.
    history = (
        "Assistant: <tool_call>\n"
        + json.dumps(write, ensure_ascii=False)
        + "\n</tool_call>\n\nUser/Tool response: Files written: solution.py, run_tests.py"
    )
    latest = (
        (f"Thought: {text}\n" if text else "")
        + "<tool_call>\n"
        + json.dumps(run)
        + "\n</tool_call>"
    )
    rules = _prompt(paths.prompts / "inhouse" / "wm_tool.txt").split("\n\nUser:\n", 1)[0]
    content = _fill(
        _prompt(paths.prompts / "vendored" / "wm_tool.txt"),
        {
            "system_prompt": rules.removeprefix("System:\n"),
            "reference_conversations": "No reference conversation",
            "history": history,
            "agent_message": latest,
        },
    )
    return [Message(role="user", content=content + OUTPUT_RULES)]


def build_cases(paths: DiagnosticPaths) -> list[Case]:
    source = Paths(paths.root, "smoke")
    config = load_config(source)
    seconds = config["sandbox"]["test_seconds"]
    duration = config["sandbox"]["wall_seconds"]
    tasks = {task.task_id: task for task in read_jsonl(source.tasks, Task)}
    candidates = {c.cand_id: c for c in read_jsonl(source.candidates, Candidate)}
    cases: list[Case] = []
    for item in read_jsonl(source.items, Item):
        if item.block != "kt_ab" or item.prompt_family != "vendored":
            continue
        task, candidate = tasks[item.task_id], candidates[item.cand_id]
        single = render_harness(task.tests, seconds)
        multi = multiline_harness(task.tests, seconds)
        if item.channel == "C":
            rendered = {
                "C0": render_messages(
                    task, candidate, "C", item.condition, item.text, "vendored", source
                ),
                "C1": render_c_upstream(
                    task, candidate, item.condition, item.text, single, source, duration
                ),
                "C2": render_c_upstream(
                    task, candidate, item.condition, item.text, multi, source, duration
                ),
            }
            if rendered["C0"] != item.messages:
                raise ValueError("Current renderer no longer reproduces the smoke item.")
        else:
            current_d = render_messages(
                task, candidate, "D", item.condition, item.text, "vendored", source
            )
            if current_d != item.messages:
                raise ValueError("Current Channel-D renderer no longer reproduces the smoke item.")
            rendered = {
                "D0": item.messages,
                "D1": render_d_upstream(candidate, item.text, single, source),
                "D2": render_d_upstream(candidate, item.text, multi, source),
            }
        for variant, messages in rendered.items():
            cases.append(
                Case(
                    case_id=f"{item.cand_id}:{item.condition}:{variant}",
                    variant=variant,
                    task_id=item.task_id,
                    cand_id=item.cand_id,
                    channel=item.channel,
                    condition=item.condition,
                    messages=messages,
                )
            )
    if len({case.case_id for case in cases}) != len(cases):
        raise ValueError("Duplicate diagnostic case IDs.")
    return cases


def prepare(paths: DiagnosticPaths) -> list[Case]:
    cases = build_cases(paths)
    serialized = json.dumps([case.model_dump() for case in cases], sort_keys=True)
    manifest = {
        "protocol": "Vendored prompt-adaptation diagnostic (not pilot scoring)",
        "variants": {
            "C0": "current vendored Channel C assembly (bare compact JSON action)",
            "C1": "upstream AgentWorldBench user turn (state, fenced JSON, instruction suffix)",
            "C2": "C1 with one TESTS entry per line in run_tests.py",
            "D0": "current vendored Channel D assembly",
            "D1": "Simia history role labels and empty-reference placeholder",
            "D2": "D1 with one TESTS entry per line in run_tests.py",
        },
        "sampling": load_config(paths)["sampling"]["wm"],
        "context_size": load_config(paths)["server"]["context_size"],
        "case_count": len(cases),
        "cases_sha256": hashlib.sha256(serialized.encode()).hexdigest(),
    }
    manifest_path = paths.data / "manifest.json"
    cases_path = paths.data / "cases.json"
    if manifest_path.exists():
        if json.loads(manifest_path.read_text(encoding="utf-8")) != manifest:
            raise ValueError("Frozen diagnostic manifest differs from the rebuilt cases.")
        if not cases_path.exists() or json.loads(cases_path.read_text(encoding="utf-8")) != [
            case.model_dump() for case in cases
        ]:
            raise ValueError("Frozen diagnostic cases differ from the rebuilt cases.")
    else:
        if cases_path.exists():
            raise ValueError("Frozen diagnostic cases exist without their manifest.")
        write_json(manifest_path, manifest)
        write_json(cases_path, [case.model_dump() for case in cases])
    return cases


def _responses(paths: DiagnosticPaths, model: str) -> dict[str, Response]:
    path = paths.data / "responses" / f"{model}.json"
    if not path.exists():
        return {}
    rows = [Response.model_validate(row) for row in json.loads(path.read_text(encoding="utf-8"))]
    if len({row.case_id for row in rows}) != len(rows):
        raise ValueError(f"Duplicate diagnostic response IDs for {model}.")
    if any(row.model != model for row in rows):
        raise ValueError(f"Diagnostic response model differs from {model}.")
    return {row.case_id: row for row in rows}


def run(
    paths: DiagnosticPaths,
    model: str,
    variants: list[str],
    conditions: list[str] | None,
    logger: logging.Logger,
) -> None:
    config = load_config(paths)
    frozen = prepare(paths)
    selected_ids = {case.case_id for case in frozen}
    cases = [
        case
        for case in frozen
        if case.variant in variants and (conditions is None or case.condition in conditions)
    ]
    done = _responses(paths, model)
    if set(done) - selected_ids:
        raise ValueError("Diagnostic responses contain IDs outside the frozen manifest.")
    todo = [case for case in cases if case.case_id not in done]
    progress = Progress(len(todo), every=10)
    target = paths.data / "responses" / f"{model}.json"
    with model_session(paths, config, model) as client:
        for case in todo:
            completion = client.complete(case.messages, config["sampling"]["wm"])
            done[case.case_id] = Response(case_id=case.case_id, model=model, **asdict(completion))
            write_json(target, [row.model_dump() for row in done.values()])
            progress.advance()
    logger.info("Completed %s calls for %s", len(todo), model)


def analyze(paths: DiagnosticPaths, model: str) -> dict:
    source = Paths(paths.root, "smoke")
    tasks = {task.task_id: task for task in read_jsonl(source.tasks, Task)}
    candidates = {c.cand_id: c for c in read_jsonl(source.candidates, Candidate)}
    responses = _responses(paths, model)
    cases = prepare(paths)
    if set(responses) - {case.case_id for case in cases}:
        raise ValueError("Diagnostic responses contain IDs outside the frozen manifest.")
    summary: dict[str, dict] = {}
    rows = []
    for case in cases:
        response = responses.get(case.case_id)
        if response is None:
            continue
        candidate = candidates[case.cand_id]
        parsed = parse_result(response.raw_output, tasks[case.task_id].n_tests)
        rows.append(
            {
                "case_id": case.case_id,
                "variant": case.variant,
                "condition": case.condition,
                "cand_id": case.cand_id,
                "n_passed": candidate.n_passed,
                "true_pass": candidate.true_pass,
                "parse_status": parsed.parse_status,
                "k_pred": parsed.k_pred,
                "n_pred": parsed.n_pred,
                "pred_pass": parsed.pred_pass,
                "finish_reason": response.finish_reason,
                "completion_tokens": response.completion_tokens,
            }
        )
    for variant in VARIANTS:
        group = [row for row in rows if row["variant"] == variant]
        if not group:
            continue
        valid = [row for row in group if row["parse_status"] == "ok"]
        baseline = [row for row in valid if row["condition"] == "T0"]
        summary[variant] = {
            "calls": len(group),
            "parse_failures": len(group) - len(valid),
            "parse_failure_rate": (len(group) - len(valid)) / len(group),
            "truncated": sum(row["finish_reason"] == "length" for row in group),
            "wrong_denominator": sum(
                row["parse_status"] == "fail" and row["n_pred"] is not None for row in group
            ),
            "mean_completion_tokens": sum(row["completion_tokens"] or 0 for row in group)
            / len(group),
            "exact_count_correct": sum(row["k_pred"] == row["n_passed"] for row in valid),
            "pass_label_correct": sum(row["pred_pass"] == row["true_pass"] for row in valid),
            "predicted_k": dict(sorted(Counter(str(row["k_pred"]) for row in valid).items())),
            "t0_valid": len(baseline),
            "t0_balanced_accuracy": balanced_accuracy(
                [row["true_pass"] for row in baseline], [row["pred_pass"] for row in baseline]
            )
            if baseline
            else None,
        }
    result = {"model": model, "summary": summary, "rows": rows}
    write_json(paths.data / f"analysis_{model}.json", result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("prepare", "run", "analyze"))
    parser.add_argument("--model", choices=("wm_b", "wm_c"), default="wm_c")
    parser.add_argument("--variants", nargs="+", choices=VARIANTS, default=list(VARIANTS))
    parser.add_argument("--conditions", nargs="+", default=None)
    args = parser.parse_args()
    paths = DiagnosticPaths(Paths.discover().root, "smoke")
    with stage_log(paths, "prompt-adaptation-" + args.stage) as logger:
        if args.stage == "prepare":
            print(len(prepare(paths)), "cases frozen")
        elif args.stage == "run":
            run(paths, args.model, args.variants, args.conditions, logger)
        else:
            print(json.dumps(analyze(paths, args.model)["summary"], indent=1))


if __name__ == "__main__":
    main()
