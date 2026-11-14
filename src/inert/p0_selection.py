"""Owner-approved, deterministic P0 sample and frozen manifest."""

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from inert.audit import StopRequired
from inert.config import Config, Paths
from inert.models import load_models, resolve_model
from inert.schemas import Candidate, Item, Task, read_jsonl, write_json

ALGORITHM = "balanced-p0-12x8-plus-4-v1"


def _hash_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()


def _file_hash(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def select_p0_items(
    tasks: list[Task], candidates: list[Candidate], items: list[Item], config: Config
) -> tuple[dict[str, Task], list[Item]]:
    n_tasks = config["p0"]["tasks"]
    n_calls = config["p0"]["calls"]
    selected_tasks = tasks[:n_tasks]
    task_map = {task.task_id: task for task in selected_tasks}
    if len(selected_tasks) != n_tasks or len(task_map) != n_tasks:
        raise StopRequired("P0 requires 12 distinct ready pilot tasks.")
    if config["channels"] != ["C", "D"] or len(config["conditions"]) != 9:
        raise StopRequired("P0 selection requires the frozen two channels and nine conditions.")
    slots, extras = divmod(n_calls, n_tasks)
    if slots != 8 or extras != 4:
        raise StopRequired("P0 selection requires the registered 100 calls across 12 tasks.")
    index: dict[tuple[str, str, str, str], Item] = {}
    for item in items:
        if item.block != "kt_ab":
            continue
        key = (item.task_id, item.cand_id, item.channel, item.condition)
        if key in index:
            raise StopRequired(f"Duplicate KT-A/KT-B item combination: {key}.")
        index[key] = item
    chosen: list[Item] = []
    for i, task in enumerate(selected_tasks):
        core = sorted(
            [c for c in candidates if c.task_id == task.task_id and c.in_core_set],
            key=lambda c: (c.gen_index, c.cand_id),
        )
        if not core or any(c.true_pass is None for c in core):
            raise StopRequired(f"P0 task {task.task_id} has no completed core set.")
        if not any(c.true_pass is True for c in core) or not any(
            c.true_pass is False for c in core
        ):
            raise StopRequired(f"P0 task {task.task_id} lacks passing or failing core candidates.")
        for j in range(slots + (i < extras)):
            channel = config["channels"][j % 2] if j < slots else config["channels"][i % 2]
            candidate = core[(i + j // 2) % len(core)]
            condition = config["conditions"][(slots * i + j) % len(config["conditions"])]
            key = (task.task_id, candidate.cand_id, channel, condition)
            if key not in index:
                raise StopRequired(f"Required P0 item is unavailable: {key}.")
            chosen.append(index[key])
    if len(chosen) != n_calls or len({item.item_id for item in chosen}) != n_calls:
        raise StopRequired("P0 selection did not yield 100 unique item IDs.")
    channels = Counter(item.channel for item in chosen)
    if channels != {"C": 50, "D": 50}:
        raise StopRequired("P0 selection did not yield 50 items in each channel.")
    if {item.condition for item in chosen} != set(config["conditions"]):
        raise StopRequired("P0 selection does not cover all nine frozen conditions.")
    return task_map, chosen


def _manifest_payload(
    paths: Paths,
    config: Config,
    registry: Config,
    tasks: list[Task],
    candidates: list[Candidate],
    items: list[Item],
) -> dict[str, Any]:
    task_map, chosen = select_p0_items(tasks, candidates, items, config)
    wm_a = registry["models"]["wm_a"]
    q4 = resolve_model(paths, wm_a, "Q4_K_M")
    assignments = []
    for item in chosen:
        messages = [message.model_dump() for message in item.messages]
        assignments.append(
            {
                "item_id": item.item_id,
                "task_id": item.task_id,
                "candidate_id": item.cand_id,
                "channel": item.channel,
                "condition": item.condition,
                "messages": messages,
                "message_sha256": _hash_bytes(_canonical(messages)),
            }
        )
    return {
        "algorithm": ALGORITHM,
        "source_sha256": {
            "tasks": _file_hash(paths.tasks),
            "candidates": _file_hash(paths.candidates),
            "items": _file_hash(paths.items),
        },
        "task_ids": list(task_map),
        "item_ids": [item.item_id for item in chosen],
        "channel_counts": dict(Counter(item.channel for item in chosen)),
        "condition_counts": dict(Counter(item.condition for item in chosen)),
        "assignments": assignments,
        "wm_a": {
            "source": wm_a["source"],
            "source_revision": wm_a["source_revision"],
            "gguf_revision": wm_a["gguf_revision"],
            "quantization": "Q4_K_M",
            "model_sha256": q4.sha256,
        },
        "inference": {
            "sampling": dict(config["sampling"]["wm"]),
            "context_size": config["server"]["context_size"],
            "server_host": config["server"]["host"],
            "server_port": config["server"]["port"],
        },
    }


def _verified_manifest(value: dict[str, Any]) -> dict[str, Any]:
    payload = {key: entry for key, entry in value.items() if key != "manifest_sha256"}
    if value.get("manifest_sha256") != _hash_bytes(_canonical(payload)):
        raise StopRequired("P0 selection manifest SHA-256 is invalid.")
    return payload


def prepare_p0_manifest(paths: Paths, config: Config) -> dict[str, Any]:
    registry = load_models(paths)
    tasks = read_jsonl(paths.tasks, Task)
    candidates = read_jsonl(paths.candidates, Candidate)
    items = read_jsonl(paths.items, Item)
    payload = _manifest_payload(paths, config, registry, tasks, candidates, items)
    value = {**payload, "manifest_sha256": _hash_bytes(_canonical(payload))}
    if paths.p0_manifest.exists():
        existing = json.loads(paths.p0_manifest.read_text(encoding="utf-8"))
        _verified_manifest(existing)
        if existing != value:
            raise StopRequired("Frozen P0 selection differs from current source files.")
        return existing
    write_json(paths.p0_manifest, value)
    return value


def load_p0_manifest(
    paths: Paths, config: Config
) -> tuple[dict[str, Any], dict[str, Task], list[Item]]:
    if not paths.p0_manifest.is_file():
        raise StopRequired("Frozen P0 selection manifest is missing; prepare inputs first.")
    saved = json.loads(paths.p0_manifest.read_text(encoding="utf-8"))
    _verified_manifest(saved)
    registry = load_models(paths)
    tasks = read_jsonl(paths.tasks, Task)
    candidates = read_jsonl(paths.candidates, Candidate)
    items = read_jsonl(paths.items, Item)
    expected = _manifest_payload(paths, config, registry, tasks, candidates, items)
    if saved != {**expected, "manifest_sha256": _hash_bytes(_canonical(expected))}:
        raise StopRequired(
            "Frozen P0 selection does not match current tasks, candidates, or items."
        )
    task_map, chosen = select_p0_items(tasks, candidates, items, config)
    return saved, task_map, chosen
