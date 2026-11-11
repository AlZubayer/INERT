import hashlib
import json
import logging
import re

from inert.audit import Progress, StopRequired, record_deviation
from inert.conditions import condition_text
from inert.config import Config, Paths
from inert.harness import render_harness
from inert.inertness import InertnessError, check_channel_d, check_dynamic, check_static
from inert.mutate import mutants
from inert.parse import parse_result
from inert.render import render_action, render_conversation, render_messages
from inert.sandbox import DockerSandbox, SandboxError, SandboxSetupError
from inert.schemas import Candidate, Item, Record, Task, Thought, read_jsonl, write_jsonl
from inert.strip import strip_text


class ExecutionRecord(Record):
    cand_id: str
    source_sha256: str
    status: str
    stdout: str
    stderr: str
    load_ok: bool | None


class InertnessRecord(Record):
    item_id: str
    check_sha256: str
    status: str


def _truth(
    candidate: Candidate, task: Task, sandbox: DockerSandbox, seconds: int
) -> tuple[Candidate, ExecutionRecord]:
    harness = render_harness(task.tests, seconds)
    identity = hashlib.sha256((candidate.code_stripped + harness).encode()).hexdigest()
    result = sandbox.run(candidate.code_stripped, harness)
    parsed = parse_result(result.stdout, task.n_tests)
    if (
        result.returncode
        or parsed.parse_status != "ok"
        or not re.fullmatch(r"RESULT: \d+/\d+\n", result.stdout)
    ):
        return candidate, ExecutionRecord(
            cand_id=candidate.cand_id,
            source_sha256=identity,
            status="unusable_harness_output",
            stdout=result.stdout,
            stderr=result.stderr,
            load_ok=None,
        )
    load_ok = True
    if parsed.k_pred == 0:
        # A separate diagnostic identifies import-time failure.
        # The fixed task harness remains unchanged.
        probe = sandbox.run(candidate.code_stripped, render_harness(["assert True"], seconds))
        load_ok = probe.stdout == "RESULT: 1/1\n" and probe.returncode == 0
    data = candidate.model_dump()
    data.update(
        n_tests=task.n_tests,
        n_passed=parsed.k_pred,
        R_exec=parsed.R_sim,
        true_pass=parsed.pred_pass,
        harness_output=result.stdout,
    )
    return Candidate(**data), ExecutionRecord(
        cand_id=candidate.cand_id,
        source_sha256=identity,
        status="ok",
        stdout=result.stdout,
        stderr=result.stderr,
        load_ok=load_ok,
    )


def execute_candidates(
    paths: Paths, config: Config, sandbox: DockerSandbox, logger: logging.Logger
) -> None:
    tasks = {task.task_id: task for task in read_jsonl(paths.tasks, Task)}
    candidates = read_jsonl(paths.candidates, Candidate)
    records_path = paths.data / "executions.jsonl"
    records = read_jsonl(records_path, ExecutionRecord)
    done = {row.cand_id for row in records}
    progress = Progress(sum(c.task_id in tasks and c.cand_id not in done for c in candidates))
    for index, candidate in enumerate(candidates):
        if candidate.task_id not in tasks or candidate.cand_id in done:
            continue
        try:
            candidates[index], record = _truth(
                candidate, tasks[candidate.task_id], sandbox, config["sandbox"]["test_seconds"]
            )
        except SandboxError as exc:
            if isinstance(exc, SandboxSetupError):
                raise
            if "timed out" not in str(exc) and "output limit" not in str(exc):
                raise
            record = ExecutionRecord(
                cand_id=candidate.cand_id,
                source_sha256=candidate.code_sha256,
                status=str(exc),
                stdout="",
                stderr="",
                load_ok=None,
            )
            logger.info("Candidate execution unavailable: %s %s", candidate.cand_id, exc)
        records.append(record)
        write_jsonl(paths.candidates, candidates, Candidate)
        write_jsonl(records_path, records, ExecutionRecord)
        progress.advance()


