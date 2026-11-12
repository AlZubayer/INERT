"""Isolated per-assertion oracle and frozen 48-call diagnostic runner."""

import argparse
import hashlib
import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from inert.audit import Progress, stage_log
from inert.config import Paths, load_config
from inert.diagnostic_assertion_resume import ordered_tests_sha256
from inert.diagnostic_direct_pass_count import DIRECT_COUNT, SYSTEM, _case_proxy
from inert.diagnostic_failure_isolation import _cached_api_body, input_hash
from inert.harness import render_harness
from inert.models import load_models, model_session, resolve_model
from inert.sandbox import DockerSandbox
from inert.schemas import Message, write_json

SELECTION_SHA256 = "3aed60838f4c44dc5a8fa76b0bcf858ffb37f5d8de5c5ab8d267d0a50add37eb"
SOURCE_SHA256 = "e76c93a8483f370dc9d684d295264175739940355df79fbe37ceddceedd24378"
AGGREGATE_SHA256 = "b180a21fe9640783f9429b2e1040a0a53b89ea7441a53610f9b9f84079d49cfe"
SELECTED_IDS = (
    "acq-mbpp-125-g06",
    "acq-mbpp-125-g07",
    "acq-mbpp-563-g00",
    "acq-mbpp-622-g00",
    "acq-mbpp-563-g10",
    "acq-mbpp-563-g13",
    "acq-mbpp-125-g00",
    "acq-mbpp-125-g01",
)
STAGES = ("A", "B", "C")
ROLES = ("wm_b", "wm_c")
READ_SYSTEM = (
    "You analyze supplied Python code and test assertions without executing code. "
    "Follow the requested output format exactly."
)
EXTRACT_INSTRUCTION = (
    "Copy the three original test assertion strings verbatim into a JSON array of exactly "
    "three strings in the same order. Use only the numbered Test assertions, not assertions "
    "inside solution.py. Return the JSON array only."
)
INDIVIDUAL_INSTRUCTION = (
    "Analyze the supplied Python solution and three original test assertions. Predict whether "
    "each test passes or fails when run with the supplied solution. Output exactly one line "
    "beginning with TEST_RESULTS:, followed by three comma-separated letters in original "
    "test order. Use P for PASS and F for FAIL. Do not output an explanation."
)


@dataclass(frozen=True)
class RunPaths(Paths):
    @property
    def data(self) -> Path:
        return self.root / "data/smoke/diagnostics/assertion_execution_20261112/run_48"


def _sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _fixed_write(path: Path, payload: dict) -> None:
    if path.exists():
        if json.loads(path.read_text(encoding="utf-8")) != payload:
            raise ValueError(f"Frozen assertion diagnostic artifact differs: {path}")
    else:
        write_json(path, payload)


def _selection(paths: RunPaths) -> tuple[list[dict], dict, dict]:
    base = paths.data.parent / "selection_resume"
    files = {
        name: base / name
        for name in ("selection_manifest.json", "source_archive.json", "oracle.json")
    }
    expected = {
        "selection_manifest.json": SELECTION_SHA256,
        "source_archive.json": SOURCE_SHA256,
        "oracle.json": AGGREGATE_SHA256,
    }
    if any(_sha256(file) != expected[name] for name, file in files.items()):
        raise ValueError("Frozen selection, source, or aggregate oracle checksum differs.")
    manifest = json.loads(files["selection_manifest.json"].read_text(encoding="utf-8"))
    source = json.loads(files["source_archive.json"].read_text(encoding="utf-8"))
    aggregate = json.loads(files["oracle.json"].read_text(encoding="utf-8"))
    selected, rows, truth = manifest["selected"], source["rows"], aggregate["rows"]
    if (
        len(selected) != 8
        or len(rows) != 8
        or len(truth) != 8
        or tuple(row["candidate_id"] for row in selected) != SELECTED_IDS
        or tuple(row["candidate_id"] for row in rows) != SELECTED_IDS
        or tuple(row["candidate_id"] for row in truth) != SELECTED_IDS
        or len({row["code_stripped_sha256"] for row in selected}) != 8
    ):
        raise ValueError("Frozen eight-candidate selection differs.")
    for selected_row, source_row, truth_row in zip(selected, rows, truth, strict=True):
        if (
            _text_hash(source_row["code_stripped"]) != selected_row["code_stripped_sha256"]
            or _text_hash(source_row["raw_source"]) != selected_row["raw_source_sha256"]
            or ordered_tests_sha256(source_row["tests"]) != selected_row["original_tests_sha256"]
            or len(source_row["tests"]) != 3
            or source_row["task_id"] != selected_row["task_id"]
            or truth_row["task_id"] != selected_row["task_id"]
            or truth_row["n_tests"] != 3
            or truth_row["recorded_stdout"] != f"RESULT: {truth_row['n_passed']}/3\n"
            or truth_row["aggregate_docker_recheck"]["stdout"] != truth_row["recorded_stdout"]
        ):
            raise ValueError(
                f"Frozen candidate/source/test truth differs: {source_row['candidate_id']}"
            )
        if {"n_passed", "outcome_stratum", "selection_rank"} & source_row.keys():
            raise ValueError("Model-facing source archive contains selection truth.")
    return rows, manifest, aggregate


