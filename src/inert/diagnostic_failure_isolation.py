"""Fixed, isolated A-F world-model failure diagnostic; never pilot scoring."""

import argparse
import hashlib
import json
import re
import sqlite3
import subprocess
from collections import defaultdict
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from inert.audit import Progress, stage_log
from inert.config import Paths, load_config
from inert.diagnostic_inhouse import classify_output
from inert.harness import render_harness
from inert.llm_client import CachedClient
from inert.models import load_models, model_session, resolve_model
from inert.parse import parse_result
from inert.render import render_messages
from inert.sandbox import DockerSandbox
from inert.schemas import Candidate, Item, Message, Record, Score, Task, read_jsonl, write_json
from inert.server import ModelServer

ROOT_NAME = "failure_isolation_20261112"
SELECTION = ["mbpp-440-g00", "mbpp-310-g00", "mbpp-440-g04", "mbpp-265-g01"]
CONDITIONS = ["T0", "NEU_A", "NEU_B", "MIS_OUTCOME", "MIS_VERIFY"]
TRUTH = {"mbpp-440-g00": 0, "mbpp-310-g00": 2, "mbpp-440-g04": 3, "mbpp-265-g01": 3}


@dataclass(frozen=True)
class FailurePaths(Paths):
    namespace: str = "main"

    @property
    def data(self) -> Path:
        return self.root / "data" / "smoke" / "diagnostics" / ROOT_NAME

    def cache(self, model: str) -> Path:
        if not re.fullmatch(r"[a-z0-9_]+", self.namespace):
            raise ValueError("Unsafe diagnostic namespace.")
        return self.data / "cache" / self.namespace / f"{model}.sqlite"

    def log_file(self, stage: str) -> Path:
        if stage == "server":
            stage = "server-" + self.namespace
        return super().log_file(stage)


class Case(Record):
    case_id: str
    stage: Literal["A", "B", "C", "D", "E", "F2"]
    model_role: Literal["wm_c", "wm_b"]
    family: Literal["vendored", "inhouse"] | None = None
    channel: Literal["C", "D"] | None = None
    task_id: str | None = None
    candidate_id: str | None = None
    condition: str | None = None
    representation: str | None = None
    expected_text: str | None = None
    expected_k: int | None = None
    expected_n: int | None = None
    source_code: str | None = None
    tests: list[str] | None = None
    messages: list[Message]
    input_sha256: str


class Response(Record):
    case_id: str
    input_sha256: str
    raw_output: str
    finish_reason: str | None
    prompt_tokens: int | None
    completion_tokens: int | None
    latency_s: float
    cache_hit: bool
    timestamp: str
    content_empty: bool
    reasoning_content_present: bool


