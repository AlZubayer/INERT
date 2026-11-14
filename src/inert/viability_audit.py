"""Offline, read-only calculations for the 2026-11-14 research decision memo.

Run with ``python -m inert.viability_audit``. Only the JSON summary in the
ignored viability-assessment directory is written. No model is loaded.
"""

import hashlib
import json
import sqlite3
import statistics
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np

from inert.config import Paths
from inert.parse import parse_result


def digest(value: Any) -> str:
    """Hash a JSON value using the manifest's canonical representation."""
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
    ).hexdigest()


def median_bounds(observed: list[float], total: int) -> tuple[float, float]:
    """Sharp median bounds when the remaining positive latencies are unknown."""
    if len(observed) > total or len(observed) <= total // 2 or total % 2:
        raise ValueError("An even total and more than half the observations are required.")
    ordered = sorted(observed)
    missing = total - len(ordered)
    lo = statistics.mean(ordered[total // 2 - missing - 1 : total // 2 - missing + 1])
    hi = statistics.mean(ordered[total // 2 - 1 : total // 2 + 1])
    return lo, hi


def file_sha(path: Path) -> str:
    """Hash an evidence file without changing it."""
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def audit(root: Path) -> dict[str, Any]:
    """Reconcile the original P0 records and derive descriptive projections."""
    paths = Paths(root)
    manifest = json.loads(paths.p0_manifest.read_text(encoding="utf-8"))
    payload = {k: v for k, v in manifest.items() if k != "manifest_sha256"}
    if digest(payload) != manifest["manifest_sha256"] or len(manifest["assignments"]) != 100:
        raise ValueError("Frozen P0 manifest does not verify.")
    assignments = {row["message_sha256"]: row for row in manifest["assignments"]}
    if len(assignments) != 100 or len({a["item_id"] for a in assignments.values()}) != 100:
        raise ValueError("P0 assignments are duplicated.")
    tasks = {
        row["task_id"]: row
        for row in map(json.loads, paths.tasks.read_text(encoding="utf-8").splitlines())
    }
    cache_path = paths.cache("wm_a")
    rows: list[dict[str, Any]] = []
    request_template: dict[str, Any] | None = None
    with sqlite3.connect(f"file:{cache_path.as_posix()}?mode=ro", uri=True) as db:
        db.execute("PRAGMA query_only=ON")
        if db.execute("PRAGMA integrity_check").fetchone() != ("ok",):
            raise ValueError("Original cache integrity check failed.")
        for key, request, response, completion in db.execute(
            "SELECT key, request, response, completion FROM calls"
        ):
            req, body, saved = map(json.loads, (request, response, completion))
            if request_template is None:
                request_template = {k: v for k, v in req.items() if k != "messages"}
            elif {k: v for k, v in req.items() if k != "messages"} != request_template:
                raise ValueError("Original P0 request settings are inconsistent.")
            assignment = assignments.get(digest(req["messages"]))
            if assignment is None or hashlib.sha256(request.encode()).hexdigest() != key:
                raise ValueError("Cache key or manifest membership disagrees.")
            choice = body["choices"][0]
            raw = choice["message"].get("content") or ""
            if choice["message"].get("reasoning_content"):
                raw = "<think>" + choice["message"]["reasoning_content"] + "</think>\n" + raw
            if (
                raw != saved["raw_output"]
                or choice["finish_reason"] != saved["finish_reason"]
                or body["usage"]["completion_tokens"] != saved["completion_tokens"]
                or req["model_file_sha256"] != manifest["wm_a"]["model_sha256"]
                or req["max_tokens"] != 1024
                or (req["temperature"], req["top_p"], req["seed"]) != (0, 1, 0)
            ):
                raise ValueError("Original response or frozen request settings disagree.")
            parsed = parse_result(raw, tasks[assignment["task_id"]]["n_tests"])
            rows.append(
                {
                    "key": key,
                    "item_id": assignment["item_id"],
                    "channel": assignment["channel"],
                    "condition": assignment["condition"],
                    "parse": parsed.parse_status,
                    "k_pred": parsed.k_pred,
                    "n_pred": parsed.n_pred,
                    "finish": saved["finish_reason"],
                    "tokens": saved["completion_tokens"],
                    "latency_s": saved["latency_s"],
                    "open_think": "<think>" in raw and "</think>" not in raw,
                    "raw_sha256": hashlib.sha256(raw.encode()).hexdigest(),
                    "raw": raw,
                }
            )
    by_id = {r["item_id"]: r for r in rows}
    if len(rows) != 62 or len(by_id) != 62 or len({r["key"] for r in rows}) != 62:
        raise ValueError("Original P0 cache is not the preserved 62-response set.")
    assert request_template is not None
    escalated_keys = {
        digest({**request_template, "messages": assignment["messages"], "max_tokens": 2048})
        for assignment in assignments.values()
    }
    if len(escalated_keys) != 100 or escalated_keys & {r["key"] for r in rows}:
        raise ValueError("Escalated request keys are duplicated or overlap the first pass.")
    ordered = [by_id[item] for item in manifest["item_ids"] if item in by_id]
    if [r["item_id"] for r in ordered] != manifest["item_ids"][:62]:
        raise ValueError("Original responses are not the first 62 frozen assignments.")
    measurement_path = next(paths.p0_measurements.glob("*.json"))
    measure = json.loads(measurement_path.read_text(encoding="utf-8"))
    if (
        measure["record_sha256"]
        != digest({k: v for k, v in measure.items() if k != "record_sha256"})
        or measure["identity"]["item_manifest_sha256"] != manifest["manifest_sha256"]
        or measure["status"] != "INCOMPLETE"
    ):
        raise ValueError("Original measurement record does not verify.")
    observations = measure["live_observations"]
    if len(observations) != 61 or set(observations) - {r["key"] for r in rows}:
        raise ValueError("Original live measurements do not match cache.")
    for row in rows:
        observation = observations.get(row["key"])
        if observation and (
            observation["latency_s"] != row["latency_s"]
            or observation["completion_tokens"] != row["tokens"]
            or observation["sample_count"] <= 0
        ):
            raise ValueError("Live observation disagrees with its original completion.")
    missing = [r for r in rows if r["key"] not in observations]
    if len(missing) != 1 or missing[0]["item_id"] != manifest["item_ids"][61]:
        raise ValueError("Original call-62 telemetry gap changed.")
    recovery = root / "data/p0/telemetry_recovery_20261114"
    replay = json.loads((recovery / "audit_summary.json").read_text(encoding="utf-8"))
    if (
        replay["request_key"] != missing[0]["key"]
        or replay["replay_raw_sha256"] != missing[0]["raw_sha256"]
        or not replay["output_byte_identical"]
        or replay["replay_peak_vram_mib"] != 15774
        or not replay["original_evidence_unchanged"]
    ):
        raise ValueError("Isolated replay disagrees with original call 62.")
    with sqlite3.connect(f"file:{(recovery / 'replay.sqlite').as_posix()}?mode=ro", uri=True) as db:
        db.execute("PRAGMA query_only=ON")
        if db.execute("PRAGMA integrity_check").fetchone() != ("ok",):
            raise ValueError("Replay cache integrity check failed.")
        replay_rows = db.execute("SELECT key, completion FROM calls").fetchall()
    if len(replay_rows) != 1 or replay_rows[0][0] != missing[0]["key"]:
        raise ValueError("Replay cache is not a separate one-call cache.")
    replay_raw = json.loads(replay_rows[0][1])["raw_output"]
    if replay_raw != missing[0]["raw"]:
        raise ValueError("Replay output is not byte-identical.")
    measured = [r for r in rows if r["key"] in observations]
    measured_latencies = [r["latency_s"] for r in measured]
    all_latencies = [r["latency_s"] for r in ordered]
    by_channel = {}
    for channel in ("C", "D"):
        group = [r for r in ordered if r["channel"] == channel]
        by_channel[channel] = {
            "calls": len(group),
            "parse_ok": sum(r["parse"] == "ok" for r in group),
            "parse_fail": sum(r["parse"] == "fail" for r in group),
            "length": sum(r["finish"] == "length" for r in group),
            "truncated_before_result": sum(
                r["finish"] == "length" and r["n_pred"] is None for r in group
            ),
            "wrong_denominator": sum(
                r["n_pred"] is not None
                and r["n_pred"] != tasks[r["item_id"].split(":")[0]]["n_tests"]
                for r in group
            ),
            "median_latency_s": statistics.median(r["latency_s"] for r in group),
        }
    stop_indices = [i + 1 for i, r in enumerate(ordered) if r["parse"] == "ok"]
    raw_fingerprints = Counter(r["raw_sha256"] for r in rows)
    lat_quantiles = {str(q): float(np.quantile(all_latencies, q)) for q in (0.1, 0.5, 0.9)}
    scenarios = {
        "optimistic": {
            "first_pass_s_per_call": lat_quantiles["0.1"],
            "escalated_s_per_call": lat_quantiles["0.1"],
        },
        "central": {
            "first_pass_s_per_call": lat_quantiles["0.5"],
            "escalated_s_per_call": 2048
            / (sum(r["tokens"] for r in measured) / sum(measured_latencies)),
        },
        "conservative": {
            "first_pass_s_per_call": lat_quantiles["0.9"],
            "escalated_s_per_call": 2.4 * lat_quantiles["0.9"],
        },
    }
    for scenario in scenarios.values():
        first = 38 * scenario["first_pass_s_per_call"]
        extended = 100 * scenario["escalated_s_per_call"]
        scenario.update(
            {
                "first_pass_hours": first / 3600,
                "escalated_hours": extended / 3600,
                "combined_hours": (first + extended) / 3600,
            }
        )
    result = {
        "evidence": {
            "manifest_identity": manifest["manifest_sha256"],
            "manifest_file_sha256": file_sha(paths.p0_manifest),
            "cache_file_sha256": file_sha(cache_path),
            "measurement_file_sha256": file_sha(measurement_path),
            "replay_cache_file_sha256": file_sha(recovery / "replay.sqlite"),
            "original_cache_integrity": "ok",
            "replay_cache_integrity": "ok",
        },
        "counts": {
            "planned": 100,
            "original": len(rows),
            "measured": len(measured),
            "missing_original_vram": len(missing),
            "replay": len(replay_rows),
            "unique_escalated_request_keys": len(escalated_keys),
            "parse_ok": sum(r["parse"] == "ok" for r in rows),
            "parse_fail": sum(r["parse"] == "fail" for r in rows),
            "length": sum(r["finish"] == "length" for r in rows),
            "stop": sum(r["finish"] == "stop" for r in rows),
            "truncated_before_result": sum(
                r["finish"] == "length" and r["n_pred"] is None for r in rows
            ),
            "result_present_but_invalid": sum(
                r["parse"] == "fail" and r["n_pred"] is not None for r in rows
            ),
            "open_think": sum(r["open_think"] for r in rows),
            "exact_duplicate_raw_outputs": sum(n - 1 for n in raw_fingerprints.values() if n > 1),
        },
        "by_channel": by_channel,
        "parse_success_positions": stop_indices,
        "measured": {
            "median_latency_s": statistics.median(measured_latencies),
            "p90_latency_s": float(np.quantile(measured_latencies, 0.9)),
            "sum_http_seconds": sum(measured_latencies),
            "completion_tokens": sum(r["tokens"] for r in measured),
            "tokens_per_second": sum(r["tokens"] for r in measured) / sum(measured_latencies),
            "peak_vram_mib": max(v["peak_vram_mib"] for v in observations.values()),
            "startup_seconds": [
                measure["startup_seconds"],
                *measure.get("additional_startup_seconds", []),
            ],
        },
        "all_62": {
            "latency_quantiles_s": lat_quantiles,
            "sum_http_seconds": sum(all_latencies),
            "median_bounds_for_final_100_s": median_bounds(all_latencies, 100),
            "completion_token_counts": dict(Counter(r["tokens"] for r in rows)),
        },
        "replay": {
            "latency_s": replay["replay_http_latency_s"],
            "peak_vram_mib": replay["replay_peak_vram_mib"],
            "raw_output_identical": True,
            "startup_seconds": replay["server_startup_seconds"],
        },
        "projected_http_only": scenarios,
    }
    return result


def main() -> None:
    """Write only a derived summary under the ignored assessment directory."""
    root = Path(__file__).resolve().parents[2]
    output = root / "data/p0/viability_assessment_20261114/audit.json"
    result = audit(root)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
