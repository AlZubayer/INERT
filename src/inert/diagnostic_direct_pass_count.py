"""Fixed direct pass-count diagnostic, isolated from pilot and smoke scoring."""

import argparse
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path

from inert.audit import Progress, stage_log
from inert.config import Paths, load_config
from inert.diagnostic_failure_isolation import _cached_api_body, c_cases, input_hash
from inert.harness import render_harness
from inert.models import load_models, model_session, resolve_model
from inert.parse import parse_result
from inert.schemas import Message, write_json

ROOT_NAME = "direct_pass_count_20261112"
SYSTEM = (
    "You predict the outcome of Python assertions by analyzing the supplied code. "
    "Do not execute any code or explain your reasoning. Return only the requested RESULT line."
)
DIRECT_COUNT = (
    "Determine the number of passing tests and total tests from the provided code and "
    "assertions. Output exactly one line in the format RESULT: k/n, where k is the "
    "passing count and n is the total test count."
)
FIXED_DENOMINATOR = (
    "There are exactly 3 tests. Determine how many of them pass. Output exactly one "
    "line in the format RESULT: k/3, where k is the passing count. Do not output any "
    "explanation."
)


@dataclass(frozen=True)
class DirectPaths(Paths):
    @property
    def data(self) -> Path:
        return self.root / "data" / "smoke" / "diagnostics" / ROOT_NAME


def _hash_file(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def build_cases(paths: Paths) -> list[dict]:
    """Use exactly the prior Stage-C source and assertion lists."""
    old_path = paths.root / "data/smoke/diagnostics/failure_isolation_20261112"
    old = json.loads((old_path / "manifest.json").read_text(encoding="utf-8"))
    truth = json.loads((old_path / "docker_truth.json").read_text(encoding="utf-8"))
    prior = {case["case_id"]: case for case in old["cases"] if case["stage"] == "C"}
    controls = c_cases(Paths(paths.root, "smoke"))
    if len(prior) != 16 or len(controls) != 16:
        raise ValueError("Previous Stage-C case count changed.")
    output = []
    for passed in range(4):
        control = f"C{passed}"
        matches = [case for case in controls if case.task_id == control]
        if len(matches) != 4:
            raise ValueError("Stage-C control matrix changed.")
        source = matches[0].source_code
        tests = matches[0].tests
        if source != "def f(x):\n    return x" or tests != ["assert True"] * passed + [
            "assert False"
        ] * (3 - passed):
            raise ValueError("Stage-C source or assertions changed.")
        expected_truth = {
            "source_sha256": hashlib.sha256(source.encode()).hexdigest(),
            "harness_sha256": hashlib.sha256(render_harness(tests).encode()).hexdigest(),
            "stdout": f"RESULT: {passed}/3\n",
        }
        if truth[control] != expected_truth:
            raise ValueError("Previous Docker ground truth differs from Stage-C controls.")
        for case in matches:
            if prior[case.case_id] != case.model_dump():
                raise ValueError("Previous fixed Stage-C manifest changed.")
        for model in ("wm_c", "wm_b"):
            for interface, final in (
                ("DIRECT_COUNT", DIRECT_COUNT),
                ("FIXED_DENOMINATOR", FIXED_DENOMINATOR),
            ):
                user = (
                    "solution.py:\n```python\n"
                    + source
                    + "\n```\n\nTest assertions:\n"
                    + "\n".join(f"{index}. {test}" for index, test in enumerate(tests, 1))
                    + "\n\n"
                    + final
                )
                messages = [
                    Message(role="system", content=SYSTEM),
                    Message(role="user", content=user),
                ]
                output.append(
                    {
                        "case_id": f"{model}-{control}-{interface}",
                        "model_role": model,
                        "control": control,
                        "interface": interface,
                        "source_code": source,
                        "tests": tests,
                        "expected_k": passed,
                        "expected_n": 3,
                        "docker_stdout": truth[control]["stdout"],
                        "messages": [message.model_dump() for message in messages],
                        "input_sha256": input_hash(messages),
                    }
                )
    return output


def prepare(paths: DirectPaths) -> dict:
    source = Paths(paths.root, "smoke")
    config = load_config(source)
    sampling = config["sampling"]["wm"]
    if sampling != {"temperature": 0.0, "top_p": 1.0, "max_tokens": 1024, "seed": 0}:
        raise ValueError("Frozen WM sampling changed.")
    if config["server"]["context_size"] != 8192:
        raise ValueError("Frozen context changed.")
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
            "resolved_identity": resolved.sha256,
            "files": [
                {
                    "path": str(path.relative_to(paths.root)).replace("\\", "/"),
                    "sha256": _hash_file(path),
                    "size_bytes": path.stat().st_size,
                }
                for path in resolved.files
            ],
        }
    old_dir = paths.root / "data/smoke/diagnostics/failure_isolation_20261112"
    server = paths.root / registry["serving"]["executable"]
    manifest = {
        "base_commit": "800da3c921cbed82488b3b945c4891d63a2ca05e",
        "protocol": "Direct Pass-Count Diagnostic, 2026-11-12",
        "sampling": sampling,
        "context_size": 8192,
        "server": {
            "executable": str(server.relative_to(paths.root)).replace("\\", "/"),
            "sha256": _hash_file(server),
            "build": registry["serving"]["build"],
            "commit": registry["serving"]["commit"],
        },
        "prior_manifest_sha256": _hash_file(old_dir / "manifest.json"),
        "prior_docker_truth_sha256": _hash_file(old_dir / "docker_truth.json"),
        "models": models,
        "cases": build_cases(paths),
    }
    target = paths.data / "manifest.json"
    if target.exists():
        if json.loads(target.read_text(encoding="utf-8")) != manifest:
            raise ValueError("Existing manifest differs; refusing to alter frozen diagnostic.")
    else:
        write_json(target, manifest)
    return manifest


