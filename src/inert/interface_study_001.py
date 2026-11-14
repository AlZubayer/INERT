"""Prepare INERT-INTERFACE-001 inputs without inference or historical writes."""

import hashlib
import json
import random
import re
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import yaml

from inert.config import Paths
from inert.render import render_conversation, render_messages
from inert.schemas import Candidate, Message, Task, read_jsonl

STUDY = "INERT-INTERFACE-001"
SEED = 20261114
TASK_RE = re.compile(r"mbpp-\d+")
RESULT_RE = re.compile(r"RESULT:[ \t]*(-?\d+)[ \t]*/[ \t]*(-?\d+)")
TEMPLATES = (
    "interface_b_system.txt",
    "interface_b_channel_c.txt",
    "interface_b_channel_d.txt",
)


def canonical(value: Any) -> bytes:
    """Serialize a JSON value deterministically for a SHA-256 identity."""
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()


def sha(value: Any) -> str:
    """Hash canonical JSON data."""
    return hashlib.sha256(canonical(value)).hexdigest()


def file_sha(path: Path) -> str:
    """Hash a file without changing it."""
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def normalized_text_sha(path: Path) -> str:
    """Hash UTF-8 text after CRLF-to-LF normalization."""
    return hashlib.sha256(
        path.read_text(encoding="utf-8").replace("\r\n", "\n").encode()
    ).hexdigest()


def selected_tasks(exposed: set[str], eligible: list[str], count: int = 18) -> list[str]:
    """Sample task IDs without using model predictions or task outcomes."""
    available = sorted(set(eligible) - exposed)
    if len(available) < count:
        raise ValueError(f"Only {len(available)} unexposed eligible tasks; need {count}.")
    return random.Random(SEED).sample(available, count)


def _task_ids(value: str) -> set[str]:
    return set(TASK_RE.findall(value))


