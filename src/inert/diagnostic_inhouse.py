"""Isolated, resumable WM-C prompt-family diagnostic; never pilot scoring."""

import argparse
import hashlib
import json
import logging
import re
import sqlite3
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path

from inert.audit import Progress, stage_log
from inert.config import Paths, load_config
from inert.models import model_session
from inert.parse import parse_result
from inert.render import render_messages
from inert.schemas import Candidate, Item, Score, Task, Thought, read_jsonl, write_json, write_jsonl


@dataclass(frozen=True)
class DiagnosticPaths(Paths):
    @property
    def data(self) -> Path:
        return self.root / "data" / "smoke" / "diagnostics" / "inhouse"


def make_diagnostic_item(original: Item, task: Task, candidate: Candidate, paths: Paths) -> Item:
    if original.prompt_family != "vendored" or original.block != "kt_ab":
        raise ValueError("Diagnostic requires a vendored kt_ab source item.")
    if original.task_id != task.task_id or original.cand_id != candidate.cand_id:
        raise ValueError("Source item, task, and candidate do not match.")
    if not original.item_id.endswith(":vendored"):
        raise ValueError("Unexpected source item ID.")
    return Item(
        **{
            **original.model_dump(exclude={"item_id", "messages", "prompt_family"}),
            "item_id": original.item_id.removesuffix(":vendored") + ":inhouse",
            "messages": render_messages(
                task,
                candidate,
                original.channel,
                original.condition,
                original.text,
                "inhouse",
                paths,
            ),
            "prompt_family": "inhouse",
        }
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare(paths: DiagnosticPaths) -> list[Item]:
    source = Paths(paths.root, "smoke")
    config = load_config(source)
    selection_path = paths.data / "selection.json"
    selection = json.loads(selection_path.read_text(encoding="utf-8"))
    if selection["model"] != "wm_c":
        raise ValueError("This diagnostic is WM-C only.")
    if len(selection["candidate_ids"]) != len(set(selection["candidate_ids"])):
        raise ValueError("Candidate IDs must be unique.")
    if len(selection["conditions"]) != len(set(selection["conditions"])):
        raise ValueError("Conditions must be unique.")
    if not set(selection["conditions"]) <= set(config["conditions"]):
        raise ValueError("Selection includes an unregistered condition.")
    tasks = {task.task_id: task for task in read_jsonl(source.tasks, Task)}
    candidates = {
        candidate.cand_id: candidate for candidate in read_jsonl(source.candidates, Candidate)
    }
    thoughts = {thought.cand_id: thought for thought in read_jsonl(source.thoughts, Thought)}
    originals = {
        (item.cand_id, item.channel, item.condition): item
        for item in read_jsonl(source.items, Item)
        if item.block == "kt_ab" and item.prompt_family == "vendored"
    }
    output: list[Item] = []
    for cand_id in selection["candidate_ids"]:
        candidate = candidates[cand_id]
        if not candidate.in_core_set or candidate.true_pass is None:
            raise ValueError("Diagnostic requires an executed core-set candidate.")
        if cand_id not in thoughts:
            raise ValueError("Core-set thought is missing.")
        task = tasks[candidate.task_id]
        for condition in selection["conditions"]:
            for channel in config["channels"]:
                original = originals[(cand_id, channel, condition)]
                output.append(make_diagnostic_item(original, task, candidate, source))
    expected = (
        len(selection["candidate_ids"]) * len(selection["conditions"]) * len(config["channels"])
    )
    if len(output) != expected or len({item.item_id for item in output}) != expected:
        raise ValueError("Diagnostic item count or IDs are inconsistent.")
    metadata = {
        "model": "wm_c",
        "prompt_family": "inhouse",
        "candidate_ids": selection["candidate_ids"],
        "conditions": selection["conditions"],
        "channels": config["channels"],
        "sampling": config["sampling"]["wm"],
        "context_size": config["server"]["context_size"],
        "source_sha256": {
            str(path.relative_to(paths.root)): _sha256(path)
            for path in (
                source.tasks,
                source.candidates,
                source.thoughts,
                source.items,
                paths.prompts / "inhouse" / "wm_terminal.txt",
                paths.prompts / "inhouse" / "wm_tool.txt",
                paths.configs / "pilot.yaml",
            )
        },
    }
    manifest_path = paths.data / "manifest.json"
    if manifest_path.exists() and json.loads(manifest_path.read_text(encoding="utf-8")) != metadata:
        raise ValueError("Diagnostic source files or frozen settings changed.")
    if paths.items.exists():
        if read_jsonl(paths.items, Item) != output:
            raise ValueError("Existing diagnostic items differ from the fixed selection.")
    else:
        write_jsonl(paths.items, output, Item)
    if not manifest_path.exists():
        write_json(manifest_path, metadata)
    return output


def run(paths: DiagnosticPaths, logger: logging.Logger) -> None:
    config = load_config(paths)
    items = prepare(paths)
    tasks = {task.task_id: task for task in read_jsonl(Paths(paths.root, "smoke").tasks, Task)}
    scores = read_jsonl(paths.scores("wm_c"), Score)
    done = {score.item_id for score in scores}
    if len(done) != len(scores) or not done <= {item.item_id for item in items}:
        raise ValueError("Unexpected or duplicate diagnostic scores.")
    metadata_path = paths.data / "completion_meta.json"
    metadata = (
        json.loads(metadata_path.read_text(encoding="utf-8")) if metadata_path.exists() else {}
    )
    todo = [item for item in items if item.item_id not in done]
    progress = Progress(len(todo))
    with model_session(paths, config, "wm_c") as client:
        for item in todo:
            completion = client.complete(item.messages, config["sampling"]["wm"])
            parsed = parse_result(completion.raw_output, tasks[item.task_id].n_tests)
            metadata[item.item_id] = {
                "finish_reason": completion.finish_reason,
                "completion_tokens": completion.completion_tokens,
                "cache_hit": completion.cache_hit,
            }
            write_json(metadata_path, metadata)
            scores.append(
                Score(
                    item_id=item.item_id,
                    wm_id="wm_c",
                    raw_output=completion.raw_output,
                    **asdict(parsed),
                    latency_s=completion.latency_s,
                    completion_tokens=completion.completion_tokens,
                    cache_hit=completion.cache_hit,
                    timestamp=completion.timestamp,
                )
            )
            write_jsonl(paths.scores("wm_c"), scores, Score)
            progress.advance()
    logger.info("Completed %s of %s fixed diagnostic calls", len(scores), len(items))


def classify_output(
    raw_output: str,
    parse_status: str,
    predicted_denominator: int | None,
    expected_denominator: int,
    finish_reason: str | None,
) -> dict[str, bool]:
    lines = [line.strip() for line in raw_output.splitlines() if line.strip()]
    repeated = any(count >= 4 for count in Counter(lines).values())
    has_result = bool(re.search(r"RESULT:\s*\d+\s*/\s*\d+", raw_output))
    missing_file = bool(
        re.search(
            r"(?:solution\.py|run_tests\.py).*No such file or directory",
            raw_output,
            flags=re.I,
        )
    )
    no_result = parse_status == "fail" and not has_result
    wrong_n = (
        parse_status == "fail"
        and predicted_denominator is not None
        and predicted_denominator != expected_denominator
    )
    return {
        "no_result": no_result,
        "incorrect_denominator": wrong_n,
        "truncated": finish_reason == "length",
        "repetitive": repeated,
        "missing_file_hallucination": missing_file,
        "other_malformed": parse_status == "fail" and not no_result and not wrong_n,
    }


def analyze(paths: DiagnosticPaths) -> dict:
    source = Paths(paths.root, "smoke")
    diagnostic_items = {item.item_id: item for item in read_jsonl(paths.items, Item)}
    vendored_items = [
        item
        for item in read_jsonl(source.items, Item)
        if item.block == "kt_ab" and item.prompt_family == "vendored"
    ]
    candidates = {
        candidate.cand_id: candidate for candidate in read_jsonl(source.candidates, Candidate)
    }
    tasks = {task.task_id: task for task in read_jsonl(source.tasks, Task)}
    completion_meta = json.loads((paths.data / "completion_meta.json").read_text(encoding="utf-8"))
    diagnostic_scores = read_jsonl(paths.scores("wm_c"), Score)
    vendored_by_messages: dict[str, list[Item]] = defaultdict(list)
    for item in vendored_items:
        key = json.dumps([message.model_dump() for message in item.messages], sort_keys=True)
        vendored_by_messages[key].append(item)
    vendored_scores: list[tuple[Item, Score, str | None]] = []
    cache = source.cache("wm_c")
    with sqlite3.connect("file:" + cache.as_posix() + "?mode=ro", uri=True) as database:
        cached = database.execute("SELECT request, completion FROM calls").fetchall()
    for request_json, completion_json in cached:
        request = json.loads(request_json)
        completion = json.loads(completion_json)
        key = json.dumps(request["messages"], sort_keys=True)
        matches = vendored_by_messages[key]
        if len(matches) != 1:
            raise ValueError("Vendored cached response maps to zero or multiple source items.")
        item = matches[0]
        parsed = parse_result(completion["raw_output"], tasks[item.task_id].n_tests)
        score = Score(
            item_id=item.item_id,
            wm_id="wm_c",
            raw_output=completion["raw_output"],
            **asdict(parsed),
            latency_s=completion["latency_s"],
            completion_tokens=completion["completion_tokens"],
            cache_hit=completion["cache_hit"],
            timestamp=completion["timestamp"],
        )
        vendored_scores.append((item, score, completion["finish_reason"]))

    rows = []
    for family, records in (
        (
            "inhouse",
            [
                (
                    diagnostic_items[score.item_id],
                    score,
                    completion_meta[score.item_id]["finish_reason"],
                )
                for score in diagnostic_scores
            ],
        ),
        ("vendored", vendored_scores),
    ):
        for item, score, finish_reason in records:
            candidate = candidates[item.cand_id]
            if candidate.n_passed is None or candidate.true_pass is None:
                raise ValueError("Ground truth is missing for a diagnostic candidate.")
            expected_n = tasks[item.task_id].n_tests
            rows.append(
                {
                    "family": family,
                    "task_id": item.task_id,
                    "candidate_id": item.cand_id,
                    "channel": item.channel,
                    "condition": item.condition,
                    "item_id": item.item_id,
                    "parse_status": score.parse_status,
                    "k_pred": score.k_pred,
                    "n_pred": score.n_pred,
                    "expected_denominator": expected_n,
                    "executed_passed": candidate.n_passed,
                    "executed_true_pass": candidate.true_pass,
                    "exact_count_correct": score.k_pred == candidate.n_passed
                    if score.parse_status == "ok"
                    else None,
                    "pass_label_correct": score.pred_pass == candidate.true_pass
                    if score.parse_status == "ok"
                    else None,
                    "completion_tokens": score.completion_tokens,
                    "finish_reason": finish_reason,
                    "categories": classify_output(
                        score.raw_output,
                        score.parse_status,
                        score.n_pred,
                        expected_n,
                        finish_reason,
                    ),
                    "raw_output": score.raw_output,
                }
            )
    summary = {}
    categories = (
        "no_result",
        "incorrect_denominator",
        "truncated",
        "repetitive",
        "missing_file_hallucination",
        "other_malformed",
    )
    for family in ("inhouse", "vendored"):
        summary[family] = {}
        for channel in ("C", "D"):
            group = [r for r in rows if r["family"] == family and r["channel"] == channel]
            valid = [r for r in group if r["parse_status"] == "ok"]
            summary[family][channel] = {
                "attempted": len(group),
                "valid": len(valid),
                "parse_failures": len(group) - len(valid),
                "parse_failure_rate": (len(group) - len(valid)) / len(group) if group else None,
                "exact_count_correct_among_valid": sum(r["exact_count_correct"] for r in valid),
                "pass_label_correct_among_valid": sum(r["pass_label_correct"] for r in valid),
                "categories": {
                    category: sum(row["categories"][category] for row in group)
                    for category in categories
                },
            }
    vendored_by_key = {
        (r["candidate_id"], r["channel"], r["condition"]): r
        for r in rows
        if r["family"] == "vendored"
    }
    pairs = []
    for row in rows:
        if row["family"] != "inhouse":
            continue
        key = (row["candidate_id"], row["channel"], row["condition"])
        old = vendored_by_key.get(key)
        if old is not None:
            pairs.append(
                {
                    "candidate_id": row["candidate_id"],
                    "channel": row["channel"],
                    "condition": row["condition"],
                    "inhouse_status": row["parse_status"],
                    "vendored_status": old["parse_status"],
                    "inhouse_k_pred": row["k_pred"],
                    "vendored_k_pred": old["k_pred"],
                    "inhouse_raw_output": row["raw_output"],
                    "vendored_raw_output": old["raw_output"],
                }
            )
    result = {
        "diagnostic_manifest": str((paths.data / "manifest.json").relative_to(paths.root)),
        "inhouse_scores": str(paths.scores("wm_c").relative_to(paths.root)),
        "vendored_cache": str(cache.relative_to(paths.root)),
        "summary": summary,
        "paired_count": len(pairs),
        "pairs": pairs,
        "rows": rows,
    }
    write_json(paths.data / "analysis.json", result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("prepare", "run", "analyze"))
    args = parser.parse_args()
    paths = DiagnosticPaths(Paths.discover().root, "smoke")
    with stage_log(paths, "diagnostic-inhouse-" + args.stage) as logger:
        if args.stage == "prepare":
            prepare(paths)
        elif args.stage == "run":
            run(paths, logger)
        else:
            analyze(paths)


if __name__ == "__main__":
    main()
