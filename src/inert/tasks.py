import ast
import hashlib
import json
import logging
import random
import subprocess
from collections.abc import Callable
from typing import Any

from inert.audit import Progress
from inert.config import Config, Paths
from inert.harness import render_harness
from inert.models import load_models, resolve_model
from inert.sandbox import DockerSandbox
from inert.schemas import Task, read_jsonl, write_json, write_jsonl
from inert.verification import load_mbpp


def normalize_mbpp(row: dict[str, Any]) -> Task:
    imports = row.get("test_imports") or []
    assertions = row["test_list"]
    tests = ["\n".join([*imports, assertion]) for assertion in assertions]
    functions = {
        node.name
        for node in ast.parse(row["code"]).body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    names = [
        node.func.id
        for test in tests
        for node in ast.walk(ast.parse(test))
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in functions
    ]
    if not names:
        raise ValueError("No reference function is called by the test assertions.")
    return Task(
        task_id=f"mbpp-{row['task_id']}",
        source="google-research-datasets/mbpp:sanitized",
        prompt=row["prompt"],
        fn_name=names[0],
        tests=tests,
        n_tests=len(tests),
        reference_code=row["code"],
    )


def task_token_text(task: Task) -> str:
    return "\n".join([task.prompt, task.reference_code, *task.tests])


def within_token_limit(task: Task, count: Callable[[str], int], limit: int) -> bool:
    return count(task_token_text(task)) < limit


class CpuTokenizer:
    def __init__(self, paths: Paths, config: Config) -> None:
        registry = load_models(paths)
        role = config["tokenizer"]["role"]
        if registry["models"][role]["source"] != config["tokenizer"]["model"]:
            raise ValueError("Task tokenizer must be the approved code proposer.")
        self.model = resolve_model(paths, registry["models"][role], "Q4_K_M").files[0]
        server = paths.root / registry["serving"]["executable"]
        self.executable = server.with_name(
            "llama-tokenize.exe" if server.suffix == ".exe" else "llama-tokenize"
        )

    def __call__(self, text: str) -> int:
        result = subprocess.run(
            [
                str(self.executable),
                "--model",
                str(self.model),
                "--stdin",
                "--ids",
                "--no-bos",
                "--no-escape",
            ],
            input=text.encode(),
            capture_output=True,
            timeout=60,
        )
        if result.returncode:
            raise RuntimeError("CPU tokenizer failed: " + result.stderr.decode(errors="replace"))
        tokens = json.loads(result.stdout)
        if not isinstance(tokens, list) or any(type(x) is not int for x in tokens):
            raise ValueError("Invalid CPU tokenizer response.")
        return len(tokens)


def _needs_external_state(task: Task) -> bool:
    forbidden = {
        "os",
        "sys",
        "random",
        "socket",
        "requests",
        "httpx",
        "urllib",
        "pathlib",
        "subprocess",
        "shutil",
        "tempfile",
        "time",
        "datetime",
    }
    for source in [task.reference_code, *task.tests]:
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Import) and any(
                x.name.split(".")[0] in forbidden for x in node.names
            ):
                return True
            if isinstance(node, ast.ImportFrom) and (node.module or "").split(".")[0] in forbidden:
                return True
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id in {"open", "input", "__import__"}
            ):
                return True
    return False


def prepare_tasks(
    paths: Paths,
    config: Config,
    sandbox: DockerSandbox,
    count: Callable[[str], int],
    logger: logging.Logger,
) -> None:
    if paths.tasks.exists():
        read_jsonl(paths.tasks, Task)
        logger.info("Tasks already selected; retaining frozen sample.")
        return
    registry = load_models(paths)
    loaded = load_mbpp(paths, registry)
    source_rows = sorted(
        [row for split in loaded.values() for row in split], key=lambda row: row["task_id"]
    )
    kept, checks = [], []
    progress = Progress(len(source_rows))
    cache_path = paths.data / "task_filter.json"
    previous = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.exists() else {}
    for row in source_rows:
        task = normalize_mbpp(row)
        key = hashlib.sha256(
            (
                task.model_dump_json()
                + json.dumps(config["tasks"], sort_keys=True)
                + json.dumps(config["sandbox"], sort_keys=True)
                + config["tokenizer"]["model"]
            ).encode()
        ).hexdigest()
        record = previous.get(key)
        if record is None:
            reason = None
            if task.n_tests < 3:
                reason = "fewer_than_three_asserts"
            elif _needs_external_state(task):
                reason = "network_files_or_randomness"
            elif not within_token_limit(task, count, config["tasks"]["max_tokens"]):
                reason = "not_under_token_limit"
            output = None
            if reason is None:
                result = sandbox.run(task.reference_code, render_harness(task.tests))
                output = result.stdout
                if result.stdout != f"RESULT: {task.n_tests}/{task.n_tests}\n" or result.returncode:
                    reason = "reference_failed"
            record = {
                "task_id": task.task_id,
                "kept": reason is None,
                "reason": reason,
                "reference_stdout": output,
            }
            previous[key] = record
            write_json(cache_path, previous)
        checks.append(record)
        if record["kept"]:
            kept.append(task)
        progress.advance()
    n, reserve_n = config["tasks"]["count"], config["tasks"]["reserves"]
    if len(kept) < n + reserve_n:
        raise ValueError("Insufficient eligible tasks; do not change the sample size silently.")
    rng = random.Random(config["tasks"]["seed"])
    selected = rng.sample(kept, n)
    remaining = [task for task in kept if task.task_id not in {x.task_id for x in selected}]
    reserves = rng.sample(remaining, reserve_n)
    write_jsonl(paths.tasks, selected, Task)
    write_jsonl(paths.reserves, reserves, Task)
    write_json(
        paths.data / "task_selection.json",
        {
            "checks": checks,
            "task_ids": [t.task_id for t in selected],
            "reserve_ids": [t.task_id for t in reserves],
            "seed": config["tasks"]["seed"],
        },
    )