def exposure_registry(root: Path) -> dict[str, Any]:
    """Index completed world-model response archives by task and source path."""
    data = root / "data"
    found: dict[str, set[str]] = defaultdict(set)
    source_counts: dict[str, int] = defaultdict(int)

    def add(task_id: str, path: Path) -> None:
        relative = path.relative_to(root).as_posix()
        found[task_id].add(relative)
        source_counts[relative] += 1

    score_files = [
        data / "smoke/scores/wm_c.jsonl",
        data / "smoke/diagnostics/inhouse/scores/wm_c.jsonl",
        data / "smoke/diagnostics/wm_b_engineering_smoke_20261114/scores/wm_b.jsonl",
        *(data / "smoke/audit").rglob("wm_c.jsonl"),
    ]
    for path in score_files:
        if not path.is_file():
            raise ValueError(f"Expected response archive is missing: {path}")
        for line in path.read_text(encoding="utf-8").splitlines():
            for task_id in _task_ids(json.loads(line)["item_id"]):
                add(task_id, path)

    diagnostics = data / "smoke/diagnostics"
    synthetic_responses = 0
    for directory in diagnostics.rglob("responses"):
        if "assertion_candidate_acquisition_20261112" in directory.parts:
            continue  # A code proposer, not an outcome-predicting world model.
        for path in directory.rglob("*.json"):
            value = json.loads(path.read_text(encoding="utf-8"))
            records = value if isinstance(value, list) else [value]
            for record in records:
                identifier = " ".join(
                    str(record.get(key, "")) for key in ("case_id", "item_id", "cand_id")
                )
                task_ids = _task_ids(path.name + " " + identifier)
                if not task_ids:
                    synthetic_responses += 1
                for task_id in task_ids:
                    add(task_id, path)

    engineering_raw = diagnostics / "wm_b_engineering_smoke_20261114/raw_responses.json"
    for record in json.loads(engineering_raw.read_text(encoding="utf-8")):
        for item_id in record["item_ids"]:
            for task_id in _task_ids(item_id):
                add(task_id, engineering_raw)

    # Reconcile the original P0 cache against its frozen 100-assignment manifest.
    manifest = json.loads((data / "p0/selection_manifest.json").read_text(encoding="utf-8"))
    assignments = {row["message_sha256"]: row for row in manifest["assignments"]}
    p0_cache = data / "cache/wm_a.sqlite"
    with sqlite3.connect(f"file:{p0_cache.as_posix()}?mode=ro", uri=True) as db:
        db.execute("PRAGMA query_only=ON")
        if db.execute("PRAGMA integrity_check").fetchone() != ("ok",):
            raise ValueError("Original P0 cache failed integrity check.")
        rows = db.execute("SELECT request FROM calls").fetchall()
    if len(rows) != 62:
        raise ValueError("Original P0 cache no longer has 62 responses.")
    for (request,) in rows:
        message_hash = sha(json.loads(request)["messages"])
        if message_hash not in assignments:
            raise ValueError("Original P0 response is absent from its frozen manifest.")
        add(assignments[message_hash]["task_id"], p0_cache)

    replay_cache = data / "p0/telemetry_recovery_20261114/replay.sqlite"
    with sqlite3.connect(f"file:{replay_cache.as_posix()}?mode=ro", uri=True) as db:
        db.execute("PRAGMA query_only=ON")
        replay_rows = db.execute("SELECT request FROM calls").fetchall()
    if len(replay_rows) != 1:
        raise ValueError("P0 replay cache is not a single response.")
    replay_hash = sha(json.loads(replay_rows[0][0])["messages"])
    if replay_hash not in assignments:
        raise ValueError("P0 replay is absent from the frozen manifest.")
    add(assignments[replay_hash]["task_id"], replay_cache)

    # The active and most recent archived smoke caches include responses that
    # were cached but not yet persisted to score JSONL when scoring stopped.
    for base in (
        data / "smoke",
        data / "smoke/audit/prompt_format_before_rerun_20261111T204010Z",
    ):
        cache = base / ("cache/wm_c.sqlite" if base.name == "smoke" else "wm_c.sqlite")
        items = base / "items.jsonl"
        by_message = {
            sha(row["messages"]): row["task_id"]
            for row in map(json.loads, items.read_text(encoding="utf-8").splitlines())
        }
        with sqlite3.connect(f"file:{cache.as_posix()}?mode=ro", uri=True) as db:
            db.execute("PRAGMA query_only=ON")
            cache_rows = db.execute("SELECT request FROM calls").fetchall()
        for (request,) in cache_rows:
            message_hash = sha(json.loads(request)["messages"])
            if message_hash not in by_message:
                raise ValueError(f"Unmapped WM-C smoke cache request: {cache}")
            add(by_message[message_hash], cache)

    return {
        "scope": "completed world-model predictions; proposer generation excluded",
        "task_sources": {task: sorted(paths) for task, paths in sorted(found.items())},
        "source_response_counts": dict(sorted(source_counts.items())),
        "synthetic_response_records_without_mbpp_id": synthetic_responses,
        "exposed_task_count": len(found),
    }


def choose_pair(
    task: Task, candidates: list[Candidate], executions: dict[str, Any]
) -> tuple[Candidate, Candidate]:
    """Choose the first Docker-verified core passing and failing candidates."""
    pool = sorted(
        (
            candidate
            for candidate in candidates
            if candidate.task_id == task.task_id and candidate.in_core_set
        ),
        key=lambda candidate: (candidate.gen_index, candidate.cand_id),
    )
    valid: list[Candidate] = []
    for candidate in pool:
        execution = executions.get(candidate.cand_id)
        if (
            candidate.n_tests != task.n_tests
            or candidate.n_passed is None
            or candidate.true_pass is None
            or candidate.harness_output != f"RESULT: {candidate.n_passed}/{task.n_tests}\n"
            or execution is None
            or execution["status"] != "ok"
            or execution["stdout"] != candidate.harness_output
            or not execution["load_ok"]
        ):
            continue
        valid.append(candidate)
    passing = next((candidate for candidate in valid if candidate.true_pass), None)
    failing = next((candidate for candidate in valid if not candidate.true_pass), None)
    if passing is None or failing is None:
        raise ValueError(f"Task {task.task_id} lacks a Docker-verified core pair.")
    return passing, failing