def choose_core(
    paths: Paths, config: Config, sandbox: DockerSandbox, logger: logging.Logger
) -> None:
    tasks = read_jsonl(paths.tasks, Task)
    candidates = read_jsonl(paths.candidates, Candidate)
    executions_path = paths.data / "executions.jsonl"
    executions = read_jsonl(executions_path, ExecutionRecord)
    loads = {row.cand_id: row.load_ok for row in executions}
    selected: set[str] = set()
    for task in tasks:
        group = sorted(
            [c for c in candidates if c.task_id == task.task_id], key=lambda c: c.gen_index
        )
        passing = [c for c in group if c.true_pass is True]
        failing = [
            c
            for c in group
            if c.true_pass is False and (c.n_passed != 0 or loads.get(c.cand_id) is True)
        ]
        if len(passing) < config["candidates"]["core_passing"]:
            reference = Candidate.from_source(
                f"{task.task_id}-reference",
                task.task_id,
                config["candidates"]["per_task"],
                "reference",
                strip_text(task.reference_code),
            )
            if reference.code_sha256 not in {c.code_sha256 for c in group}:
                reference, execution = _truth(
                    reference, task, sandbox, config["sandbox"]["test_seconds"]
                )
                if reference.true_pass is not True:
                    raise StopRequired(
                        "Reference solution failed after task selection; inspect sandbox records."
                    )
                candidates.append(reference)
                executions.append(execution)
                passing.append(reference)
        if len(failing) < config["candidates"]["core_failing"] and passing:
            options = []
            for number, (operator, code) in enumerate(mutants(passing[0].code_stripped)):
                candidate = Candidate.from_source(
                    f"{task.task_id}-mutant-{operator}",
                    task.task_id,
                    config["candidates"]["per_task"] + 1 + number,
                    f"mutant:{operator}",
                    code,
                )
                if candidate.code_sha256 in {
                    c.code_sha256 for c in candidates if c.task_id == task.task_id
                }:
                    continue
                candidate, execution = _truth(
                    candidate, task, sandbox, config["sandbox"]["test_seconds"]
                )
                executions.append(execution)
                if candidate.true_pass is False and execution.load_ok:
                    options.append(candidate)
            # Preserve operator order within partial failures and complete failures.
            options.sort(key=lambda c: c.n_passed == 0)
            for candidate in options:
                if len(failing) >= config["candidates"]["core_failing"]:
                    break
                candidates.append(candidate)
                failing.append(candidate)
        if not passing or not failing:
            reserves = read_jsonl(paths.reserves, Task)
            if not reserves:
                raise StopRequired("No reserve tasks remain; do not change sample size silently.")
            replacement = reserves.pop(0)
            tasks = [replacement if t.task_id == task.task_id else t for t in tasks]
            write_jsonl(paths.tasks, tasks, Task)
            write_jsonl(paths.reserves, reserves, Task)
            from inert.schemas import write_json

            drops_path = paths.data / "task_drops.json"
            drops = json.loads(drops_path.read_text()) if drops_path.exists() else []
            drops.append(
                {
                    "task_id": task.task_id,
                    "replacement": replacement.task_id,
                    "reason": "Could not supply at least one passing and one failing candidate.",
                }
            )
            write_json(drops_path, drops)
            write_jsonl(paths.candidates, candidates, Candidate)
            write_jsonl(executions_path, executions, ExecutionRecord)
            raise StopRequired(
                "Reserve task activated. Rerun propose, execute, and core-set before continuing."
            )
        selected.update(c.cand_id for c in passing[: config["candidates"]["core_passing"]])
        selected.update(c.cand_id for c in failing[: config["candidates"]["core_failing"]])
    candidates = [
        Candidate(**{**c.model_dump(), "in_core_set": c.cand_id in selected}) for c in candidates
    ]
    write_jsonl(paths.candidates, candidates, Candidate)
    write_jsonl(executions_path, executions, ExecutionRecord)
    logger.info("Selected %s core candidates", len(selected))


def build_items(
    paths: Paths,
    config: Config,
    sandbox: DockerSandbox,
    logger: logging.Logger,
    family: str = "vendored",
) -> None:
    tasks = {task.task_id: task for task in read_jsonl(paths.tasks, Task)}
    candidates = [c for c in read_jsonl(paths.candidates, Candidate) if c.task_id in tasks]
    thoughts = {t.cand_id: t.text for t in read_jsonl(paths.thoughts, Thought)}
    checks_path = paths.data / "inertness.jsonl"
    existing_checks = read_jsonl(checks_path, InertnessRecord)
    checks = {record.item_id: record for record in existing_checks}
    checked = {record.check_sha256 for record in existing_checks if record.status == "PASS"}
    items: list[Item] = []
    plans = []
    for candidate in candidates:
        if candidate.true_pass is None:
            continue
        if candidate.in_core_set:
            plans.extend(
                (candidate, channel, condition, "kt_ab")
                for channel in config["channels"]
                for condition in config["conditions"]
            )
        if candidate.origin == "proposer":
            plans.extend(
                (candidate, "C", condition, block)
                for block, conditions in [
                    ("kt_c_a", ["NAT", "T0"]),
                    ("kt_c_b", ["NEU_A", "CLAIM_POS"]),
                ]
                for condition in conditions
            )
    progress = Progress(len(plans))
    for candidate, channel, condition, block in plans:
        task = tasks[candidate.task_id]
        if channel == "D" and candidate.natural_text and candidate.cand_id not in thoughts:
            raise ValueError("Natural thought is missing; run inert thoughts first.")
        text = condition_text(
            config,
            condition,
            task.fn_name,
            candidate.true_pass,
            channel,
            candidate.natural_text,
            thoughts.get(candidate.cand_id, ""),
        )
        item_id = f"{task.task_id}:{candidate.cand_id}:{channel}:{condition}:{block}:{family}"
        try:
            if channel == "C":
                source, _ = render_action(task, candidate, condition, text)
                check_static(source, candidate.code_stripped)
                harness = render_harness(task.tests, config["sandbox"]["test_seconds"])
                digest = hashlib.sha256(
                    (
                        source
                        + harness
                        + candidate.harness_output
                        + json.dumps(config["sandbox"], sort_keys=True)
                    ).encode()
                ).hexdigest()
                if candidate.in_core_set and digest not in checked:
                    check_dynamic(sandbox, source, harness, candidate.harness_output)
                    checked.add(digest)
                checks[item_id] = InertnessRecord(
                    item_id=item_id, check_sha256=digest, status="PASS"
                )
            else:
                check_channel_d(
                    render_conversation(task, candidate, text),
                    render_conversation(task, candidate, ""),
                )
        except InertnessError:
            record_deviation(
                paths,
                f"Inertness check failed for {item_id}. Stage stopped for repair.",
                scoring_started=any((paths.data / "scores").glob("*.jsonl")),
            )
            raise
        items.append(
            Item(
                item_id=item_id,
                task_id=task.task_id,
                cand_id=candidate.cand_id,
                channel=channel,
                condition=condition,
                block=block,
                text=text,
                messages=render_messages(task, candidate, channel, condition, text, family, paths),
                prompt_family=family,
            )
        )
        write_jsonl(checks_path, checks.values(), InertnessRecord)
        progress.advance()
    write_jsonl(paths.items, items, Item)
    logger.info("Rendered and checked %s items", len(items))
