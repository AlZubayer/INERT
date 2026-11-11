import json
import logging
from dataclasses import asdict

from inert.audit import Progress, StopRequired
from inert.config import Config, Paths
from inert.decide import validity
from inert.llm_client import CachedClient
from inert.parse import parse_result
from inert.schemas import Candidate, Item, Score, Task, read_jsonl, write_json, write_jsonl
from inert.stats import balanced_accuracy


def score_items(
    paths: Paths,
    config: Config,
    model: str,
    items: list[Item],
    client: CachedClient,
    logger: logging.Logger,
) -> list[Score]:
    tasks = {task.task_id: task for task in read_jsonl(paths.tasks, Task)}
    scores = read_jsonl(paths.scores(model), Score)
    done = {score.item_id for score in scores}
    if len(done) != len(scores):
        raise ValueError("Duplicate score IDs.")
    todo = [item for item in items if item.item_id not in done]
    progress = Progress(len(todo))
    parameters = dict(config["sampling"]["wm"])
    p0_file = paths.results / "p0.json"
    if model == "wm_a" and p0_file.exists():
        p0 = json.loads(p0_file.read_text(encoding="utf-8"))
        parameters["max_tokens"] = p0.get("max_tokens", parameters["max_tokens"])
    try:
        for item in todo:
            result = client.complete(item.messages, parameters)
            parsed = parse_result(result.raw_output, tasks[item.task_id].n_tests)
            scores.append(
                Score(
                    item_id=item.item_id,
                    wm_id=model,
                    raw_output=result.raw_output,
                    **asdict(parsed),
                    latency_s=result.latency_s,
                    completion_tokens=result.completion_tokens,
                    cache_hit=result.cache_hit,
                    timestamp=result.timestamp,
                )
            )
            progress.advance()
            if len(scores) % 10 == 0:
                write_jsonl(paths.scores(model), scores, Score)
            first = scores[: config["p0"]["parse_check_calls"]]
            if (
                len(first) == config["p0"]["parse_check_calls"]
                and sum(s.parse_status == "fail" for s in first) / len(first)
                > config["thresholds"]["parse_failure"]
            ):
                raise StopRequired(
                    "Parse-failure rate exceeds 10% on the first 200 calls. "
                    "Inspect prompt adaptation; do not continue or clear cache silently."
                )
            measured = [s.latency_s for s in scores if not s.cache_hit]
            if measured:
                hours = (len(todo) - progress.done) * sum(measured) / len(measured) / 3600
                if hours > config["thresholds"]["max_gpu_hours"]:
                    raise StopRequired("Estimated remaining GPU time exceeds 60 hours.")
    finally:
        write_jsonl(paths.scores(model), scores, Score)
    if (
        scores
        and sum(s.parse_status == "fail" for s in scores) / len(scores)
        > config["thresholds"]["parse_failure"]
    ):
        raise StopRequired(
            "Overall parse-failure rate exceeds 10%; inspect outputs before continuing."
        )
    logger.info("Scored %s total records for %s", len(scores), model)
    return scores


def check_model_validity(
    paths: Paths, config: Config, model: str, planned_items: list[Item] | None = None
) -> dict:
    items = {item.item_id: item for item in read_jsonl(paths.items, Item)}
    candidates = {c.cand_id: c for c in read_jsonl(paths.candidates, Candidate)}
    scores = read_jsonl(paths.scores(model), Score)
    plan = list(items.values()) if planned_items is None else planned_items
    cells = {}
    channels = sorted({i.channel for i in plan if i.block == "kt_ab"})
    for channel in channels:
        planned = [
            i for i in plan if i.block == "kt_ab" and i.channel == channel and i.condition == "T0"
        ]
        matched = [
            (items[s.item_id], s)
            for s in scores
            if s.item_id in items and items[s.item_id] in planned and s.parse_status == "ok"
        ]
        ba = balanced_accuracy(
            [candidates[i.cand_id].true_pass for i, _ in matched], [s.pred_pass for _, s in matched]
        )
        cells[channel] = {**validity(ba, config["thresholds"]), "baseline_ba": ba}
    write_json(paths.results / f"{model}_validity.json", cells)
    if cells and all(cell["kt_a"] == "INVALID" for cell in cells.values()):
        raise StopRequired(
            f"Every planned {model} channel is INVALID. Review the task set before continuing."
        )
    return cells
