"""Isolated, owner-authorized WM-B engineering smoke run.

This module deliberately leaves the official smoke profile and its artifacts alone.
"""

import argparse
import hashlib
import json
import re
import shutil
import sqlite3
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from inert.audit import stage_log
from inert.conditions import condition_text
from inert.config import Config, Paths, load_config
from inert.decide import validity
from inert.harness import render_harness
from inert.inertness import check_channel_d, check_static
from inert.models import load_models, model_session, resolve_model
from inert.parse import parse_result
from inert.pipeline import ExecutionRecord, InertnessRecord
from inert.render import render_action, render_conversation, render_messages
from inert.schemas import (
    Candidate,
    Item,
    Score,
    Task,
    Thought,
    atomic_text,
    read_jsonl,
    write_json,
)
from inert.score import check_model_validity, score_items
from inert.stats import balanced_accuracy

RUN_NAME = "wm_b_engineering_smoke_20261114"
SOURCE_NAMES = ("tasks", "candidates", "executions", "thoughts", "items", "inertness")
CONDITIONS = (
    "T0",
    "NEU_A",
    "NEU_B",
    "NAT",
    "TRUE",
    "MIS_OUTCOME",
    "MIS_VERIFY",
    "MIS_PROPERTY",
    "MIS_AUTHORITY",
)