def _hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _hash_file(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def input_hash(messages: list[Message]) -> str:
    payload = [message.model_dump() for message in messages]
    return _hash_bytes(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode())


def _case(case_id: str, stage: str, messages: list[Message], **fields: object) -> Case:
    return Case(
        case_id=case_id,
        stage=stage,
        model_role="wm_b" if stage == "E" else "wm_c",
        messages=messages,
        input_sha256=input_hash(messages),
        **fields,
    )


def a_cases() -> list[Case]:
    requests = [
        ("A1", "Reply with exactly READY.", "READY"),
        ("A2", "What is 1 + 1? Output only the integer.", "2"),
        ("A3", "Count the entries in [7, 8, 9]. Output only the integer.", "3"),
        ("A4", "Copy exactly this literal string and nothing else: RESULT: 1/3", "RESULT: 1/3"),
    ]
    output = []
    for identifier, request, expected in requests:
        user = Message(role="user", content=request)
        for structure, messages in (
            (
                "system_user",
                [Message(role="system", content="Reply with only the requested answer."), user],
            ),
            ("user_only", [user]),
        ):
            output.append(
                _case(
                    f"{identifier}-{structure}",
                    "A",
                    messages,
                    task_id=identifier,
                    representation=structure,
                    expected_text=expected,
                )
            )
    return output


def b_cases(tasks: dict[str, Task]) -> list[Case]:
    base = tasks["mbpp-440"].tests
    lists = [
        ("mbpp-440", base),
        ("mbpp-310", tasks["mbpp-310"].tests),
        ("mbpp-265", tasks["mbpp-265"].tests),
        ("mbpp-440-n2", base[:2]),
        ("mbpp-440-n4", [*base, "assert True"]),
    ]
    instruction = (
        "Count the entries in the TESTS list. Do not execute any test. "
        "Output only the integer count"
    )
    output = []
    for identifier, tests in lists:
        harness = render_harness(tests)
        representations = {
            "B1": "\n".join("- " + test for test in tests),
            "B2": "TESTS = " + repr(tests),
            "B3": harness,
            "B4": json.dumps(
                {"name": "write_files", "arguments": {"files": {"run_tests.py": harness}}},
                ensure_ascii=False,
            ),
        }
        for representation, value in representations.items():
            messages = [Message(role="user", content=instruction + "\n\n" + value)]
            output.append(
                _case(
                    f"B-{identifier}-{representation}",
                    "B",
                    messages,
                    task_id=identifier,
                    representation=representation,
                    expected_text=str(len(tests)),
                    expected_n=len(tests),
                    tests=tests,
                )
            )
    return output


def c_cases(paths: Paths) -> list[Case]:
    output = []
    for passed in range(4):
        identifier = f"C{passed}"
        tests = ["assert True"] * passed + ["assert False"] * (3 - passed)
        task = Task(
            task_id=identifier,
            source="synthetic-control",
            prompt="Run the supplied fixed assertions.",
            fn_name="f",
            tests=tests,
            n_tests=3,
            reference_code="def f(x): return x",
        )
        candidate = Candidate.from_source(
            identifier, identifier, 0, "reference", "def f(x): return x"
        )
        for channel in ("C", "D"):
            for family in ("vendored", "inhouse"):
                messages = render_messages(task, candidate, channel, "T0", "", family, paths)
                output.append(
                    _case(
                        f"C-{identifier}-{channel}-{family}",
                        "C",
                        messages,
                        family=family,
                        channel=channel,
                        task_id=identifier,
                        candidate_id=identifier,
                        condition="T0",
                        expected_k=passed,
                        expected_n=3,
                        source_code=candidate.code_stripped,
                        tests=tests,
                    )
                )
    return output


def classify_count(raw_output: str, expected: int) -> tuple[bool, int | None]:
    value = raw_output.strip()
    observed = int(value) if re.fullmatch(r"\d+", value) else None
    return observed == expected, observed


def _real_cases(paths: Paths, stage: Literal["D", "E"]) -> list[Case]:
    source = Paths(paths.root, "smoke")
    tasks = {task.task_id: task for task in read_jsonl(source.tasks, Task)}
    candidates = {
        candidate.cand_id: candidate for candidate in read_jsonl(source.candidates, Candidate)
    }
    vendored = {
        (item.cand_id, item.channel, item.condition): item
        for item in read_jsonl(source.items, Item)
        if item.block == "kt_ab" and item.prompt_family == "vendored"
    }
    previous_inhouse = {
        (item.cand_id, item.channel, item.condition): item
        for item in read_jsonl(paths.root / "data/smoke/diagnostics/inhouse/items.jsonl", Item)
    }
    output = []
    conditions = ["T0"] if stage == "D" else CONDITIONS
    for candidate_id in SELECTION:
        candidate = candidates[candidate_id]
        task = tasks[candidate.task_id]
        if task.n_tests != 3 or candidate.n_passed != TRUTH[candidate_id]:
            raise ValueError(f"Fixed data anchor changed: {candidate_id}")
        if not candidate.in_core_set or candidate.harness_output is None:
            raise ValueError(f"Missing Docker ground truth: {candidate_id}")
        for condition in conditions:
            for channel in ("C", "D"):
                original = vendored[(candidate_id, channel, condition)]
                for family in ("vendored", "inhouse"):
                    messages = render_messages(
                        task, candidate, channel, condition, original.text, family, source
                    )
                    if family == "vendored" and messages != original.messages:
                        raise ValueError("Current vendored renderer differs from smoke items.")
                    if family == "inhouse":
                        prior = previous_inhouse[(candidate_id, channel, condition)]
                        if prior.text != original.text or prior.messages != messages:
                            raise ValueError(
                                "Current in-house renderer differs from historical items."
                            )
                    output.append(
                        _case(
                            f"{stage}-{candidate_id}-{condition}-{channel}-{family}",
                            stage,
                            messages,
                            family=family,
                            channel=channel,
                            task_id=task.task_id,
                            candidate_id=candidate_id,
                            condition=condition,
                            expected_k=candidate.n_passed,
                            expected_n=task.n_tests,
                            source_code=candidate.code_stripped,
                            tests=task.tests,
                        )
                    )
    return output


def build_manifest(paths: FailurePaths) -> dict:
    source = Paths(paths.root, "smoke")
    selection_file = paths.root / "data/smoke/diagnostics/inhouse/selection.json"
    selection = json.loads(selection_file.read_text(encoding="utf-8"))
    if (
        selection.get("candidate_ids") != SELECTION
        or selection.get("conditions") != CONDITIONS
        or selection.get("model") != "wm_c"
    ):
        raise ValueError("Prior diagnostic selection differs from the protocol; stop.")
    tasks = {task.task_id: task for task in read_jsonl(source.tasks, Task)}
    if set(tasks) != {"mbpp-440", "mbpp-310", "mbpp-265"}:
        raise ValueError("The three smoke tasks changed.")
    if any(task.n_tests != 3 for task in tasks.values()):
        raise ValueError("A smoke task no longer has three tests.")
    cases = [*a_cases(), *b_cases(tasks), *c_cases(source)]
    d = _real_cases(paths, "D")
    e = _real_cases(paths, "E")
    cases.extend(d)
    cases.extend(e)
    for case in d:
        if case.family == "inhouse":
            cases.append(
                Case.model_validate(
                    {
                        **case.model_dump(),
                        "case_id": case.case_id.replace("D-", "F2-", 1),
                        "stage": "F2",
                    }
                )
            )
    counts = {
        stage: sum(case.stage == stage for case in cases)
        for stage in ("A", "B", "C", "D", "E", "F2")
    }
    if counts != {"A": 8, "B": 20, "C": 16, "D": 16, "E": 80, "F2": 8}:
        raise ValueError(f"Unexpected manifest counts: {counts}")
    if len({case.case_id for case in cases}) != len(cases):
        raise ValueError("Duplicate diagnostic case ID.")
    if any(case.input_sha256 != input_hash(case.messages) for case in cases):
        raise ValueError("Message hash mismatch.")
    config = load_config(source)
    sampling = config["sampling"]["wm"]
    if (
        sampling != {"temperature": 0.0, "top_p": 1.0, "max_tokens": 1024, "seed": 0}
        or config["server"]["context_size"] != 8192
    ):
        raise ValueError("Frozen WM sampling or context differs from protocol.")
    registry = load_models(paths)
    models = {}
    for role in ("wm_c", "wm_b"):
        model = registry["models"][role]
        resolved = resolve_model(paths, model, "Q4_K_M")
        models[role] = {
            "source": model["source"],
            "source_revision": model["source_revision"],
            "gguf_repository": model["gguf_repository"],
            "gguf_revision": model["gguf_revision"],
            "license": model["license"],
            "n_gpu_layers": model["n_gpu_layers"],
            "files": [
                {
                    "path": entry["path"],
                    "size_bytes": entry["size_bytes"],
                    "sha256": entry["sha256"],
                }
                for entry in model["files"]
                if "q4_k_m" in entry["filename"].lower()
            ],
            "resolved_identity": resolved.sha256,
        }
    source_paths = [
        paths.root / name
        for name in (
            "AGENTS.md",
            "Pilot_Experimental_Design.md",
            "Pilot_Next_Steps.md",
            "results/pilot/WM_Failure_Isolation_Protocol.md",
            "configs/models.yaml",
            "configs/pilot.yaml",
            "prompts/inhouse/wm_terminal.txt",
            "prompts/inhouse/wm_tool.txt",
            "prompts/vendored/wm_terminal.txt",
            "prompts/vendored/wm_tool.txt",
            "data/smoke/tasks.jsonl",
            "data/smoke/candidates.jsonl",
            "data/smoke/thoughts.jsonl",
            "data/smoke/items.jsonl",
            "data/smoke/diagnostics/inhouse/selection.json",
            "data/smoke/diagnostics/inhouse/items.jsonl",
            "data/smoke/diagnostics/inhouse/scores/wm_c.jsonl",
            "data/smoke/diagnostics/inhouse/analysis.json",
        )
    ]
    server_path = paths.root / registry["serving"]["executable"]
    source_paths.append(server_path)
    return {
        "protocol_base_commit": "b0097b75e0ab3c86fd224c330cb69a8090ebe694",
        "sampling": sampling,
        "context_size": 8192,
        "server": {
            "executable": str(server_path.relative_to(paths.root)),
            "sha256": _hash_file(server_path),
            "version": registry["serving"]["build"],
            "commit": registry["serving"]["commit"],
        },
        "models": models,
        "source_sha256": {
            str(path.relative_to(paths.root)).replace("\\", "/"): _hash_file(path)
            for path in source_paths
        },
        "counts": counts,
        "cases": [case.model_dump() for case in cases],
    }


def prepare(paths: FailurePaths) -> dict:
    manifest = build_manifest(paths)
    target = paths.data / "manifest.json"
    if target.exists():
        prior = json.loads(target.read_text(encoding="utf-8"))
        if prior != manifest:
            raise ValueError("Existing fixed manifest does not match source files or model hashes.")
    else:
        write_json(target, manifest)
    return manifest


def _response_path(paths: FailurePaths, case: Case) -> Path:
    if not re.fullmatch(r"[A-Za-z0-9_-]+", case.case_id):
        raise ValueError("Unsafe diagnostic case ID.")
    return paths.data / "responses" / case.stage / (case.case_id + ".json")


def _verify_synthetic_docker(paths: FailurePaths, cases: list[Case]) -> None:
    expected = {}
    sandbox = DockerSandbox(paths, load_config(paths)["sandbox"])
    for case in cases:
        if case.stage != "C":
            continue
        if case.task_id in expected:
            continue
        if case.source_code is None or case.tests is None:
            raise ValueError("Synthetic Docker input missing.")
        expected[case.task_id] = {
            "source_sha256": _hash_bytes(case.source_code.encode()),
            "harness_sha256": _hash_bytes(render_harness(case.tests).encode()),
            "stdout": f"RESULT: {case.expected_k}/{case.expected_n}\n",
        }
    truth_path = paths.data / "docker_truth.json"
    if truth_path.exists():
        if json.loads(truth_path.read_text(encoding="utf-8")) != expected:
            raise ValueError("Saved synthetic Docker truth differs from the fixed manifest.")
        return
    for case in cases:
        if case.stage != "C" or case.family != "inhouse" or case.channel != "C":
            continue
        result = sandbox.run(case.source_code, render_harness(case.tests), use_cache=False)
        if (
            result.returncode != 0
            or result.stderr
            or result.stdout != expected[case.task_id]["stdout"]
        ):
            raise ValueError(f"Synthetic Docker truth mismatch: {case.case_id}: {result}")
    write_json(truth_path, expected)


def _cached_api_body(client: CachedClient, case: Case, parameters: dict) -> dict:
    payload = {"messages": [message.model_dump() for message in case.messages], **parameters}
    identity = {
        "model_file_sha256": client.model_hash,
        "server_flags_that_affect_output": client.flags,
        **payload,
    }
    serialized = json.dumps(identity, sort_keys=True, ensure_ascii=False, allow_nan=False)
    key = _hash_bytes(serialized.encode())
    row = client.db.execute("SELECT response FROM calls WHERE key = ?", (key,)).fetchone()
    if row is None:
        raise ValueError("Completion missing from the isolated raw API cache.")
    return json.loads(row[0])


def _runtime_snapshot(paths: FailurePaths, client: CachedClient) -> None:
    path = paths.data / "runtime" / f"{paths.namespace}.json"
    if path.exists():
        return
    snapshot = {"server_flags": client.flags, "model_identity": client.model_hash}
    for endpoint in ("/props", "/slots"):
        try:
            response = client.http.get(endpoint, timeout=10)
            snapshot[endpoint] = {
                "status": response.status_code,
                "body": response.json() if response.status_code == 200 else response.text[:500],
            }
        except Exception as exc:
            snapshot[endpoint] = {"status": "NOT_OBSERVED", "reason": type(exc).__name__}
    write_json(path, snapshot)


@contextmanager
def _parallel_one_session(paths: FailurePaths, config: dict) -> Iterator[CachedClient]:
    registry = load_models(paths)
    model = registry["models"]["wm_c"]
    resolved = resolve_model(paths, model, "Q4_K_M")
    executable = paths.root / registry["serving"]["executable"]
    flags = {
        "context_size": config["server"]["context_size"],
        "gpu_layers": model["n_gpu_layers"],
        "jinja": True,
        "reasoning_format": "none",
        "server_sha256": _hash_file(executable),
        "parallel": 1,
    }
    args = [
        "--model",
        str(resolved.files[0]),
        "--host",
        config["server"]["host"],
        "--port",
        str(config["server"]["port"]),
        "--ctx-size",
        str(config["server"]["context_size"]),
        "--n-gpu-layers",
        str(model["n_gpu_layers"]),
        "--jinja",
        "--reasoning-format",
        "none",
        "--parallel",
        "1",
    ]
    server = ModelServer(paths, config["server"], [str(executable)], args)
    started = False

    def ensure_server() -> None:
        nonlocal started
        if not started:
            server.__enter__()
            started = True

    url = f"http://{config['server']['host']}:{config['server']['port']}"
    with CachedClient(
        paths.cache("wm_c"),
        url,
        resolved.sha256,
        flags,
        timeout=config["server"]["request_seconds"],
        on_miss=ensure_server,
    ) as client:
        try:
            yield client
        finally:
            if started:
                server.__exit__()


def run_stage(paths: FailurePaths, stage: Literal["A", "B", "C", "D", "E", "F2"]) -> None:
    manifest = prepare(paths)
    cases = [Case.model_validate(case) for case in manifest["cases"] if case["stage"] == stage]
    if stage == "C":
        _verify_synthetic_docker(paths, cases)
    pending = []
    for case in cases:
        file = _response_path(paths, case)
        if file.exists():
            response = Response.model_validate_json(file.read_text(encoding="utf-8"))
            if response.case_id != case.case_id or response.input_sha256 != case.input_sha256:
                raise ValueError("Existing response does not match the fixed manifest.")
        else:
            pending.append(case)
    progress = Progress(len(pending)) if pending else None
    config = load_config(paths)
    params = config["sampling"]["wm"]
    grouped: dict[str, list[Case]] = defaultdict(list)
    for case in pending:
        grouped[case.family or "control"].append(case)
    with stage_log(paths, "failure-isolation-" + stage.lower()) as logger:
        for family, group in grouped.items():
            namespace = f"{stage.lower()}_{family}"
            scoped = FailurePaths(paths.root, "smoke", namespace)
            session = (
                _parallel_one_session(scoped, config)
                if stage == "F2"
                else model_session(scoped, config, group[0].model_role)
            )
            with session as client:
                for case in group:
                    completion = client.complete(case.messages, params)
                    if not completion.cache_hit:
                        _runtime_snapshot(scoped, client)
                    body = _cached_api_body(client, case, params)
                    message = body["choices"][0]["message"]
                    record = Response(
                        case_id=case.case_id,
                        input_sha256=case.input_sha256,
                        raw_output=completion.raw_output,
                        finish_reason=completion.finish_reason,
                        prompt_tokens=body.get("usage", {}).get("prompt_tokens"),
                        completion_tokens=completion.completion_tokens,
                        latency_s=completion.latency_s,
                        cache_hit=completion.cache_hit,
                        timestamp=completion.timestamp,
                        content_empty=not bool(message.get("content")),
                        reasoning_content_present=bool(message.get("reasoning_content")),
                    )
                    write_json(_response_path(paths, case), record.model_dump())
                    logger.info(
                        "%s cache_hit=%s prompt_tokens=%s finish=%s",
                        case.case_id,
                        record.cache_hit,
                        record.prompt_tokens,
                        record.finish_reason,
                    )
                    progress.advance()
    print(
        f"{stage}: {len(cases) - len(pending)} existing, "
        f"{len(pending)} recorded; total {len(cases)}",
        flush=True,
    )


def inspect_runtime(paths: FailurePaths) -> dict:
    manifest = prepare(paths)
    executable = paths.root / manifest["server"]["executable"]
    version = subprocess.run(
        [str(executable), "--version"], capture_output=True, text=True, timeout=15
    )
    result = {
        "version_stdout": version.stdout,
        "version_stderr": version.stderr,
        "version_returncode": version.returncode,
        "sessions": {},
    }
    for namespace in (
        "a_control",
        "b_control",
        "c_vendored",
        "c_inhouse",
        "d_vendored",
        "d_inhouse",
        "e_vendored",
        "e_inhouse",
        "f2_inhouse",
    ):
        logs = sorted((paths.data / "logs").glob(f"server-{namespace}-*.log"))
        entry = {
            "log_path": None,
            "n_slots": None,
            "n_ctx_slot": None,
            "kv_unified": None,
            "truncated_requests": None,
            "props_path": None,
        }
        if logs:
            log = logs[-1]
            text = log.read_text(encoding="utf-8", errors="replace")
            entry["log_path"] = str(log.relative_to(paths.root)).replace("\\", "/")
            match = re.search(
                r"initializing, n_slots = (\d+), n_ctx_slot = (\d+), kv_unified = '([^']+)'", text
            )
            if match:
                entry["n_slots"] = int(match[1])
                entry["n_ctx_slot"] = int(match[2])
                entry["kv_unified"] = match[3]
            values = re.findall(r"stop processing: n_tokens = \d+, truncated = (\d+)", text)
            entry["truncated_requests"] = sum(value != "0" for value in values) if values else None
            entry["slot_release_count"] = len(values)
        props = paths.data / "runtime" / f"{namespace}.json"
        if props.exists():
            entry["props_path"] = str(props.relative_to(paths.root)).replace("\\", "/")
        result["sessions"][namespace] = entry
    write_json(paths.data / "runtime_inspection.json", result)
    return result


def _historical_rows(paths: FailurePaths, manifest: dict) -> dict[str, list[dict]]:
    source = Paths(paths.root, "smoke")
    old_base = paths.root / "data/smoke/diagnostics/inhouse"
    source_hashes = manifest["source_sha256"]
    for filename in ("items.jsonl", "scores/wm_c.jsonl", "analysis.json"):
        file = old_base / filename
        key = str(file.relative_to(paths.root)).replace("\\", "/")
        if _hash_file(file) != source_hashes[key]:
            raise ValueError("Historical in-house source changed after manifest creation.")
    old_items = {item.item_id: item for item in read_jsonl(old_base / "items.jsonl", Item)}
    old_scores = {
        score.item_id: score for score in read_jsonl(old_base / "scores/wm_c.jsonl", Score)
    }
    if len(old_scores) != 40:
        raise ValueError("Expected 40 historical WM-C in-house responses.")
    inhouse = []
    for item_id, score in old_scores.items():
        item = old_items[item_id]
        inhouse.append(
            {
                "key": (item.cand_id, item.channel, item.condition),
                "input_sha256": input_hash(item.messages),
                "raw_output": score.raw_output,
            }
        )
    vendored_items = {
        input_hash(item.messages): item
        for item in read_jsonl(source.items, Item)
        if item.block == "kt_ab" and item.prompt_family == "vendored"
    }
    vendored = []
    cache = source.cache("wm_c")
    with sqlite3.connect("file:" + cache.as_posix() + "?mode=ro", uri=True) as db:
        rows = db.execute("SELECT request, completion FROM calls").fetchall()
    for request_json, completion_json in rows:
        request = json.loads(request_json)
        messages = [Message.model_validate(message) for message in request["messages"]]
        prompt_hash = input_hash(messages)
        item = vendored_items.get(prompt_hash)
        if item is None:
            raise ValueError("Historical vendored response cannot be matched to a source item.")
        vendored.append(
            {
                "key": (item.cand_id, item.channel, item.condition),
                "input_sha256": prompt_hash,
                "raw_output": json.loads(completion_json)["raw_output"],
            }
        )
    if len(vendored) != 19:
        raise ValueError("Expected 19 historical vendored WM-C responses.")
    previous = json.loads((old_base / "analysis.json").read_text(encoding="utf-8"))
    for family, rows in (("inhouse", inhouse), ("vendored", vendored)):
        old = {
            (r["candidate_id"], r["channel"], r["condition"]): r
            for r in previous["rows"]
            if r["family"] == family
        }
        if len(old) != len(rows):
            raise ValueError("Historical analysis row count differs from raw records.")
        for row in rows:
            if old[row["key"]]["raw_output"] != row["raw_output"]:
                raise ValueError("Historical raw output differs from cached or scored source.")
    return {"inhouse": inhouse, "vendored": vendored}


def analyze(paths: FailurePaths) -> dict:
    manifest = prepare(paths)
    cases = [Case.model_validate(case) for case in manifest["cases"]]
    rows = []
    for case in cases:
        file = _response_path(paths, case)
        if not file.exists():
            continue
        response = Response.model_validate_json(file.read_text(encoding="utf-8"))
        if response.case_id != case.case_id or response.input_sha256 != case.input_sha256:
            raise ValueError("Response mismatch during analysis.")
        row = {
            "case_id": case.case_id,
            "stage": case.stage,
            "model_role": case.model_role,
            "family": case.family,
            "channel": case.channel,
            "task_id": case.task_id,
            "candidate_id": case.candidate_id,
            "condition": case.condition,
            "representation": case.representation,
            "input_sha256": case.input_sha256,
            "expected_text": case.expected_text,
            "expected_k": case.expected_k,
            "expected_n": case.expected_n,
            "raw_output": response.raw_output,
            "prompt_tokens": response.prompt_tokens,
            "completion_tokens": response.completion_tokens,
            "finish_reason": response.finish_reason,
            "cache_hit": response.cache_hit,
            "content_empty": response.content_empty,
            "reasoning_content_present": response.reasoning_content_present,
        }
        if case.stage == "A":
            row["format_ok"] = response.raw_output.strip() == case.expected_text
            row["strict_output_format"] = row["format_ok"]
        elif case.stage == "B":
            row["format_ok"], row["observed_integer"] = classify_count(
                response.raw_output, case.expected_n
            )
            row["strict_output_format"] = bool(re.fullmatch(r"\d+", response.raw_output.strip()))
            row["spurious_10"] = row["observed_integer"] == 10
        else:
            parsed = parse_result(response.raw_output, case.expected_n)
            matches = re.findall(r"RESULT:\s*(\d+)\s*/\s*(\d+)", response.raw_output)
            row["observed_final_result"] = "RESULT: " + "/".join(matches[-1]) if matches else None
            row["parse_status"] = parsed.parse_status
            row["k_pred"] = parsed.k_pred
            row["n_pred"] = parsed.n_pred
            row["format_ok"] = parsed.parse_status == "ok"
            row["strict_output_format"] = bool(
                re.fullmatch(r"RESULT:\s*\d+\s*/\s*\d+", response.raw_output.strip())
            )
            row["count_correct"] = parsed.parse_status == "ok" and parsed.k_pred == case.expected_k
            row["label_correct"] = parsed.parse_status == "ok" and parsed.pred_pass == (
                case.expected_k == case.expected_n
            )
            row["categories"] = classify_output(
                response.raw_output,
                parsed.parse_status,
                parsed.n_pred,
                case.expected_n,
                response.finish_reason,
            )
        rows.append(row)
    summary = {}
    for stage in ("A", "B", "C", "D", "E", "F2"):
        summary[stage] = {}
        group = [row for row in rows if row["stage"] == stage]
        summary[stage]["all"] = {
            "attempted": len(group),
            "format_ok": sum(row["format_ok"] for row in group),
            "strict_output_format": sum(row["strict_output_format"] for row in group),
        }
        for family in ("vendored", "inhouse"):
            for channel in ("C", "D"):
                cell = [
                    row for row in group if row["family"] == family and row["channel"] == channel
                ]
                if cell:
                    summary[stage][f"{family}_{channel}"] = {
                        "attempted": len(cell),
                        "format_ok": sum(row["format_ok"] for row in cell),
                        "strict_output_format": sum(row["strict_output_format"] for row in cell),
                        "count_correct_all": sum(row.get("count_correct", False) for row in cell),
                        "label_correct_all": sum(row.get("label_correct", False) for row in cell),
                        "categories": {
                            key: sum(row["categories"][key] for row in cell)
                            for key in cell[0]["categories"]
                        },
                    }
    historical = _historical_rows(paths, manifest)
    e_cases = [case for case in cases if case.stage == "E"]
    e_by_key = {
        (case.candidate_id, case.channel, case.condition, case.family): case for case in e_cases
    }
    pairs = {}
    historical_unmatched = {}
    for family in ("inhouse", "vendored"):
        key = f"wm_b_vs_historical_wm_c_{family}"
        paired = []
        unmatched = []
        for old in historical[family]:
            case = e_by_key.get((*old["key"], family))
            if case is None or case.input_sha256 != old["input_sha256"]:
                unmatched.append(
                    {
                        "key": list(old["key"]),
                        "reason": "outside fixed E matrix"
                        if case is None
                        else "prompt hash differs",
                    }
                )
                continue
            latest = next((row for row in rows if row["case_id"] == case.case_id), None)
            if latest is not None:
                paired.append(
                    {
                        "key": list(old["key"]),
                        "channel": old["key"][1],
                        "input_sha256": case.input_sha256,
                        "wm_b_case_id": case.case_id,
                        "wm_b_raw_output": latest["raw_output"],
                        "wm_c_raw_output": old["raw_output"],
                    }
                )
        pairs[key] = paired
        historical_unmatched[family] = unmatched
    paired_families = []
    for case in e_cases:
        if case.family != "vendored":
            continue
        other = e_by_key[(case.candidate_id, case.channel, case.condition, "inhouse")]
        first = next((row for row in rows if row["case_id"] == case.case_id), None)
        second = next((row for row in rows if row["case_id"] == other.case_id), None)
        if first is not None and second is not None:
            paired_families.append(
                {
                    "key": [case.candidate_id, case.channel, case.condition],
                    "channel": case.channel,
                    "vendored_case_id": case.case_id,
                    "inhouse_case_id": other.case_id,
                }
            )
    pairs["wm_b_vendored_vs_inhouse"] = paired_families
    result = {
        "manifest_sha256": _hash_file(paths.data / "manifest.json"),
        "summary": summary,
        "rows": rows,
        "pairs": pairs,
        "historical_unmatched": historical_unmatched,
    }
    write_json(paths.data / "analysis.json", result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "stage", choices=("prepare", "A", "B", "C", "D", "E", "F1", "F2", "analyze")
    )
    args = parser.parse_args()
    paths = FailurePaths(Paths.discover().root, "smoke")
    if args.stage == "prepare":
        manifest = prepare(paths)
        print(manifest["counts"])
    elif args.stage == "F1":
        inspect_runtime(paths)
    elif args.stage == "analyze":
        analyze(paths)
    else:
        run_stage(paths, args.stage)


if __name__ == "__main__":
    main()