def analyze_response(raw: str, expected_k: int, expected_n: int, finish: str | None) -> dict:
    parsed = parse_result(raw, expected_n)
    matches = re.findall(r"RESULT:\s*(\d+)\s*/\s*(\d+)", raw)
    final = "RESULT: " + "/".join(matches[-1]) if matches else None
    strict = bool(re.fullmatch(r"RESULT: \d+/\d+", raw.strip()))
    return {
        "observed_final_result": final,
        "strict_format": strict,
        "parser_status": parsed.parse_status,
        "k_pred": parsed.k_pred,
        "n_pred": parsed.n_pred,
        "denominator_matches": parsed.n_pred == expected_n,
        "wrong_denominator": parsed.n_pred is not None and parsed.n_pred != expected_n,
        "exact_count": parsed.parse_status == "ok" and parsed.k_pred == expected_k,
        "label_correct": parsed.parse_status == "ok"
        and parsed.pred_pass == (expected_k == expected_n),
        "commentary_or_repetition": bool(raw.strip()) and not strict,
        "result_occurrences": len(matches),
        "truncated": finish == "length",
    }


def response_path(paths: DirectPaths, case: dict) -> Path:
    if not re.fullmatch(r"[A-Za-z0-9_-]+", case["case_id"]):
        raise ValueError("Unsafe case ID.")
    return paths.data / "responses" / f"{case['case_id']}.json"


def run(paths: DirectPaths) -> None:
    manifest = prepare(paths)
    config = load_config(paths)
    params = config["sampling"]["wm"]
    pending = [case for case in manifest["cases"] if not response_path(paths, case).exists()]
    progress = Progress(len(pending)) if pending else None
    with stage_log(paths, "direct-pass-count") as logger:
        for role in ("wm_c", "wm_b"):
            group = [case for case in pending if case["model_role"] == role]
            if not group:
                continue
            with model_session(paths, config, role) as client:
                for case in group:
                    messages = [Message.model_validate(message) for message in case["messages"]]
                    completion = client.complete(messages, params)
                    body = _cached_api_body(client, _case_proxy(case, messages), params)
                    record = {
                        "case_id": case["case_id"],
                        "input_sha256": case["input_sha256"],
                        "raw_output": completion.raw_output,
                        "raw_api_response": body,
                        "prompt_tokens": body.get("usage", {}).get("prompt_tokens"),
                        "completion_tokens": completion.completion_tokens,
                        "finish_reason": completion.finish_reason,
                        "cache_hit": completion.cache_hit,
                        "latency_s": completion.latency_s,
                        "timestamp": completion.timestamp,
                    }
                    write_json(response_path(paths, case), record)
                    logger.info(
                        "%s finish=%s cache_hit=%s",
                        case["case_id"],
                        completion.finish_reason,
                        completion.cache_hit,
                    )
                    progress.advance()
    existing = len(manifest["cases"]) - len(pending)
    print(f"Recorded {existing} existing, {len(pending)} new responses.")


@dataclass(frozen=True)
class _case_proxy:
    """Small adapter for the prior read-only raw-cache lookup."""

    case_id: str
    messages: list[Message]

    def __init__(self, case: dict, messages: list[Message]) -> None:
        object.__setattr__(self, "case_id", case["case_id"])
        object.__setattr__(self, "messages", messages)


def analyze(paths: DirectPaths) -> dict:
    manifest = prepare(paths)
    rows = []
    for case in manifest["cases"]:
        file = response_path(paths, case)
        if not file.exists():
            continue
        response = json.loads(file.read_text(encoding="utf-8"))
        if (
            response["case_id"] != case["case_id"]
            or response["input_sha256"] != case["input_sha256"]
        ):
            raise ValueError("Saved response does not match manifest.")
        rows.append(
            {
                **{
                    key: case[key]
                    for key in (
                        "case_id",
                        "model_role",
                        "control",
                        "interface",
                        "expected_k",
                        "expected_n",
                        "input_sha256",
                    )
                },
                **{
                    key: response[key]
                    for key in (
                        "raw_output",
                        "prompt_tokens",
                        "completion_tokens",
                        "finish_reason",
                        "cache_hit",
                    )
                },
                **analyze_response(
                    response["raw_output"],
                    case["expected_k"],
                    case["expected_n"],
                    response["finish_reason"],
                ),
            }
        )
    result = {"manifest_sha256": _hash_file(paths.data / "manifest.json"), "rows": rows}
    write_json(paths.data / "analysis.json", result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("prepare", "run", "analyze"))
    stage = parser.parse_args().stage
    paths = DirectPaths(Paths.discover().root, "smoke")
    if stage == "prepare":
        print(f"Prepared {len(prepare(paths)['cases'])} fixed cases.")
    elif stage == "run":
        run(paths)
    else:
        print(f"Analyzed {len(analyze(paths)['rows'])} responses.")


if __name__ == "__main__":
    main()