@dataclass(frozen=True)
class EngineeringPaths(Paths):
    @property
    def data(self) -> Path:
        return self.root / "data" / "smoke" / "diagnostics" / RUN_NAME

    @property
    def results(self) -> Path:
        return self.data / "results"


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def message_hash(item: Item) -> str:
    messages = [message.model_dump() for message in item.messages]
    return hashlib.sha256(
        json.dumps(messages, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


def engineering_config(paths: Paths) -> Config:
    config = load_config(paths)
    if config["smoke"]["models"] != ["wm_c"]:
        raise ValueError("Unexpected official smoke model configuration.")
    config["scoring_order"] = ["wm_b"]
    if (
        config["sampling"]["wm"]
        != {
            "temperature": 0.0,
            "top_p": 1.0,
            "max_tokens": 1024,
            "seed": 0,
        }
        or config["server"]["context_size"] != 8192
    ):
        raise ValueError("Frozen WM-B inference settings have changed.")
    if tuple(config["conditions"]) != CONDITIONS or config["channels"] != ["C", "D"]:
        raise ValueError("Frozen conditions or channels have changed.")
    return config


def historical_inventory(paths: EngineeringPaths) -> dict[str, str]:
    smoke = paths.root / "data" / "smoke"
    files = [
        path for path in smoke.rglob("*") if path.is_file() and not path.is_relative_to(paths.data)
    ]
    historical_results = paths.root / "results" / "pilot" / "smoke"
    if historical_results.exists():
        files += [path for path in historical_results.rglob("*") if path.is_file()]
    return {
        str(path.relative_to(paths.root)).replace("\\", "/"): digest(path) for path in sorted(files)
    }


def verify_historical_inventory(paths: EngineeringPaths) -> None:
    original = json.loads((paths.data / "historical_inventory.json").read_text(encoding="utf-8"))
    prospective_path = paths.data / "historical_inventory_prospective.json"
    if prospective_path.exists():
        incident = json.loads(
            (paths.data / "preservation_incident/incident.json").read_text(encoding="utf-8")
        )
        exception = incident["source"]
        saved = json.loads(prospective_path.read_text(encoding="utf-8"))
        if (
            incident["status"] != "HISTORICAL_PRESERVATION_EXCEPTION_ACCEPTED"
            or original.get(exception) != incident["expected_original_sha256"]
            or saved.get(exception) != incident["accepted_prospective_sha256"]
            or set(original) != set(saved)
            or any(original[name] != saved[name] for name in original if name != exception)
            or digest(paths.root / incident["byte_copy"]) != incident["accepted_prospective_sha256"]
        ):
            raise ValueError("Prospective inventory is not the approved one-file exception.")
    elif (paths.data / "preservation_incident/incident.json").exists():
        raise ValueError("Preservation incident exists without an accepted prospective baseline.")
    else:
        saved = original
    current = historical_inventory(paths)
    if current != saved:
        differences = sorted(set(current) ^ set(saved))
        differences += [
            name for name in current.keys() & saved.keys() if current[name] != saved[name]
        ]
        raise ValueError(f"Historical smoke artifacts changed: {differences[:10]}")


def accept_preservation_exception(paths: EngineeringPaths) -> None:
    original = json.loads((paths.data / "historical_inventory.json").read_text(encoding="utf-8"))
    incident = json.loads(
        (paths.data / "preservation_incident/incident.json").read_text(encoding="utf-8")
    )
    current = historical_inventory(paths)
    exception = incident["source"]
    changed = {
        name for name in original.keys() | current.keys() if original.get(name) != current.get(name)
    }
    if (
        changed != {exception}
        or original[exception] != incident["expected_original_sha256"]
        or current[exception] != incident["accepted_prospective_sha256"]
        or incident["sqlite_integrity"] != "ok"
    ):
        raise ValueError("Current history differs from the approved exception.")
    target = paths.data / "historical_inventory_prospective.json"
    if target.exists() and json.loads(target.read_text(encoding="utf-8")) != current:
        raise ValueError("Existing prospective baseline differs; do not overwrite it.")
    if not target.exists():
        write_json(target, current)
    verify_historical_inventory(paths)


def validate_dataset(
    paths: Paths, config: Config
) -> tuple[list[Task], list[Candidate], list[Item]]:
    tasks = read_jsonl(paths.tasks, Task)
    candidates = read_jsonl(paths.candidates, Candidate)
    executions = read_jsonl(paths.data / "executions.jsonl", ExecutionRecord)
    thoughts = read_jsonl(paths.thoughts, Thought)
    items = read_jsonl(paths.items, Item)
    checks = read_jsonl(paths.data / "inertness.jsonl", InertnessRecord)
    task_map = {task.task_id: task for task in tasks}
    cand_map = {cand.cand_id: cand for cand in candidates}
    execution_map = {row.cand_id: row for row in executions}
    thought_map = {row.cand_id: row.text for row in thoughts}
    check_map = {row.item_id: row for row in checks}
    if len(tasks) != 3 or len(task_map) != 3:
        raise ValueError("Expected exactly three distinct smoke tasks.")
    if (len(cand_map), len(execution_map), len(thought_map), len(check_map)) != (
        len(candidates),
        len(executions),
        len(thoughts),
        len(checks),
    ) or len({item.item_id for item in items}) != len(items):
        raise ValueError("Duplicate source record ID.")
    if any(cand.task_id not in task_map for cand in candidates):
        raise ValueError("Candidate references an unknown task.")
    if set(execution_map) != set(cand_map) or not set(thought_map) <= set(cand_map):
        raise ValueError("Execution or thought references do not match candidates.")
    for cand in candidates:
        task = task_map[cand.task_id]
        row = execution_map[cand.cand_id]
        harness = render_harness(task.tests, config["sandbox"]["test_seconds"])
        expected = hashlib.sha256((cand.code_stripped + harness).encode()).hexdigest()
        parsed = parse_result(row.stdout, task.n_tests)
        if (
            row.status != "ok"
            or row.source_sha256 != expected
            or parsed.parse_status != "ok"
            or cand.n_tests != task.n_tests
            or cand.n_passed != parsed.k_pred
            or cand.harness_output != row.stdout
            or cand.true_pass != parsed.pred_pass
        ):
            raise ValueError(f"Execution evidence mismatch: {cand.cand_id}")
    if len([cand for cand in candidates if cand.in_core_set]) != 11:
        raise ValueError("Core-set selection changed.")
    expected_checks = set()
    for item in items:
        task = task_map.get(item.task_id)
        cand = cand_map.get(item.cand_id)
        if task is None or cand is None or cand.task_id != item.task_id:
            raise ValueError(f"Bad item reference: {item.item_id}")
        if item.prompt_family != "vendored" or item.channel not in config["channels"]:
            raise ValueError(f"Unexpected renderer or channel: {item.item_id}")
        if item.block == "kt_ab" and (not cand.in_core_set or item.condition not in CONDITIONS):
            raise ValueError(f"Unexpected core assignment: {item.item_id}")
        expected_id = (
            f"{task.task_id}:{cand.cand_id}:{item.channel}:{item.condition}:{item.block}:vendored"
        )
        text = condition_text(
            config,
            item.condition,
            task.fn_name,
            cand.true_pass,
            item.channel,
            cand.natural_text,
            thought_map.get(cand.cand_id, ""),
        )
        if item.item_id != expected_id or item.text != text:
            raise ValueError(f"Condition text or ID mismatch: {item.item_id}")
        if item.messages != render_messages(
            task, cand, item.channel, item.condition, text, "vendored", paths
        ):
            raise ValueError(f"Rendered messages changed: {item.item_id}")
        if item.channel == "C":
            source, _ = render_action(task, cand, item.condition, text)
            check_static(source, cand.code_stripped)
            harness = render_harness(task.tests, config["sandbox"]["test_seconds"])
            expected_check = hashlib.sha256(
                (
                    source
                    + harness
                    + cand.harness_output
                    + json.dumps(config["sandbox"], sort_keys=True)
                ).encode()
            ).hexdigest()
            row = check_map.get(item.item_id)
            if row is None or row.status != "PASS" or row.check_sha256 != expected_check:
                raise ValueError(f"Inertness evidence mismatch: {item.item_id}")
            expected_checks.add(item.item_id)
        else:
            check_channel_d(
                render_conversation(task, cand, text), render_conversation(task, cand, "")
            )
    if set(check_map) != expected_checks:
        raise ValueError("Inertness records do not cover exactly the Channel-C items.")
    core_items = [item for item in items if item.block == "kt_ab"]
    actual = Counter((item.cand_id, item.channel, item.condition) for item in core_items)
    expected = Counter(
        (cand.cand_id, channel, condition)
        for cand in candidates
        if cand.in_core_set
        for channel in config["channels"]
        for condition in CONDITIONS
    )
    if actual != expected:
        raise ValueError("Core matrix is incomplete or duplicated.")
    return tasks, candidates, items


def prepare(paths: EngineeringPaths) -> dict[str, Any]:
    if (paths.data / "manifest.json").exists():
        return verify_manifest(paths)
    config = engineering_config(paths)
    inventory = historical_inventory(paths)
    source = Paths(paths.root, "smoke")
    tasks, candidates, items = validate_dataset(source, config)
    model = load_models(paths)["models"]["wm_b"]
    if (
        model["source"] != "Qwen/Qwen2.5-7B-Instruct"
        or model.get("quantization", "Q4_K_M") != "Q4_K_M"
    ):
        raise ValueError("Unexpected WM-B model identity or quantization.")
    resolved = resolve_model(paths, model, "Q4_K_M")
    if len(resolved.files) != 2:
        raise ValueError("Expected two pinned WM-B shards.")
    serving = load_models(paths)["serving"]
    executable = paths.root / serving["executable"]
    if serving["build"] != "b12110" or serving["commit"] != "cd959bae9":
        raise ValueError("Configured llama.cpp revision changed.")
    server_sha = digest(executable)
    paths.data.mkdir(parents=True, exist_ok=True)
    write_json(paths.data / "historical_inventory.json", inventory)
    source_hashes = {}
    for name in SOURCE_NAMES:
        old = source.data / f"{name}.jsonl"
        new = paths.data / f"{name}.jsonl"
        shutil.copyfile(old, new)
        if digest(old) != digest(new):
            raise ValueError(f"Copy mismatch: {name}")
        source_hashes[name] = digest(new)
    validate_dataset(paths, config)
    core = [item for item in items if item.block == "kt_ab"]
    manifest = {
        "kind": "wm_b_engineering_smoke",
        "starting_commit": "ce09ef20a56f3053ac51620011865a5bf1fd5486",
        "model": "Qwen/Qwen2.5-7B-Instruct",
        "quantization": "Q4_K_M",
        "model_shards": {
            str(path.relative_to(paths.root)).replace("\\", "/"): digest(path)
            for path in resolved.files
        },
        "model_identity": resolved.sha256,
        "server_build": serving["build"],
        "server_commit": serving["commit"],
        "server_sha256": server_sha,
        "server_args": [
            "--model",
            str(resolved.files[0]),
            "--host",
            config["server"]["host"],
            "--port",
            str(config["server"]["port"]),
            "--ctx-size",
            "8192",
            "--n-gpu-layers",
            str(model["n_gpu_layers"]),
            "--jinja",
            "--reasoning-format",
            "none",
        ],
        "sampling": config["sampling"]["wm"],
        "context_size": 8192,
        "source_hashes": source_hashes,
        "renderer_sha256": digest(paths.root / "src/inert/render.py"),
        "config_sha256": digest(paths.configs / "pilot.yaml"),
        "conditions": list(CONDITIONS),
        "channels": ["C", "D"],
        "tasks": [task.task_id for task in tasks],
        "planned_core_calls": len(core),
        "planned_optional_kt_c_calls": len(items) - len(core),
        "cases": [
            {
                "item_id": item.item_id,
                "task_id": item.task_id,
                "cand_id": item.cand_id,
                "channel": item.channel,
                "condition": item.condition,
                "block": item.block,
                "messages": [message.model_dump() for message in item.messages],
                "message_sha256": message_hash(item),
            }
            for item in items
        ],
    }
    write_json(paths.data / "manifest.json", manifest)
    atomic_text(paths.data / "manifest.sha256", digest(paths.data / "manifest.json") + "\n")
    write_json(
        paths.data / "evaluation_truth.json",
        {
            cand.cand_id: {
                "task_id": cand.task_id,
                "n_passed": cand.n_passed,
                "n_tests": cand.n_tests,
                "true_pass": cand.true_pass,
                "harness_output": cand.harness_output,
            }
            for cand in candidates
        },
    )
    verify_historical_inventory(paths)
    return manifest


def verify_manifest(paths: EngineeringPaths) -> dict[str, Any]:
    saved_hash = (paths.data / "manifest.sha256").read_text(encoding="utf-8").strip()
    if digest(paths.data / "manifest.json") != saved_hash:
        raise ValueError("Frozen manifest hash mismatch.")
    manifest = json.loads((paths.data / "manifest.json").read_text(encoding="utf-8"))
    config = engineering_config(paths)
    tasks, candidates, items = validate_dataset(paths, config)
    core = [item for item in items if item.block == "kt_ab"]
    if (
        len(tasks) != 3
        or sum(cand.in_core_set for cand in candidates) != 11
        or len(core) != 198
        or manifest["planned_core_calls"] != 198
        or manifest["tasks"] != [task.task_id for task in tasks]
        or manifest["conditions"] != list(CONDITIONS)
        or manifest["channels"] != ["C", "D"]
    ):
        raise ValueError("Frozen WM-B core matrix changed.")
    registry = load_models(paths)
    model = registry["models"]["wm_b"]
    resolved = resolve_model(paths, model, "Q4_K_M")
    current_shards = {
        str(path.relative_to(paths.root)).replace("\\", "/"): digest(path)
        for path in resolved.files
    }
    executable = paths.root / registry["serving"]["executable"]
    if (
        model["source"] != manifest["model"]
        or manifest["quantization"] != "Q4_K_M"
        or current_shards != manifest["model_shards"]
        or resolved.sha256 != manifest["model_identity"]
        or digest(executable) != manifest["server_sha256"]
        or registry["serving"]["build"] != manifest["server_build"]
        or registry["serving"]["commit"] != manifest["server_commit"]
    ):
        raise ValueError("Frozen model or server identity changed.")
    if manifest["sampling"] != config["sampling"]["wm"] or manifest["context_size"] != 8192:
        raise ValueError("Frozen inference configuration mismatch.")
    if manifest["renderer_sha256"] != digest(paths.root / "src/inert/render.py") or manifest[
        "config_sha256"
    ] != digest(paths.configs / "pilot.yaml"):
        raise ValueError("Official renderer or config changed.")
    if any(
        digest(paths.data / f"{name}.jsonl") != value
        for name, value in manifest["source_hashes"].items()
    ):
        raise ValueError("Frozen source record changed.")
    actual = {item.item_id: item for item in items}
    if len(manifest["cases"]) != len(actual):
        raise ValueError("Manifest case count changed.")
    for case in manifest["cases"]:
        item = actual.get(case["item_id"])
        if (
            item is None
            or item.task_id != case["task_id"]
            or item.cand_id != case["cand_id"]
            or item.channel != case["channel"]
            or item.condition != case["condition"]
            or item.block != case["block"]
            or case["message_sha256"] != message_hash(item)
            or case["messages"] != [message.model_dump() for message in item.messages]
        ):
            raise ValueError(f"Manifest message mismatch: {case['item_id']}")
    if len({case["item_id"] for case in manifest["cases"]}) != len(manifest["cases"]):
        raise ValueError("Duplicate manifest assignment.")
    verify_historical_inventory(paths)
    return manifest


def export_responses(paths: EngineeringPaths, manifest: dict[str, Any]) -> None:
    cache = paths.cache("wm_b")
    if not cache.exists():
        return
    cases_by_hash = {}
    for case in manifest["cases"]:
        cases_by_hash.setdefault(case["message_sha256"], []).append(case["item_id"])
    rows = []
    with sqlite3.connect(cache) as db:
        for key, request, response, completion in db.execute(
            "SELECT key, request, response, completion FROM calls ORDER BY rowid"
        ):
            identity = json.loads(request)
            messages = identity["messages"]
            msg_hash = hashlib.sha256(
                json.dumps(messages, sort_keys=True, ensure_ascii=False).encode()
            ).hexdigest()
            if msg_hash not in cases_by_hash:
                raise ValueError("Unmatched isolated WM-B cache request.")
            if (
                identity["model_file_sha256"] != manifest["model_identity"]
                or any(identity[key] != value for key, value in manifest["sampling"].items())
                or identity["server_flags_that_affect_output"]["server_sha256"]
                != manifest["server_sha256"]
            ):
                raise ValueError("Isolated cache request setting mismatch.")
            rows.append(
                {
                    "cache_key": key,
                    "item_ids": cases_by_hash[msg_hash],
                    "request": identity,
                    "raw_api_body": json.loads(response),
                    "completion": json.loads(completion),
                }
            )
    write_json(paths.data / "raw_responses.json", rows)


def run(paths: EngineeringPaths) -> None:
    manifest = verify_manifest(paths)
    config = engineering_config(paths)
    items = read_jsonl(paths.items, Item)
    core = [item for item in items if item.block == "kt_ab"]
    if len(core) != 198 or any(item.block != "kt_ab" for item in core):
        raise ValueError("Only the frozen 198 core items may be scored.")
    with stage_log(paths, "wm_b_engineering_smoke") as logger:
        try:
            with model_session(paths, config, "wm_b", quantization="Q4_K_M") as client:
                score_items(paths, config, "wm_b", core, client, logger)
            check_model_validity(paths, config, "wm_b", core)
        finally:
            export_responses(paths, manifest)
            verify_historical_inventory(paths)


def summarize(paths: EngineeringPaths) -> dict[str, Any]:
    manifest = verify_manifest(paths)
    items = {item.item_id: item for item in read_jsonl(paths.items, Item)}
    candidates = {cand.cand_id: cand for cand in read_jsonl(paths.candidates, Candidate)}
    scores = read_jsonl(paths.scores("wm_b"), Score)
    if len({score.item_id for score in scores}) != len(scores) or len(scores) > 198:
        raise ValueError("Duplicate engineering score.")
    raw_path = paths.data / "raw_responses.json"
    responses = json.loads(raw_path.read_text(encoding="utf-8")) if raw_path.exists() else []
    response_by_item = {item_id: row for row in responses for item_id in row["item_ids"]}
    failures = []
    summary: dict[str, Any] = {
        "manifest_sha256": digest(paths.data / "manifest.json"),
        "completed": len(scores),
        "new": sum(not s.cache_hit for s in scores),
        "cached": sum(s.cache_hit for s in scores),
        "planned_core": manifest["planned_core_calls"],
        "planned_optional": manifest["planned_optional_kt_c_calls"],
    }
    by_channel = {}
    for channel in ("C", "D"):
        group = [score for score in scores if items[score.item_id].channel == channel]
        core = [score for score in group if items[score.item_id].block == "kt_ab"]
        parsed = [score for score in group if score.parse_status == "ok"]
        t0 = [
            score
            for score in core
            if items[score.item_id].condition == "T0" and score.parse_status == "ok"
        ]
        ba = balanced_accuracy(
            [candidates[items[s.item_id].cand_id].true_pass for s in t0],
            [s.pred_pass for s in t0],
        )
        by_channel[channel] = {
            "completed": len(group),
            "parse_ok": len(parsed),
            "parse_fail": len(group) - len(parsed),
            "exact": sum(s.k_pred == candidates[items[s.item_id].cand_id].n_passed for s in parsed),
            "binary_correct": sum(
                s.pred_pass == candidates[items[s.item_id].cand_id].true_pass for s in parsed
            ),
            "t0_ba": ba,
            "t0_validity": validity(ba, engineering_config(paths)["thresholds"]),
            "t0_false_pass": sum(
                s.pred_pass for s in t0 if not candidates[items[s.item_id].cand_id].true_pass
            ),
            "t0_failing": sum(not candidates[items[s.item_id].cand_id].true_pass for s in t0),
            "by_condition": {
                condition: {
                    "completed": len(rows),
                    "parse_fail": sum(s.parse_status == "fail" for s in rows),
                }
                for condition in CONDITIONS
                if (rows := [s for s in core if items[s.item_id].condition == condition])
            },
        }
    for score in scores:
        item = items.get(score.item_id)
        if item is None or item.block != "kt_ab" or score.wm_id != "wm_b":
            raise ValueError("Score does not belong to frozen WM-B matrix.")
        response = response_by_item.get(score.item_id)
        if response is None or response["completion"]["raw_output"] != score.raw_output:
            raise ValueError("Missing or mismatched raw API response.")
        if score.parse_status == "fail":
            raw = score.raw_output
            failures.append(
                {
                    "item_id": score.item_id,
                    "channel": item.channel,
                    "condition": item.condition,
                    "raw_output": raw,
                    "expected_n": candidates[item.cand_id].n_tests,
                    "predicted_n": score.n_pred,
                    "missing_result": not bool(re.search(r"RESULT:\s*\d+\s*/\s*\d+", raw)),
                    "finish_reason": response["completion"]["finish_reason"],
                    "completion_tokens": score.completion_tokens,
                }
            )
    summary["channels"] = by_channel
    summary["parse_failures"] = len(failures)
    summary["wrong_denominators"] = sum(
        failure["predicted_n"] is not None and failure["predicted_n"] != failure["expected_n"]
        for failure in failures
    )
    summary["missing_results"] = sum(failure["missing_result"] for failure in failures)
    summary["length_finishes"] = sum(
        response_by_item[s.item_id]["completion"]["finish_reason"] == "length" for s in scores
    )
    summary["failures"] = failures
    write_json(paths.results / "engineering_summary.json", summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command", choices=("prepare", "accept-incident", "run", "summarize", "verify")
    )
    args = parser.parse_args()
    paths = EngineeringPaths(Paths.discover().root, "smoke")
    if args.command == "prepare":
        prepare(paths)
    elif args.command == "accept-incident":
        accept_preservation_exception(paths)
    elif args.command == "run":
        run(paths)
    elif args.command == "summarize":
        print(json.dumps(summarize(paths), ensure_ascii=False, indent=2))
    else:
        verify_manifest(paths)


if __name__ == "__main__":
    main()
