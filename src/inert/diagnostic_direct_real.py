"""Fixed direct-interface diagnostic on four real Docker-executed candidates."""

import argparse
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path

from inert.audit import Progress, stage_log
from inert.config import Paths, load_config
from inert.diagnostic_direct_pass_count import (
    DIRECT_COUNT,
    FIXED_DENOMINATOR,
    SYSTEM,
    _case_proxy,
    _hash_file,
    analyze_response,
)
from inert.diagnostic_failure_isolation import (
    SELECTION,
    TRUTH,
    Case,
    Response,
    _cached_api_body,
    input_hash,
)
from inert.diagnostic_inhouse import classify_output
from inert.harness import render_harness
from inert.models import load_models, model_session, resolve_model
from inert.sandbox import DockerSandbox
from inert.schemas import Candidate, Message, Task, read_jsonl, write_json

ROOT_NAME = "direct_real_candidates_20261112"
PRIOR_DIRECT_SHA256 = "77f74e1283ff10236e71beb8e1c3c0d7f8ac929312cabee5b45a32c8b7c4b5d9"


@dataclass(frozen=True)
class RealPaths(Paths):
    @property
    def data(self) -> Path:
        return self.root / "data" / "smoke" / "diagnostics" / ROOT_NAME


def _source_records(paths: Paths) -> tuple[dict[str, Task], dict[str, Candidate]]:
    source = Paths(paths.root, "smoke")
    tasks = {task.task_id: task for task in read_jsonl(source.tasks, Task)}
    candidates = {
        candidate.cand_id: candidate for candidate in read_jsonl(source.candidates, Candidate)
    }
    return tasks, candidates


def _prior_templates(paths: Paths) -> dict[str, dict]:
    previous = paths.root / "data/smoke/diagnostics/direct_pass_count_20261112/manifest.json"
    if _hash_file(previous) != PRIOR_DIRECT_SHA256:
        raise ValueError("Prior direct-interface manifest hash changed.")
    old = json.loads(previous.read_text(encoding="utf-8"))
    cases = {
        case["interface"]: case
        for case in old["cases"]
        if case["model_role"] == "wm_c" and case["control"] == "C0"
    }
    if set(cases) != {"DIRECT_COUNT", "FIXED_DENOMINATOR"}:
        raise ValueError("Prior direct-interface templates missing.")
    for interface, final in (
        ("DIRECT_COUNT", DIRECT_COUNT),
        ("FIXED_DENOMINATOR", FIXED_DENOMINATOR),
    ):
        case = cases[interface]
        if case["messages"][0] != Message(role="system", content=SYSTEM).model_dump():
            raise ValueError("Prior system instruction changed.")
        if not case["messages"][1]["content"].endswith(final):
            raise ValueError("Prior final instruction changed.")
    return cases


def _render_from_template(template: dict, code: str, tests: list[str]) -> list[Message]:
    old_source = template["source_code"]
    old_tests = template["tests"]
    old_code_block = f"solution.py:\n```python\n{old_source}\n```"
    old_test_block = "Test assertions:\n" + "\n".join(
        f"{index}. {test}" for index, test in enumerate(old_tests, 1)
    )
    content = template["messages"][1]["content"]
    if content.count(old_code_block) != 1 or content.count(old_test_block) != 1:
        raise ValueError("Prior direct prompt structure changed.")
    new_code_block = f"solution.py:\n```python\n{code}\n```"
    new_test_block = "Test assertions:\n" + "\n".join(
        f"{index}. {test}" for index, test in enumerate(tests, 1)
    )
    user = content.replace(old_code_block, new_code_block, 1).replace(
        old_test_block, new_test_block, 1
    )
    return [Message(role="system", content=SYSTEM), Message(role="user", content=user)]


def _prior_real_cases(paths: Paths) -> dict[tuple[str, str], Case]:
    previous = paths.root / "data/smoke/diagnostics/failure_isolation_20261112/manifest.json"
    old = json.loads(previous.read_text(encoding="utf-8"))
    result = {}
    for raw in old["cases"]:
        if raw["stage"] not in ("D", "E") or raw["condition"] != "T0":
            continue
        case = Case.model_validate(raw)
        key = (case.model_role, case.candidate_id)
        if key not in result:
            result[key] = case
        elif result[key].source_code != case.source_code or result[key].tests != case.tests:
            raise ValueError("Historical source/test mismatch across channels or families.")
    if set(result) != {(role, identifier) for role in ("wm_c", "wm_b") for identifier in SELECTION}:
        raise ValueError("Historical T0 candidate matrix incomplete.")
    return result


