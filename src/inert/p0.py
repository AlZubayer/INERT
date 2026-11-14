import logging
import re
import threading
import time
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import yaml

from inert.audit import Progress, StopRequired, record_deviation
from inert.config import Config, Paths
from inert.llm_client import completion_request
from inert.models import load_models, model_session
from inert.p0_measurement import (
    finalize_measurement,
    measurement_path,
    query_vram_mib,
    record_live_request,
    trial_identity,
)
from inert.p0_selection import load_p0_manifest
from inert.parse import ParsedResult, parse_result
from inert.schemas import Score, atomic_text, write_json, write_jsonl
from inert.server import ServerError


def feasibility_decision(median_seconds: float, thresholds: Config) -> str:
    if median_seconds <= thresholds["p0_full_seconds"]:
        return "full"
    if median_seconds <= thresholds["p0_reduced_seconds"]:
        return "reduced"
    return "drop_wm_a"


def p0_quantizations(paths: Paths, registry: Config) -> list[str]:
    q3_files = [
        paths.root / entry["path"]
        for entry in registry["models"]["wm_a"]["files"]
        if "q3_k_m" in entry["filename"].lower()
    ]
    if q3_files and all(path.is_file() for path in q3_files):
        return ["Q4_K_M", "Q3_K_M"]
    return ["Q4_K_M"]


def truncated_before_result(finish_reason: str | None, parsed: ParsedResult) -> bool:
    return finish_reason == "length" and parsed.n_pred is None


def oom_from_load_error(error: ServerError) -> bool:
    match = re.search(r"see (.+?\.log)(?:\.|$)", str(error))
    if match is None:
        return False
    log_path = Path(match.group(1))
    if not log_path.is_file():
        return False
    error_text = log_path.read_text(encoding="utf-8", errors="replace").lower()
    return any(
        message in error_text for message in ("out of memory", "failed to allocate", "cudamalloc")
    )


def run_p0(paths: Paths, config: Config, logger: logging.Logger) -> dict:
    registry = load_models(paths)
    manifest, task_map, items = load_p0_manifest(paths, config)
    outcomes = []
    for quant in p0_quantizations(paths, registry):
        max_layers = registry["models"]["wm_a"]["layer_count"] + 1
        trials = range(max_layers, -1, -1) if quant == "Q4_K_M" else [max_layers]
        for layers in trials:
            try:
                with model_session(paths, config, "wm_a", quant, layers) as client:
                    parameters = dict(config["sampling"]["wm"])
                    attempts = []
                    while True:
                        identity = trial_identity(
                            paths,
                            registry,
                            client,
                            quant,
                            layers,
                            parameters,
                            manifest["manifest_sha256"],
                        )
                        peak: list[int] = []
                        monitor_errors: list[str] = []
                        stopped = threading.Event()
                        trial_started = time.perf_counter()

                        def monitor(
                            stopped: threading.Event = stopped,
                            peak: list[int] = peak,
                            monitor_errors: list[str] = monitor_errors,
                        ) -> None:
                            while not stopped.is_set():
                                try:
                                    peak.append(query_vram_mib())
                                except StopRequired as error:
                                    monitor_errors.append(str(error))
                                    return
                                stopped.wait(0.1)

                        watcher = threading.Thread(target=monitor, daemon=True)
                        watcher.start()
                        live_requests = 0
                        request_keys: list[str] = []
                        try:
                            scores = []
                            truncated = 0
                            progress = Progress(len(items))
                            for item in items:
                                key, _, _ = completion_request(
                                    client.model_hash, client.flags, item.messages, parameters
                                )
                                sample_start = len(peak)
                                completion = client.complete(item.messages, parameters)
                                if not completion.cache_hit:
                                    live_requests += 1
                                    if monitor_errors:
                                        raise StopRequired(monitor_errors[0])
                                    peak.append(query_vram_mib())
                                    window = peak[sample_start:]
                                    record_live_request(
                                        paths,
                                        identity,
                                        key,
                                        max(window),
                                        len(window),
                                        completion.latency_s,
                                        completion.completion_tokens,
                                        client.server_startup_seconds
                                        if live_requests == 1
                                        else None,
                                    )
                                request_keys.append(key)
                                parsed = parse_result(
                                    completion.raw_output, task_map[item.task_id].n_tests
                                )
                                truncated += truncated_before_result(
                                    completion.finish_reason, parsed
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
                        finally:
                            stopped.set()
                            watcher.join(timeout=11)
                        if watcher.is_alive() and live_requests:
                            raise StopRequired("P0 GPU-memory monitor did not stop cleanly.")
                        if monitor_errors and live_requests:
                            raise StopRequired(monitor_errors[0])
                        measurement = finalize_measurement(
                            paths,
                            identity,
                            request_keys,
                            scores,
                            time.perf_counter() - trial_started,
                        )
                        score_path = (
                            paths.data / "p0" / f"{quant}-{layers}-{parameters['max_tokens']}.jsonl"
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
                                True,
                            )
                            parameters["max_tokens"] = config["p0"]["extended_max_tokens"]
                            continue
                        break
                    latencies = [
                        measurement["live_observations"][key]["latency_s"] for key in request_keys
                    ]
                    fail_rate = sum(s.parse_status == "fail" for s in scores) / len(scores)
                    if fail_rate > config["thresholds"]["parse_failure"]:
                        raise StopRequired(
                            "P0 parse-failure rate exceeds 10%. "
                            "Inspect the prompt before continuing."
                        )
                    total_tokens = sum(
                        measurement["live_observations"][key]["completion_tokens"]
                        for key in request_keys
                    )
                    outcomes.append(
                        {
                            "quantization": quant,
                            "n_gpu_layers": layers,
                            "median_seconds": float(np.median(latencies)),
                            "p90_seconds": float(np.quantile(latencies, 0.9)),
                            "tokens_per_second": total_tokens / sum(latencies),
                            "parse_failure_rate": fail_rate,
                            "peak_vram_mib": measurement["peak_vram_mib"],
                            "vram_measurement_file": str(
                                measurement_path(paths, identity).relative_to(paths.root)
                            ),
                            "vram_live_requests": measurement["live_requests_completed"],
                            "live_requests_this_run": measurement["last_run_live_requests"],
                            "cache_hits_this_run": measurement["last_run_cache_hits"],
                            "server_startup_seconds": measurement["startup_seconds"],
                            "total_elapsed_seconds": measurement["last_run_elapsed_seconds"],
                            "latency_source": (
                                "live HTTP request durations, including cached originals"
                            ),
                            "max_tokens": parameters["max_tokens"],
                            "source_score_files": attempts,
                            "calls": len(scores),
                        }
                    )
                    break
            except ServerError as error:
                logger.exception("WM-A load failed: %s layers=%s", quant, layers)
                if not oom_from_load_error(error):
                    raise StopRequired(
                        "WM-A could not be loaded. Review the server log "
                        "before substituting or dropping it."
                    ) from error
            except FileNotFoundError as error:
                raise StopRequired(f"WM-A {quant} model file is unavailable.") from error
    if not outcomes and "Q3_K_M" not in p0_quantizations(paths, registry):
        raise StopRequired("WM-A Q4 could not load and the prescribed Q3 fallback is unavailable.")
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