def oracle_harness(tests: list[str], test_seconds: int) -> str:
    """Instrument the frozen harness semantics without executing on the host."""
    if len(tests) != 3 or test_seconds <= 0:
        raise ValueError("The diagnostic requires three tests and a positive timeout.")
    return f"""import json
import signal

TESTS = {tests!r}

class _Timeout(Exception):
    pass

def _handler(signum, frame):
    raise _Timeout()

def main():
    try:
        import solution
        namespace = dict(vars(solution))
    except BaseException as exc:
        payload = {{
            "load_status": "import_failure",
            "import_exception": type(exc).__name__,
            "test_results": [],
            "harness_equivalent_vector": ["F"] * len(TESTS),
        }}
        print("ORACLE_JSON:" + json.dumps(payload))
        return
    signal.signal(signal.SIGALRM, _handler)
    outcomes = []
    for test in TESTS:
        try:
            signal.alarm({test_seconds})
            exec(test, dict(namespace))
            outcomes.append({{"status": "PASS", "exception_type": None}})
        except _Timeout:
            outcomes.append({{"status": "TIMEOUT", "exception_type": "_Timeout"}})
        except AssertionError:
            outcomes.append({{"status": "ASSERTION_FAIL", "exception_type": "AssertionError"}})
        except BaseException as exc:
            outcomes.append({{"status": "OTHER_EXCEPTION", "exception_type": type(exc).__name__}})
        finally:
            signal.alarm(0)
    payload = {{
        "load_status": "ok",
        "import_exception": None,
        "test_results": outcomes,
        "harness_equivalent_vector": [
            "P" if row["status"] == "PASS" else "F" for row in outcomes
        ],
    }}
    print("ORACLE_JSON:" + json.dumps(payload))

if __name__ == "__main__":
    main()
"""


def parse_oracle(raw: str, returncode: int, stderr: str) -> dict:
    if returncode or stderr or not raw.startswith("ORACLE_JSON:") or raw.count("\n") != 1:
        raise ValueError("Per-assertion Docker oracle did not return one valid line.")
    record = json.loads(raw.removeprefix("ORACLE_JSON:").strip())
    if record["load_status"] == "import_failure":
        if record["test_results"] or record["harness_equivalent_vector"] != ["F"] * 3:
            raise ValueError("Import failure incorrectly claims executed tests.")
    elif record["load_status"] == "ok":
        if len(record["test_results"]) != 3 or record["harness_equivalent_vector"] != [
            "P" if row["status"] == "PASS" else "F" for row in record["test_results"]
        ]:
            raise ValueError("Per-test outcome vector is incomplete or inconsistent.")
        if any(
            row["status"] not in ("PASS", "ASSERTION_FAIL", "OTHER_EXCEPTION", "TIMEOUT")
            for row in record["test_results"]
        ):
            raise ValueError("Unknown per-test outcome status.")
    else:
        raise ValueError("Unknown oracle load status.")
    return record