def finalized_result(raw: str, finish_reason: str | None, n_tests: int) -> tuple[str, int | None]:
    """Study-only final-answer metric; does not change the pilot parser."""
    if finish_reason != "stop":
        return "truncated_or_unfinished", None
    if raw.count("<think>") != raw.count("</think>") or raw.count("<think>") > 1:
        return "unclosed_or_multiple_think", None
    visible = re.sub(r"<think>.*?</think>", "", raw, flags=re.S)
    matches = list(RESULT_RE.finditer(visible))
    if not matches:
        if RESULT_RE.search(raw):
            return "result_only_in_reasoning", None
        return ("malformed_result" if "RESULT:" in visible else "missing_result"), None
    if len(matches) != 1:
        return "multiple_results", None
    match = matches[0]
    before = visible[: match.start()]
    after = visible[match.end() :]
    if before.rsplit("\n", 1)[-1].strip():
        return "result_not_standalone", None
    if after.split("\n", 1)[0].strip():
        return "result_not_standalone", None
    trailer = after.strip()
    if trailer and not re.fullmatch(r"[^\s\n]+@[^\s\n]+:[^\n]*[#$]", trailer):
        return "not_final", None
    k, n = int(match.group(1)), int(match.group(2))
    if n != n_tests:
        return "wrong_denominator", None
    if k < 0 or k > n:
        return "out_of_range", None
    return "ok", k


def _template(path: Path) -> str:
    return path.read_text(encoding="utf-8").replace("\r\n", "\n")


def render_b(task: Task, candidate: Candidate, channel: str, paths: Paths) -> list[Message]:
    """Render the one frozen explicit interface with channel-specific payloads."""
    directory = paths.prompts / "interface_study_001"
    system = _template(directory / TEMPLATES[0]).rstrip("\n")
    if channel == "C":
        baseline = render_messages(task, candidate, "C", "T0", "", "vendored", paths)
        action_json = baseline[1].content
        user = _template(directory / TEMPLATES[1]).replace("{action_json}", action_json)
    elif channel == "D":
        conversation = render_conversation(task, candidate, "")
        user = _template(directory / TEMPLATES[2]).replace("{conversation}", conversation)
    else:
        raise ValueError("Unknown study channel.")
    user = user.replace("{n_tests}", str(task.n_tests)).rstrip("\n")
    return [Message(role="system", content=system), Message(role="user", content=user)]