def build_cases(paths: Paths) -> list[dict]:
    tasks, candidates = _source_records(paths)
    templates = _prior_templates(paths)
    historical = _prior_real_cases(paths)
    output = []
    for candidate_id in SELECTION:
        candidate = candidates[candidate_id]
        task = tasks[candidate.task_id]
        if (
            candidate.n_passed != TRUTH[candidate_id]
            or candidate.n_tests != 3
            or task.n_tests != 3
            or candidate.harness_output != f"RESULT: {TRUTH[candidate_id]}/3\n"
            or not candidate.in_core_set
        ):
            raise ValueError(f"Fixed candidate or Docker truth changed: {candidate_id}")
        code = candidate.code_stripped
        tests = task.tests
        code_sha = hashlib.sha256(code.encode()).hexdigest()
        test_sha = hashlib.sha256(json.dumps(tests, ensure_ascii=False).encode()).hexdigest()
        harness_sha = hashlib.sha256(render_harness(tests).encode()).hexdigest()
        if code_sha != candidate.code_sha256:
            raise ValueError(f"Candidate code hash mismatch: {candidate_id}")
        for role in ("wm_c", "wm_b"):
            prior = historical[(role, candidate_id)]
            if (
                prior.source_code != code
                or prior.tests != tests
                or prior.expected_k != candidate.n_passed
                or prior.expected_n != 3
            ):
                raise ValueError(f"Prior failure-isolation input differs: {candidate_id}")
            for interface in ("DIRECT_COUNT", "FIXED_DENOMINATOR"):
                messages = _render_from_template(templates[interface], code, tests)
                if f"RESULT: {candidate.n_passed}/3" in messages[1].content:
                    raise ValueError("Docker ground truth leaked into diagnostic prompt.")
                output.append(
                    {
                        "case_id": f"{role}-{candidate_id}-{interface}",
                        "model_role": role,
                        "candidate_id": candidate_id,
                        "task_id": task.task_id,
                        "condition": "T0",
                        "interface": interface,
                        "source_code": code,
                        "tests": tests,
                        "code_sha256": code_sha,
                        "test_sha256": test_sha,
                        "harness_sha256": harness_sha,
                        "expected_k": candidate.n_passed,
                        "expected_n": 3,
                        "docker_stdout": candidate.harness_output,
                        "messages": [message.model_dump() for message in messages],
                        "input_sha256": input_hash(messages),
                    }
                )
    if len(output) != 16 or len({case["case_id"] for case in output}) != 16:
        raise ValueError("Real direct diagnostic matrix is not 16 unique calls.")
    return output


def historical_t0(paths: RealPaths) -> list[dict]:
    """Pair every old T0 response to its fixed manifest input and analysis row."""
    old_dir = paths.root / "data/smoke/diagnostics/failure_isolation_20261112"
    manifest = json.loads((old_dir / "manifest.json").read_text(encoding="utf-8"))
    analysis = json.loads((old_dir / "analysis.json").read_text(encoding="utf-8"))
    rows = {row["case_id"]: row for row in analysis["rows"]}
    new = {
        (case["model_role"], case["candidate_id"]): case
        for case in build_cases(paths)
        if case["interface"] == "DIRECT_COUNT"
    }
    result = []
    for raw in manifest["cases"]:
        if raw["stage"] not in ("D", "E") or raw["condition"] != "T0":
            continue
        case = Case.model_validate(raw)
        expected = new[(case.model_role, case.candidate_id)]
        if (
            case.source_code != expected["source_code"]
            or case.tests != expected["tests"]
            or case.expected_k != expected["expected_k"]
            or case.expected_n != expected["expected_n"]
            or input_hash(case.messages) != case.input_sha256
        ):
            raise ValueError("Historical T0 input does not match real candidate.")
        file = old_dir / "responses" / case.stage / f"{case.case_id}.json"
        response = Response.model_validate_json(file.read_text(encoding="utf-8"))
        prior_row = rows[case.case_id]
        if (
            response.case_id != case.case_id
            or response.input_sha256 != case.input_sha256
            or response.raw_output != prior_row["raw_output"]
        ):
            raise ValueError("Historical T0 response does not match its input or analysis.")
        evaluation = analyze_response(
            response.raw_output, case.expected_k, 3, response.finish_reason
        )
        result.append(
            {
                "case_id": case.case_id,
                "model_role": case.model_role,
                "candidate_id": case.candidate_id,
                "condition": case.condition,
                "channel": case.channel,
                "family": case.family,
                "input_sha256": case.input_sha256,
                "raw_output": response.raw_output,
                "completion_tokens": response.completion_tokens,
                "finish_reason": response.finish_reason,
                **evaluation,
            }
        )
    if len(result) != 32 or len({row["case_id"] for row in result}) != 32:
        raise ValueError("Historical T0 response matrix incomplete.")
    return result