def build_oracle(paths: RunPaths) -> dict:
    rows, _, aggregate = _selection(paths)
    target = paths.data / "per_assertion_oracle.json"
    if target.exists():
        saved = json.loads(target.read_text(encoding="utf-8"))
        if (
            saved["selection_manifest_sha256"] != SELECTION_SHA256
            or saved["source_archive_sha256"] != SOURCE_SHA256
            or len(saved["rows"]) != 8
            or [row["candidate_id"] for row in saved["rows"]] != list(SELECTED_IDS)
        ):
            raise ValueError("Saved per-assertion oracle differs from frozen selection.")
        return saved
    config = load_config(paths)
    sandbox = DockerSandbox(paths, config["sandbox"])
    truth = {row["candidate_id"]: row for row in aggregate["rows"]}
    output = []
    for source in rows:
        identifier = source["candidate_id"]
        code, tests = source["code_stripped"], source["tests"]
        detail = sandbox.run(
            code, oracle_harness(tests, config["sandbox"]["test_seconds"]), use_cache=False
        )
        parsed = parse_oracle(detail.stdout, detail.returncode, detail.stderr)
        aggregate_result = sandbox.run(code, render_harness(tests), use_cache=False)
        actual_count = parsed["harness_equivalent_vector"].count("P")
        expected = truth[identifier]
        if (
            actual_count != expected["n_passed"]
            or aggregate_result.stdout != expected["recorded_stdout"]
            or aggregate_result.returncode != 0
            or aggregate_result.stderr
        ):
            discrepancy = {
                "candidate_id": identifier,
                "per_assertion": parsed,
                "aggregate_stdout": aggregate_result.stdout,
                "aggregate_returncode": aggregate_result.returncode,
                "aggregate_stderr": aggregate_result.stderr,
                "frozen_truth": expected,
            }
            write_json(paths.data / "oracle_discrepancy.json", discrepancy)
            raise ValueError(f"Per-assertion oracle disagrees with frozen truth: {identifier}")
        output.append(
            {
                "candidate_id": identifier,
                "task_id": source["task_id"],
                "code_sha256": _text_hash(code),
                "tests_sha256": ordered_tests_sha256(tests),
                "load_status": parsed["load_status"],
                "import_exception": parsed["import_exception"],
                "test_results": parsed["test_results"],
                "vector": parsed["harness_equivalent_vector"],
                "n_passed": actual_count,
                "detailed_stdout": detail.stdout,
                "aggregate_stdout": aggregate_result.stdout,
                "aggregate_returncode": aggregate_result.returncode,
            }
        )
    oracle = {
        "selection_manifest_sha256": SELECTION_SHA256,
        "source_archive_sha256": SOURCE_SHA256,
        "frozen_aggregate_oracle_sha256": AGGREGATE_SHA256,
        "docker_image_id": sandbox.image_id,
        "sandbox_config": config["sandbox"],
        "rows": output,
    }
    _fixed_write(target, oracle)
    return oracle


def _messages(stage: str, code: str, tests: list[str]) -> list[Message]:
    """Render from source content only; no execution-truth arguments exist."""
    if stage not in STAGES or len(tests) != 3:
        raise ValueError("Unexpected stage or test count.")
    user = (
        "solution.py:\n```python\n"
        + code
        + "\n```\n\nTest assertions:\n"
        + "\n".join(f"{index}. {test}" for index, test in enumerate(tests, 1))
        + "\n\n"
    )
    if stage == "A":
        return [
            Message(role="system", content=READ_SYSTEM),
            Message(role="user", content=user + EXTRACT_INSTRUCTION),
        ]
    if stage == "B":
        return [
            Message(role="system", content=READ_SYSTEM),
            Message(role="user", content=user + INDIVIDUAL_INSTRUCTION),
        ]
    return [
        Message(role="system", content=SYSTEM),
        Message(role="user", content=user + DIRECT_COUNT),
    ]


def build_cases(source_rows: list[dict]) -> list[dict]:
    """Freeze 48 independent prompts without reading oracle or selection truth."""
    if len(source_rows) != 8 or tuple(row["candidate_id"] for row in source_rows) != SELECTED_IDS:
        raise ValueError("Source archive does not match the fixed candidate order.")
    cases = []
    for stage in STAGES:
        for role in ROLES:
            for source in source_rows:
                messages = _messages(stage, source["code_stripped"], source["tests"])
                cases.append(
                    {
                        "case_id": f"{stage}-{role}-{source['candidate_id']}",
                        "stage": stage,
                        "model_role": role,
                        "candidate_id": source["candidate_id"],
                        "task_id": source["task_id"],
                        "code_sha256": _text_hash(source["code_stripped"]),
                        "tests_sha256": ordered_tests_sha256(source["tests"]),
                        "messages": [message.model_dump() for message in messages],
                        "input_sha256": input_hash(messages),
                    }
                )
    if len(cases) != 48 or len({case["case_id"] for case in cases}) != 48:
        raise ValueError("The fixed diagnostic does not contain 48 unique calls.")
    return cases


