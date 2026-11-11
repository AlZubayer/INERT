import logging
import subprocess
import threading
from dataclasses import asdict
from datetime import UTC, datetime

import numpy as np
import yaml

from inert.audit import Progress, StopRequired, record_deviation
from inert.config import Config, Paths
from inert.models import load_models, model_session
from inert.parse import parse_result
from inert.schemas import Item, Score, Task, atomic_text, read_jsonl, write_json, write_jsonl
from inert.server import ServerError


def feasibility_decision(median_seconds: float, thresholds: Config) -> str:
    if median_seconds <= thresholds["p0_full_seconds"]:
        return "full"
    if median_seconds <= thresholds["p0_reduced_seconds"]:
        return "reduced"
    return "drop_wm_a"


def run_p0(paths: Paths, config: Config, logger: logging.Logger) -> dict:
    registry = load_models(paths)
    tasks = read_jsonl(paths.tasks, Task)
    task_map = {task.task_id: task for task in tasks[: config["p0"]["tasks"]]}
    items = [item for item in read_jsonl(paths.items, Item) if item.task_id in task_map][
        : config["p0"]["calls"]
    ]
    if len(items) != config["p0"]["calls"]:
        raise ValueError("P0 requires 100 prepared items from the first 12 ready tasks.")
    outcomes = []
    for quant in ["Q4_K_M", "Q3_K_M"]:
        max_layers = registry["models"]["wm_a"]["layer_count"] + 1
        trials = range(max_layers, -1, -1) if quant == "Q4_K_M" else [max_layers]
        for layers in trials:
            try:
                with model_session(paths, config, "wm_a", quant, layers) as client:
                    peak: list[int] = []
                    stopped = threading.Event()

                    def monitor(stopped: threading.Event = stopped, peak: list[int] = peak) -> None:
                        while not stopped.is_set():
                            result = subprocess.run(
                                [
                                    "nvidia-smi",
                                    "--query-gpu=memory.used",
                                    "--format=csv,noheader,nounits",
                                ],
                                capture_output=True,
                                text=True,
                                timeout=10,
                            )
                            if result.returncode == 0:
                                peak.extend(int(x) for x in result.stdout.split() if x.isdigit())
                            stopped.wait(0.1)

                    watcher = threading.Thread(target=monitor, daemon=True)
                    watcher.start()
                    parameters = dict(config["sampling"]["wm"])
                    attempts = []
                    try:
                        while True:
                            scores = []
                            truncated = 0
                            progress = Progress(len(items))
                            for item in items:
                                completion = client.complete(item.messages, parameters)
                                parsed = parse_result(
                                    completion.raw_output, task_map[item.task_id].n_tests
                                )
                                truncated += (
                                    completion.finish_reason == "length"
                                    and parsed.parse_status == "fail"
                                )
                                scores.append(
                                    Score(
                                        item_id=item.item_id,
                                        wm_id="wm_a",
                                        raw_output=completion.raw_output,
                                        **asdict(parsed),
                                        latency_s=completion.latency_s,
                                        completion_tokens=completion.completion_tokens,
                                        cache_hit=completion.cache_hit,
                                        timestamp=completion.timestamp,
                                    )
                                )
                                progress.advance()
                            score_path = (
                                paths.data
                                / "p0"
                                / f"{quant}-{layers}-{parameters['max_tokens']}.jsonl"
                            )
                            write_jsonl(score_path, scores, Score)
                            attempts.append(str(score_path.relative_to(paths.root)))
                            if (
                                truncated / len(items) > config["thresholds"]["p0_truncation"]
                                and parameters["max_tokens"] != config["p0"]["extended_max_tokens"]
                            ):
                                record_deviation(
                                    paths,
                                    f"P0 {quant}: truncated without RESULT above 5%; "
                                    "raise WM-A max_tokens to 2048 under section 5.2.",
                                    False,
                                )
                                parameters["max_tokens"] = config["p0"]["extended_max_tokens"]
                                continue
                            break
                    finally:
                        stopped.set()
                        watcher.join(timeout=11)
                    latencies = [s.latency_s for s in scores]
                    fail_rate = sum(s.parse_status == "fail" for s in scores) / len(scores)
                    if fail_rate > config["thresholds"]["parse_failure"]:
                        raise StopRequired(
                            "P0 parse-failure rate exceeds 10%. "
                            "Inspect the prompt before continuing."
                        )
                    total_tokens = sum(s.completion_tokens or 0 for s in scores)
                    outcomes.append(
                        {
                            "quantization": quant,
                            "n_gpu_layers": layers,
                            "median_seconds": float(np.median(latencies)),
                            "p90_seconds": float(np.quantile(latencies, 0.9)),
                            "tokens_per_second": total_tokens / sum(latencies),
                            "parse_failure_rate": fail_rate,
                            "peak_vram_mib": max(peak) if peak else None,
                            "max_tokens": parameters["max_tokens"],
                            "source_score_files": attempts,
                            "calls": len(scores),
                        }
                    )
                    break
            except ServerError:
                logs = sorted((paths.data / "logs").glob("server-*.log"))
                error_text = (
                    logs[-1].read_text(encoding="utf-8", errors="replace").lower() if logs else ""
                )
                logger.exception("WM-A load failed: %s layers=%s", quant, layers)
                if not any(
                    message in error_text
                    for message in ("out of memory", "failed to allocate", "cudamalloc")
                ):
                    raise StopRequired(
                        "WM-A could not be loaded. Review the server log "
                        "before substituting or dropping it."
                    ) from None
    if not outcomes:
        result = {
            "decision": "drop_wm_a",
            "reason": "Both prescribed quantizations failed to load.",
            "timestamp": datetime.now(UTC).isoformat(),
            "trials": [],
        }
    else:
        best = min(outcomes, key=lambda row: row["median_seconds"])
        result = {
            **best,
            "decision": feasibility_decision(best["median_seconds"], config["thresholds"]),
            "timestamp": datetime.now(UTC).isoformat(),
            "trials": outcomes,
        }
        registry["models"]["wm_a"]["n_gpu_layers"] = best["n_gpu_layers"]
        registry["models"]["wm_a"]["quantization"] = best["quantization"]
        atomic_text(paths.configs / "models.yaml", yaml.safe_dump(registry, sort_keys=False))
    write_json(paths.results / "p0.json", result)
    if result["decision"] == "drop_wm_a":
        raise StopRequired("P0 says drop WM-A. The owner must decide before continuing.")
    return result