def prepare(paths: RealPaths) -> dict:
    config = load_config(Paths(paths.root, "smoke"))
    sampling = config["sampling"]["wm"]
    if sampling != {"temperature": 0.0, "top_p": 1.0, "max_tokens": 1024, "seed": 0}:
        raise ValueError("Frozen WM sampling changed.")
    if config["server"]["context_size"] != 8192:
        raise ValueError("Frozen WM context changed.")
    registry = load_models(paths)
    old_direct = paths.root / "data/smoke/diagnostics/direct_pass_count_20261112/manifest.json"
    old_failure = paths.root / "data/smoke/diagnostics/failure_isolation_20261112"
    prior_models = json.loads(old_direct.read_text(encoding="utf-8"))["models"]
    models = {}
    for role in ("wm_c", "wm_b"):
        resolved = resolve_model(paths, registry["models"][role], "Q4_K_M")
        if resolved.sha256 != prior_models[role]["resolved_identity"]:
            raise ValueError(f"Pinned model identity changed: {role}")
        models[role] = {
            **prior_models[role],
            "files": [
                {
                    "path": str(path.relative_to(paths.root)).replace("\\", "/"),
                    "sha256": _hash_file(path),
                    "size_bytes": path.stat().st_size,
                }
                for path in resolved.files
            ],
        }
        if models[role]["files"] != prior_models[role]["files"]:
            raise ValueError(f"Pinned model file changed: {role}")
    server = paths.root / registry["serving"]["executable"]
    manifest = {
        "base_commit": "8e4d8f73c3696abf176c326104b4201efa841310",
        "protocol": "Real-Candidate Direct Pass-Count Diagnostic, 2026-11-12",
        "sampling": sampling,
        "context_size": 8192,
        "server": {
            "executable": str(server.relative_to(paths.root)).replace("\\", "/"),
            "sha256": _hash_file(server),
            "build": registry["serving"]["build"],
            "commit": registry["serving"]["commit"],
        },
        "models": models,
        "source_sha256": {
            str(file.relative_to(paths.root)).replace("\\", "/"): _hash_file(file)
            for file in (
                paths.root / "data/smoke/tasks.jsonl",
                paths.root / "data/smoke/candidates.jsonl",
                old_direct,
                old_failure / "manifest.json",
                old_failure / "analysis.json",
            )
        },
        "cases": build_cases(paths),
    }
    target = paths.data / "manifest.json"
    if target.exists():
        if json.loads(target.read_text(encoding="utf-8")) != manifest:
            raise ValueError("Fixed real-candidate manifest differs; refusing overwrite.")
    else:
        write_json(target, manifest)
    return manifest