def prepare(paths: RunPaths) -> dict:
    source_rows, _, _ = _selection(paths)
    if not (paths.data / "per_assertion_oracle.json").exists():
        raise ValueError("Per-assertion Docker oracle must pass before inference preparation.")
    oracle = build_oracle(paths)
    if any(row["n_passed"] != row["vector"].count("P") for row in oracle["rows"]):
        raise ValueError("Per-assertion oracle count disagrees with its vector.")
    config = load_config(paths)
    if (
        config["sampling"]["wm"]
        != {"temperature": 0.0, "top_p": 1.0, "max_tokens": 1024, "seed": 0}
        or config["server"]["context_size"] != 8192
    ):
        raise ValueError("Frozen model sampling or context differs.")
    registry = load_models(paths)
    models = {}
    for role in ROLES:
        model = registry["models"][role]
        if model["license"] != "apache-2.0":
            raise ValueError(f"Unexpected model license: {role}")
        resolved = resolve_model(paths, model, "Q4_K_M")
        models[role] = {
            "source": model["source"],
            "source_revision": model["source_revision"],
            "gguf_revision": model["gguf_revision"],
            "license": model["license"],
            "resolved_identity": resolved.sha256,
            "files": [
                {
                    "path": path.relative_to(paths.root).as_posix(),
                    "sha256": _sha256(path),
                    "size_bytes": path.stat().st_size,
                }
                for path in resolved.files
            ],
        }
    server = paths.root / registry["serving"]["executable"]
    version = subprocess.run([str(server), "--version"], capture_output=True, text=True, timeout=20)
    manifest = {
        "protocol": "Frozen assertion-reading and execution-reasoning diagnostic",
        "selection_manifest_sha256": SELECTION_SHA256,
        "source_archive_sha256": SOURCE_SHA256,
        "aggregate_oracle_sha256": AGGREGATE_SHA256,
        "per_assertion_oracle_sha256": _sha256(paths.data / "per_assertion_oracle.json"),
        "sampling": config["sampling"]["wm"],
        "context_size": config["server"]["context_size"],
        "server": {
            "path": server.relative_to(paths.root).as_posix(),
            "sha256": _sha256(server),
            "configured_build": registry["serving"]["build"],
            "configured_commit": registry["serving"]["commit"],
            "version_stdout": version.stdout,
            "version_stderr": version.stderr,
            "version_returncode": version.returncode,
        },
        "models": models,
        "cases": build_cases(source_rows),
    }
    serialized = json.dumps(manifest, ensure_ascii=False)
    if any(marker in serialized for marker in ('"n_passed"', '"outcome_stratum"', '"expected_k"')):
        raise ValueError("Inference manifest contains Docker truth labels.")
    _fixed_write(paths.data / "manifest.json", manifest)
    return manifest


def response_path(paths: RunPaths, case: dict) -> Path:
    if not re.fullmatch(r"[A-Za-z0-9_-]+", case["case_id"]):
        raise ValueError("Unsafe case ID.")
    return paths.data / "responses" / f"{case['case_id']}.json"


def run(paths: RunPaths) -> None:
    manifest = prepare(paths)
    params = manifest["sampling"]
    for case in manifest["cases"]:
        path = response_path(paths, case)
        if path.exists():
            old = json.loads(path.read_text(encoding="utf-8"))
            if old["case_id"] != case["case_id"] or old["input_sha256"] != case["input_sha256"]:
                raise ValueError(f"Saved response does not match fixed prompt: {path}")
    pending = [case for case in manifest["cases"] if not response_path(paths, case).exists()]
    progress = Progress(len(pending)) if pending else None
    with stage_log(paths, "assertion-execution-run") as logger:
        for stage in STAGES:
            for role in ROLES:
                group = [
                    case
                    for case in pending
                    if case["stage"] == stage and case["model_role"] == role
                ]
                if not group:
                    continue
                with model_session(paths, load_config(paths), role) as client:
                    for case in group:
                        messages = [Message.model_validate(value) for value in case["messages"]]
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
                        _fixed_write(response_path(paths, case), record)
                        logger.info("%s finish=%s", case["case_id"], completion.finish_reason)
                        if progress is not None:
                            progress.advance()
    print(
        f"Recorded {len(manifest['cases']) - len(pending)} existing and {len(pending)} new calls."
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("oracle", "prepare", "run"))
    stage = parser.parse_args().stage
    paths = RunPaths(Paths.discover().root, "smoke")
    if stage == "oracle":
        result = build_oracle(paths)
        print(f"Verified {len(result['rows'])} per-assertion vectors in Docker.")
    elif stage == "prepare":
        result = prepare(paths)
        digest = _sha256(paths.data / "manifest.json")
        print(f"Froze {len(result['cases'])} model requests; SHA-256 {digest}.")
    else:
        run(paths)


if __name__ == "__main__":
    main()