def build(root: Path, protocol_path: Path | None = None) -> dict[str, Any]:
    """Prepare deterministic study records; keep truth outside model messages."""
    paths = Paths(root)
    tasks = read_jsonl(paths.tasks, Task)
    candidates = read_jsonl(paths.candidates, Candidate)
    execution_rows = [
        json.loads(line)
        for line in (paths.data / "executions.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    executions = {row["cand_id"]: row for row in execution_rows}
    execution_counts = Counter(row["cand_id"] for row in execution_rows)
    official = tasks[:50]
    by_task = {task.task_id: task for task in official}
    p0 = json.loads(paths.p0_manifest.read_text(encoding="utf-8"))
    registry = exposure_registry(root)
    exposed = set(registry["task_sources"])
    development = p0["task_ids"][:6]
    if len(development) != 6 or not set(development) <= exposed:
        raise ValueError("Development tasks are not six previously exposed P0 tasks.")
    eligible = []
    pairs = {}
    for task in official:
        try:
            pairs[task.task_id] = choose_pair(task, candidates, executions)
        except ValueError:
            continue
        eligible.append(task.task_id)
    if any(task not in eligible for task in development):
        raise ValueError("A development task lacks a verified passing/failing pair.")
    heldout = selected_tasks(exposed, eligible)
    if set(development) & set(heldout):
        raise ValueError("Development and held-out tasks overlap.")
    selected = development + heldout
    if any(
        execution_counts[candidate.cand_id] != 1
        for task_id in selected
        for candidate in pairs[task_id]
    ):
        raise ValueError("A selected candidate has ambiguous Docker execution records.")
    template_hashes = {
        name: hashlib.sha256(
            _template(paths.prompts / "interface_study_001" / name).encode()
        ).hexdigest()
        for name in TEMPLATES
    }
    source_hashes = {
        name: file_sha(paths.data / f"{name}.jsonl")
        for name in ("tasks", "candidates", "executions", "items")
    }
    source_hashes["p0_manifest"] = file_sha(paths.p0_manifest)
    source_hashes["official_renderer"] = file_sha(root / "src/inert/render.py")
    source_hashes["official_parser"] = file_sha(root / "src/inert/parse.py")
    source_hashes["study_preparation_code"] = file_sha(Path(__file__))
    source_hashes["pilot_config"] = file_sha(paths.configs / "pilot.yaml")
    source_hashes["model_registry"] = file_sha(paths.configs / "models.yaml")
    for name in ("wm_terminal.txt", "wm_tool.txt"):
        source_hashes[f"vendored_{name}"] = file_sha(paths.prompts / "vendored" / name)
    study_dir = paths.data / "interface_study_001"
    split = {
        "selection_seed": SEED,
        "development_task_ids": development,
        "heldout_task_ids": heldout,
        "eligible_unexposed_count": len(set(eligible) - exposed),
        "excluded_exposed_official_task_ids": sorted(set(by_task) & exposed),
        "selected_candidate_ids": {
            task_id: sorted(candidate.cand_id for candidate in pairs[task_id])
            for task_id in selected
        },
    }
    if protocol_path is None or not protocol_path.is_file():
        return {"registry": registry, "split": split, "template_hashes": template_hashes}
    model_registry = yaml.safe_load((paths.configs / "models.yaml").read_text(encoding="utf-8"))
    wm_b = model_registry["models"]["wm_b"]
    for entry in wm_b["files"]:
        if file_sha(root / entry["path"]) != entry["sha256"]:
            raise ValueError("WM-B local shard differs from the pinned model registry.")
    executable = root / model_registry["serving"]["executable"]
    server_sha = file_sha(executable)
    if server_sha != "00d50686815af38249d0218c91558fbd0e9093ac8c074bac86196907f4305e31":
        raise ValueError("Local llama-server binary differs from the archived WM-B study.")
    engineering = json.loads(
        (paths.data / "smoke/diagnostics/wm_b_engineering_smoke_20261114/manifest.json").read_text(
            encoding="utf-8"
        )
    )
    engineering_cache = (
        paths.data / "smoke/diagnostics/wm_b_engineering_smoke_20261114/cache/wm_b.sqlite"
    )
    with sqlite3.connect(f"file:{engineering_cache.as_posix()}?mode=ro", uri=True) as db:
        db.execute("PRAGMA query_only=ON")
        request_row = db.execute("SELECT request FROM calls LIMIT 1").fetchone()
    if request_row is None:
        raise ValueError("Archived WM-B engineering cache has no request identity.")
    request_identity = json.loads(request_row[0])
    if request_identity["model_file_sha256"] != engineering["model_identity"]:
        raise ValueError("Archived WM-B model identity disagrees with its manifest.")
    model = {
        "source": wm_b["source"],
        "source_revision": wm_b["source_revision"],
        "gguf_revision": wm_b["gguf_revision"],
        "quantization": "Q4_K_M",
        "shards": [{"path": row["path"], "sha256": row["sha256"]} for row in wm_b["files"]],
        "model_identity": engineering["model_identity"],
        "server_binary_sha256": server_sha,
        "server_build": model_registry["serving"]["build"],
        "server_commit": model_registry["serving"]["commit"],
        "server_args": engineering["server_args"],
        "server_flags_that_affect_output": request_identity["server_flags_that_affect_output"],
        "context_size": 8192,
        "sampling": {"temperature": 0.0, "top_p": 1.0, "max_tokens": 1024, "seed": 0},
    }
    original_items = {}
    for line in paths.items.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        if row["task_id"] in selected and row["condition"] == "T0" and row["block"] == "kt_ab":
            original_items[row["item_id"]] = row
    assignments = {"development": [], "heldout": []}
    truth: dict[str, Any] = {}
    for stage, task_ids in (("development", development), ("heldout", heldout)):
        for task_id in task_ids:
            task = by_task[task_id]
            for label, candidate in zip(("passing", "failing"), pairs[task_id], strict=True):
                truth[candidate.cand_id] = {
                    "task_id": task_id,
                    "n_tests": task.n_tests,
                    "n_passed": candidate.n_passed,
                    "true_pass": candidate.true_pass,
                    "harness_output": candidate.harness_output,
                    "code_sha256": candidate.code_sha256,
                    "source_sha256": executions[candidate.cand_id]["source_sha256"],
                    "selection_label": label,
                }
                for interface in ("A", "B"):
                    for channel in ("C", "D"):
                        messages = (
                            render_messages(task, candidate, channel, "T0", "", "vendored", paths)
                            if interface == "A"
                            else render_b(task, candidate, channel, paths)
                        )
                        message_values = [message.model_dump() for message in messages]
                        if RESULT_RE.search("\n".join(message.content for message in messages)):
                            raise ValueError("Model-facing messages contain a numeric RESULT line.")
                        if interface == "A":
                            item_id = f"{task_id}:{candidate.cand_id}:{channel}:T0:kt_ab:vendored"
                            if (
                                item_id not in original_items
                                or original_items[item_id]["messages"] != message_values
                            ):
                                raise ValueError(
                                    "Interface A differs from frozen official T0 messages."
                                )
                        assignment_id = (
                            f"is001:{stage}:{task_id}:{candidate.cand_id}:{interface}:{channel}"
                        )
                        assignment = {
                            "assignment_id": assignment_id,
                            "task_id": task_id,
                            "candidate_id": candidate.cand_id,
                            "candidate_code_sha256": candidate.code_sha256,
                            "test_assertions_sha256": sha(task.tests),
                            "n_tests": task.n_tests,
                            "interface": interface,
                            "channel": channel,
                            "messages": message_values,
                            "message_sha256": sha(message_values),
                        }
                        assignments[stage].append(assignment)
        random.Random(SEED + (stage == "heldout")).shuffle(assignments[stage])
    combined = assignments["development"] + assignments["heldout"]
    if len(combined) != 192 or len({a["assignment_id"] for a in combined}) != 192:
        raise ValueError("Study assignment count or identity is wrong.")
    if len({a["message_sha256"] for a in combined}) != 192:
        raise ValueError("Study has an unexpected duplicate model-facing prompt.")
    manifest = {
        "study_id": STUDY,
        "protocol_version": "1.0.0",
        "prepared_date": "2026-11-14",
        "status": "PROTOCOL_LOCKED_PENDING_OWNER_APPROVAL",
        "base_commit": "5226cf42df389d7611d7f0320d7b01bbe49cd649",
        "protocol_sha256": normalized_text_sha(protocol_path),
        "analysis_plan_version": "1.0.0",
        "exposure_registry_sha256": sha(registry),
        "task_split_sha256": sha(split),
        "template_sha256": template_hashes,
        "source_file_sha256": source_hashes,
        "model": model,
        "assignment_order": (
            "development first, heldout only after separate owner unlock; "
            "within phase seed-shuffled"
        ),
        "assignments": combined,
    }
    manifest["manifest_sha256"] = sha(manifest)
    truth_record = {
        "study_id": STUDY,
        "source_file_sha256": source_hashes,
        "candidate_truth": truth,
    }
    truth_record["evaluation_truth_sha256"] = sha(truth_record)
    if len(truth) != 48:
        raise ValueError("Selected candidate truth records are not unique.")
    for name, value in (
        ("exposure_registry.json", registry),
        ("task_split.json", split),
        ("evaluation_truth.json", truth_record),
        ("manifest.json", manifest),
    ):
        path = study_dir / name
        content = json.dumps(value, indent=2, ensure_ascii=False) + "\n"
        if path.exists() and path.read_text(encoding="utf-8") != content:
            raise ValueError(f"Frozen study artifact differs on rerun: {path}")
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_text(content, encoding="utf-8", newline="\n")
    return {"registry": registry, "split": split, "manifest": manifest, "truth": truth_record}


def main() -> None:
    """Create only the ignored prospective manifest after the protocol exists."""
    root = Path(__file__).resolve().parents[2]
    protocol = root / "results/pilot/INERT_Interface_Study_Protocol_20261114.md"
    result = build(root, protocol)
    print(
        json.dumps(
            {
                "status": result["manifest"]["status"]
                if "manifest" in result
                else "DRAFT_SPLIT_ONLY",
                "exposed_tasks": result["registry"]["exposed_task_count"],
                "excluded_official": len(result["split"]["excluded_exposed_official_task_ids"]),
                "heldout_eligible": result["split"]["eligible_unexposed_count"],
                "manifest_sha256": result.get("manifest", {}).get("manifest_sha256"),
            }
        )
    )


if __name__ == "__main__":
    main()