def verify_docker(paths: RealPaths) -> dict:
    manifest = prepare(paths)
    truth_path = paths.data / "docker_truth.json"
    expected = {
        case["candidate_id"]: case
        for case in manifest["cases"]
        if case["model_role"] == "wm_c" and case["interface"] == "DIRECT_COUNT"
    }
    if truth_path.exists():
        prior = json.loads(truth_path.read_text(encoding="utf-8"))
        if set(prior) != set(expected) or any(
            prior[identifier]["stdout"] != case["docker_stdout"]
            or prior[identifier]["code_sha256"] != case["code_sha256"]
            or prior[identifier]["harness_sha256"] != case["harness_sha256"]
            or prior[identifier]["returncode"] != 0
            for identifier, case in expected.items()
        ):
            raise ValueError("Saved Docker verification differs from fixed manifest.")
        return prior
    sandbox = DockerSandbox(paths, load_config(paths)["sandbox"])
    truth = {}
    for identifier, case in expected.items():
        result = sandbox.run(case["source_code"], render_harness(case["tests"]), use_cache=False)
        if result.returncode != 0 or result.stdout != case["docker_stdout"] or result.stderr:
            raise ValueError(f"Docker result disagrees with fixed truth: {identifier}: {result}")
        truth[identifier] = {
            "code_sha256": case["code_sha256"],
            "test_sha256": case["test_sha256"],
            "harness_sha256": case["harness_sha256"],
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode,
        }
    write_json(truth_path, truth)
    return truth


def response_path(paths: RealPaths, case: dict) -> Path:
    if not re.fullmatch(r"[A-Za-z0-9_-]+", case["case_id"]):
        raise ValueError("Unsafe diagnostic case ID.")
    return paths.data / "responses" / f"{case['case_id']}.json"


def run(paths: RealPaths) -> None:
    manifest = prepare(paths)
    verify_docker(paths)
    config = load_config(paths)
    params = config["sampling"]["wm"]
    pending = []
    for case in manifest["cases"]:
        file = response_path(paths, case)
        if file.exists():
            saved = json.loads(file.read_text(encoding="utf-8"))
            if saved["case_id"] != case["case_id"] or saved["input_sha256"] != case["input_sha256"]:
                raise ValueError("Existing response does not match the fixed input.")
        else:
            pending.append(case)
    progress = Progress(len(pending)) if pending else None
    with stage_log(paths, "direct-real-candidates") as logger:
        for role in ("wm_c", "wm_b"):
            group = [case for case in pending if case["model_role"] == role]
            if not group:
                continue
            with model_session(paths, config, role) as client:
                for case in group:
                    messages = [Message.model_validate(message) for message in case["messages"]]
                    completion = client.complete(messages, params)
                    body = _cached_api_body(client, _case_proxy(case, messages), params)
                    write_json(
                        response_path(paths, case),
                        {
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
                        },
                    )
                    logger.info(
                        "%s finish=%s cache_hit=%s",
                        case["case_id"],
                        completion.finish_reason,
                        completion.cache_hit,
                    )
                    progress.advance()
    print(
        f"Completed {len(manifest['cases']) - len(pending)} existing and {len(pending)} new calls."
    )


def analyze(paths: RealPaths) -> dict:
    manifest = prepare(paths)
    verify_docker(paths)
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
            raise ValueError("Response differs from fixed input.")
        evaluation = analyze_response(
            response["raw_output"],
            case["expected_k"],
            case["expected_n"],
            response["finish_reason"],
        )
        categories = classify_output(
            response["raw_output"],
            evaluation["parser_status"],
            evaluation["n_pred"],
            case["expected_n"],
            response["finish_reason"],
        )
        rows.append(
            {
                **{
                    key: case[key]
                    for key in (
                        "case_id",
                        "model_role",
                        "candidate_id",
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
                **evaluation,
                "categories": categories,
            }
        )
    result = {
        "manifest_sha256": _hash_file(paths.data / "manifest.json"),
        "docker_truth_sha256": _hash_file(paths.data / "docker_truth.json"),
        "rows": rows,
        "historical_t0": historical_t0(paths),
    }
    write_json(paths.data / "analysis.json", result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("prepare", "verify-docker", "run", "analyze"))
    stage = parser.parse_args().stage
    paths = RealPaths(Paths.discover().root, "smoke")
    if stage == "prepare":
        print(f"Prepared {len(prepare(paths)['cases'])} fixed calls.")
    elif stage == "verify-docker":
        print(f"Verified {len(verify_docker(paths))} Docker ground-truth results.")
    elif stage == "run":
        run(paths)
    else:
        print(f"Analyzed {len(analyze(paths)['rows'])} responses.")


if __name__ == "__main__":
    main()
