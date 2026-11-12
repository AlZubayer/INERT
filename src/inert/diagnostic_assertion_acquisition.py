"""Isolated, fixed-budget acquisition of fresh 1/3 MBPP candidates."""

import argparse
import hashlib
import json
import random
import re
from dataclasses import dataclass
from pathlib import Path

from inert.audit import Progress, stage_log
from inert.config import Paths, load_config
from inert.diagnostic_direct_pass_count import _case_proxy, _hash_file
from inert.diagnostic_failure_isolation import _cached_api_body, input_hash
from inert.harness import render_harness
from inert.models import load_models, model_session, resolve_model
from inert.proposer import _messages, extract_code
from inert.sandbox import DockerSandbox, SandboxError, SandboxSetupError
from inert.schemas import Candidate, Message, Task, read_jsonl, write_json, write_jsonl
from inert.tasks import CpuTokenizer, _needs_external_state, normalize_mbpp, task_token_text
from inert.verification import load_mbpp

ROOT_NAME = "assertion_candidate_acquisition_20261112"
TASK_SEED = 20261111
MAX_TASKS = 8
ATTEMPTS_PER_TASK = 16
PREVIOUS_AUDIT_SHA256 = "6def12845d6b69f9179efd649d34d0ac79ac2934df50cd26ed3219f6c4ad2845"


@dataclass(frozen=True)
class AcquisitionPaths(Paths):
    @property
    def data(self) -> Path:
        return self.root / "data" / "smoke" / "diagnostics" / ROOT_NAME


def select_task_ids(eligible_ids: list[str], maximum: int = MAX_TASKS) -> list[str]:
    """The approved sort, fixed-seed shuffle, and first-eight rule."""
    ordered = sorted(eligible_ids)
    if len(ordered) != len(set(ordered)):
        raise ValueError("Duplicate eligible task ID.")
    random.Random(TASK_SEED).shuffle(ordered)
    return ordered[:maximum]


def attempt_plan(task_ids: list[str]) -> list[dict]:
    if len(task_ids) > MAX_TASKS:
        raise ValueError("Acquisition exceeds eight tasks.")
    return [
        {
            "task_id": task_id,
            "task_index": task_index,
            "gen_index": k,
            "seed": 1000 + task_index * 100 + k,
            "candidate_id": f"acq-{task_id}-g{k:02}",
        }
        for task_index, task_id in enumerate(task_ids)
        for k in range(ATTEMPTS_PER_TASK)
    ]


def classify_result(stdout: str, returncode: int) -> int | None:
    if returncode != 0 or not re.fullmatch(r"RESULT: [0-3]/3\n", stdout):
        return None
    return int(stdout[8])


def choose_shortlist(qualifying: list[dict], task_order: list[str]) -> list[dict]:
    """Prefer distinct tasks, then earliest task and generation index."""
    rank = {task_id: index for index, task_id in enumerate(task_order)}
    ordered = sorted(qualifying, key=lambda row: (rank[row["task_id"]], row["gen_index"]))
    distinct = []
    seen_tasks, seen_hashes = set(), set()
    for row in ordered:
        if row["task_id"] not in seen_tasks and row["code_sha256"] not in seen_hashes:
            distinct.append(row)
            seen_tasks.add(row["task_id"])
            seen_hashes.add(row["code_sha256"])
        if len(distinct) == 2:
            return distinct
    if not distinct:
        return []
    for row in ordered:
        if row["code_sha256"] not in seen_hashes:
            distinct.append(row)
            break
    return distinct


def has_diverse_pair(qualifying: list[dict]) -> bool:
    """The acquisition may stop only after a complete batch contains two tasks."""
    return len(qualifying) >= 2 and len({row["task_id"] for row in qualifying}) >= 2


def freshness_status(
    candidate_id: str,
    code_sha256: str,
    prior_ids: set[str],
    prior_hashes: set[str],
) -> dict[str, bool]:
    """Compare both namespaced ID and stripped code against prior inference pool."""
    id_overlap = candidate_id in prior_ids
    hash_overlap = code_sha256 in prior_hashes
    return {
        "candidate_id_overlap": id_overlap,
        "code_sha256_overlap": hash_overlap,
        "fresh": not (id_overlap or hash_overlap),
    }


def _fixed_write(path: Path, payload: dict) -> None:
    if path.exists():
        if json.loads(path.read_text(encoding="utf-8")) != payload:
            raise ValueError(f"Frozen acquisition artifact differs: {path}")
    else:
        write_json(path, payload)


def _load_prior_audit(paths: AcquisitionPaths) -> dict:
    path = paths.root / "data/smoke/diagnostics/assertion_execution_20261112/selection_audit.json"
    if _hash_file(path) != PREVIOUS_AUDIT_SHA256:
        raise ValueError("Previous selection audit changed.")
    return json.loads(path.read_text(encoding="utf-8"))


def prepare(paths: AcquisitionPaths) -> dict:
    """Freeze all task choices and 128 possible requests before inference."""
    source = Paths(paths.root)
    smoke = Paths(paths.root, "smoke")
    config, registry = load_config(smoke), load_models(source)
    if (
        registry["dataset"]["id"] != "google-research-datasets/mbpp"
        or registry["dataset"]["config"] != "sanitized"
    ):
        raise ValueError("Pinned MBPP dataset differs from protocol.")
    if (
        config["sampling"]["proposer"]
        != {
            "temperature": 0.8,
            "top_p": 0.95,
            "max_tokens": 768,
            "seed_base": 1000,
            "task_stride": 100,
        }
        or config["server"]["context_size"] != 8192
        or config["candidates"]["per_task"] != 16
        or config["tasks"]["seed"] != TASK_SEED
        or config["tasks"]["max_tokens"] != 1500
    ):
        raise ValueError("Frozen task, generation, or context settings changed.")
    proposer = registry["models"]["proposer"]
    resolved = resolve_model(source, proposer, "Q4_K_M")
    prior_audit = _load_prior_audit(paths)
    old_tasks = {row["task_id"] for row in prior_audit["pool"]}
    old_tasks.update(task.task_id for task in read_jsonl(smoke.tasks, Task))
    pilot_tasks = {task.task_id for task in read_jsonl(source.tasks, Task)}
    dataset = load_mbpp(source, registry, offline=True)
    rows = sorted(
        [row for split in dataset.values() for row in split], key=lambda row: row["task_id"]
    )
    old_filter_path = smoke.data / "task_filter.json"
    old_filter = json.loads(old_filter_path.read_text(encoding="utf-8"))
    tasks, checks = {}, []
    for row in rows:
        task = normalize_mbpp(row)
        key = hashlib.sha256(
            (
                task.model_dump_json()
                + json.dumps(config["tasks"], sort_keys=True)
                + json.dumps(config["sandbox"], sort_keys=True)
                + config["tokenizer"]["model"]
            ).encode()
        ).hexdigest()
        cached = old_filter.get(key)
        if cached is None or cached["task_id"] != task.task_id:
            raise ValueError(
                f"Missing hash-matched existing token/Docker task filter: {task.task_id}"
            )
        reason = (
            "not_exactly_three_assertions"
            if task.n_tests != 3
            else "network_files_or_randomness"
            if _needs_external_state(task)
            else cached.get("reason")
            if not cached["kept"]
            else "previous_smoke_or_diagnostic_task"
            if task.task_id in old_tasks
            else None
        )
        if reason is None:
            if cached["reference_stdout"] != "RESULT: 3/3\n":
                raise ValueError(f"Reference Docker evidence missing: {task.task_id}")
            tasks[task.task_id] = task
        checks.append(
            {
                "task_id": task.task_id,
                "task_sha256": hashlib.sha256(task.model_dump_json().encode()).hexdigest(),
                "filter_key": key,
                "n_tests": task.n_tests,
                "reason": reason,
                "pilot_sample_overlap": task.task_id in pilot_tasks,
            }
        )
    selected_ids = select_task_ids(list(tasks))
    audit = {
        "dataset": {
            "id": registry["dataset"]["id"],
            "config": registry["dataset"]["config"],
            "revision": registry["dataset"]["revision"],
        },
        "dataset_files": [
            {"filename": entry["filename"], "sha256": entry["sha256"]}
            for entry in registry["dataset"]["files"]
        ],
        "source_task_filter_sha256": _hash_file(old_filter_path),
        "prior_selection_audit_sha256": PREVIOUS_AUDIT_SHA256,
        "seed": TASK_SEED,
        "rules": (
            "exactly three original tests; reference 3/3 in Docker; "
            "approved safety and strict <1500 Coder-token filter; unused task"
        ),
        "complete_eligible_ids_sorted": sorted(tasks),
        "checks": checks,
        "selected_ids": selected_ids,
    }
    _fixed_write(paths.data / "task_eligibility_audit.json", audit)
    if len(selected_ids) != MAX_TASKS:
        return {"status": "BLOCKED_TASK_SELECTION", "audit": audit}
    tokenizer = CpuTokenizer(source, config)
    selected = []
    for task_id in selected_ids:
        task = tasks[task_id]
        token_count = tokenizer(task_token_text(task))
        if token_count >= 1500:
            raise ValueError(f"Selected task exceeds verified token filter: {task_id}")
        selected.append(
            {
                "task": task.model_dump(),
                "task_sha256": hashlib.sha256(task.model_dump_json().encode()).hexdigest(),
                "token_count": token_count,
                "prior_filter_key": next(
                    check["filter_key"] for check in checks if check["task_id"] == task_id
                ),
            }
        )
    selection = {
        "base_commit": "499503473de82b50577e405f135e4530771a96e8",
        "seed": TASK_SEED,
        "ordering_rule": "sort task_id, random.Random(20261111).shuffle, take first eight",
        "task_eligibility_audit_sha256": _hash_file(paths.data / "task_eligibility_audit.json"),
        "pilot_sample_ids": sorted(pilot_tasks),
        "selected": selected,
    }
    _fixed_write(paths.data / "task_selection_manifest.json", selection)
    prompt = paths.root / "prompts/inhouse/proposer_code.txt"
    plan = []
    for attempt in attempt_plan(selected_ids):
        task = tasks[attempt["task_id"]]
        messages = _messages(
            source,
            "proposer_code.txt",
            {"task_prompt": task.prompt, "first_test_assert": task.tests[0]},
        )
        plan.append(
            {
                **attempt,
                "messages": [message.model_dump() for message in messages],
                "input_sha256": input_hash(messages),
            }
        )
    attempts = {
        "task_selection_manifest_sha256": _hash_file(paths.data / "task_selection_manifest.json"),
        "prompt_sha256": _hash_file(prompt),
        "proposer": {
            "source": proposer["source"],
            "source_revision": proposer["source_revision"],
            "gguf_revision": proposer["gguf_revision"],
            "license": proposer["license"],
            "resolved_identity": resolved.sha256,
            "files": [
                {
                    "path": str(file.relative_to(paths.root)).replace("\\", "/"),
                    "sha256": _hash_file(file),
                }
                for file in resolved.files
            ],
        },
        "sampling": config["sampling"]["proposer"],
        "context_size": config["server"]["context_size"],
        "attempts": plan,
    }
    _fixed_write(paths.data / "generation_attempt_manifest.json", attempts)
    return {"status": "READY", "audit": audit, "selection": selection, "attempts": attempts}


def verify_references(paths: AcquisitionPaths) -> dict:
    prepared = prepare(paths)
    if prepared["status"] != "READY":
        raise ValueError("Task selection blocked.")
    target = paths.data / "reference_docker_checks.json"
    selected = prepared["selection"]["selected"]
    if target.exists():
        prior = json.loads(target.read_text(encoding="utf-8"))
        if [row["task_id"] for row in prior["rows"]] != [
            row["task"]["task_id"] for row in selected
        ] or any(
            row["stdout"] != "RESULT: 3/3\n" or row["returncode"] != 0 for row in prior["rows"]
        ):
            raise ValueError("Saved reference Docker checks disagree with selected tasks.")
        return prior
    sandbox = DockerSandbox(paths, load_config(paths)["sandbox"])
    output = []
    for entry in selected:
        task = Task.model_validate(entry["task"])
        result = sandbox.run(task.reference_code, render_harness(task.tests), use_cache=False)
        if result.returncode != 0 or result.stderr or result.stdout != "RESULT: 3/3\n":
            raise ValueError(f"Selected reference failed Docker recheck: {task.task_id}: {result}")
        output.append(
            {
                "task_id": task.task_id,
                "task_sha256": entry["task_sha256"],
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode,
            }
        )
    record = {
        "selection_manifest_sha256": _hash_file(paths.data / "task_selection_manifest.json"),
        "rows": output,
    }
    _fixed_write(target, record)
    return record


def _attempt_path(paths: AcquisitionPaths, attempt: dict) -> Path:
    return paths.data / "responses" / f"{attempt['candidate_id']}.json"


def _execution_path(paths: AcquisitionPaths, candidate: Candidate) -> Path:
    return paths.data / "executions" / f"{candidate.cand_id}.json"


def _old_hashes(paths: AcquisitionPaths) -> set[str]:
    prior = _load_prior_audit(paths)
    return {row["code_sha256"] for row in prior["pool"]}


def _generate_task(
    paths: AcquisitionPaths,
    client: object,
    config: dict,
    attempts: list[dict],
    candidates: list[Candidate],
    seen_hashes: set[str],
    progress: Progress,
) -> None:
    by_id = {candidate.cand_id: candidate for candidate in candidates}
    for attempt in attempts:
        file = _attempt_path(paths, attempt)
        if file.exists():
            record = json.loads(file.read_text(encoding="utf-8"))
            if (
                record["candidate_id"] != attempt["candidate_id"]
                or record["input_sha256"] != attempt["input_sha256"]
                or record["seed"] != attempt["seed"]
            ):
                raise ValueError("Saved proposer response differs from fixed attempt.")
        else:
            messages = [Message.model_validate(message) for message in attempt["messages"]]
            parameters = {
                key: config["sampling"]["proposer"][key]
                for key in ("temperature", "top_p", "max_tokens")
            }
            parameters["seed"] = attempt["seed"]
            completion = client.complete(messages, parameters)
            body = _cached_api_body(
                client, _case_proxy({"case_id": attempt["candidate_id"]}, messages), parameters
            )
            extracted = extract_code(completion.raw_output)
            try:
                candidate = Candidate.from_source(
                    attempt["candidate_id"],
                    attempt["task_id"],
                    attempt["gen_index"],
                    "proposer",
                    extracted,
                )
                duplicate = candidate.code_sha256 in seen_hashes
                status = "duplicate" if duplicate else "accepted"
                code_sha = candidate.code_sha256
            except SyntaxError:
                status, code_sha = "syntax_error", None
            record = {
                "candidate_id": attempt["candidate_id"],
                "task_id": attempt["task_id"],
                "gen_index": attempt["gen_index"],
                "seed": attempt["seed"],
                "input_sha256": attempt["input_sha256"],
                "raw_output": completion.raw_output,
                "raw_api_response": body,
                "extracted_code": extracted,
                "syntax_valid": status != "syntax_error",
                "status": status,
                "code_sha256": code_sha,
                "completion_tokens": completion.completion_tokens,
                "prompt_tokens": body.get("usage", {}).get("prompt_tokens"),
                "finish_reason": completion.finish_reason,
                "cache_hit": completion.cache_hit,
                "timestamp": completion.timestamp,
            }
            _fixed_write(file, record)
        if record["status"] == "accepted":
            candidate = Candidate.from_source(
                attempt["candidate_id"],
                attempt["task_id"],
                attempt["gen_index"],
                "proposer",
                record["extracted_code"],
            )
            if candidate.code_sha256 != record["code_sha256"]:
                raise ValueError("Accepted candidate hash differs from saved response.")
            old = by_id.get(candidate.cand_id)
            if old is None:
                candidates.append(candidate)
                by_id[candidate.cand_id] = candidate
                write_jsonl(paths.candidates, candidates, Candidate)
            elif old.code_sha256 != candidate.code_sha256:
                raise ValueError("Checkpointed candidate code differs.")
            seen_hashes.add(candidate.code_sha256)
        progress.advance()


def _execute_task(
    paths: AcquisitionPaths,
    sandbox: DockerSandbox,
    config: dict,
    task: Task,
    candidates: list[Candidate],
) -> None:
    for index, candidate in enumerate(candidates):
        if candidate.task_id != task.task_id:
            continue
        file = _execution_path(paths, candidate)
        if file.exists():
            record = json.loads(file.read_text(encoding="utf-8"))
            if (
                record["candidate_id"] != candidate.cand_id
                or record["code_sha256"] != candidate.code_sha256
            ):
                raise ValueError("Saved execution differs from accepted candidate.")
            if record["n_passed"] is not None and candidate.n_passed is None:
                candidates[index] = Candidate.model_validate(
                    {
                        **candidate.model_dump(),
                        "n_tests": 3,
                        "n_passed": record["n_passed"],
                        "R_exec": record["n_passed"] / 3,
                        "true_pass": record["n_passed"] == 3,
                        "harness_output": record["stdout"],
                    }
                )
                write_jsonl(paths.candidates, candidates, Candidate)
            continue
        try:
            result = sandbox.run(
                candidate.code_stripped, render_harness(task.tests), use_cache=False
            )
            count = classify_result(result.stdout, result.returncode)
            if result.stderr:
                count = None
            import_probe = None
            load_ok = count is not None and count > 0
            if count in (0, 1):
                probe = sandbox.run(
                    candidate.code_stripped, render_harness(["assert True"]), use_cache=False
                )
                import_probe = {
                    "stdout": probe.stdout,
                    "stderr": probe.stderr,
                    "returncode": probe.returncode,
                }
                load_ok = (
                    probe.returncode == 0 and probe.stdout == "RESULT: 1/1\n" and not probe.stderr
                )
            record = {
                "candidate_id": candidate.cand_id,
                "task_id": task.task_id,
                "code_sha256": candidate.code_sha256,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode,
                "n_passed": count,
                "load_ok": load_ok,
                "import_probe": import_probe,
                "status": "ok" if count is not None else "unusable_harness_output",
            }
        except SandboxError as exc:
            if isinstance(exc, SandboxSetupError):
                raise
            record = {
                "candidate_id": candidate.cand_id,
                "task_id": task.task_id,
                "code_sha256": candidate.code_sha256,
                "stdout": "",
                "stderr": "",
                "returncode": None,
                "n_passed": None,
                "load_ok": None,
                "import_probe": None,
                "status": type(exc).__name__ + ": " + str(exc),
            }
        _fixed_write(file, record)
        if record["n_passed"] is not None:
            candidates[index] = Candidate.model_validate(
                {
                    **candidate.model_dump(),
                    "n_tests": 3,
                    "n_passed": record["n_passed"],
                    "R_exec": record["n_passed"] / 3,
                    "true_pass": record["n_passed"] == 3,
                    "harness_output": record["stdout"],
                }
            )
            write_jsonl(paths.candidates, candidates, Candidate)


def run(paths: AcquisitionPaths) -> None:
    prepared = prepare(paths)
    if prepared["status"] != "READY":
        raise ValueError("Task selection blocked; no proposer calls permitted.")
    verify_references(paths)
    config = load_config(paths)
    plan = prepared["attempts"]["attempts"]
    task_order = [entry["task"]["task_id"] for entry in prepared["selection"]["selected"]]
    tasks = {
        entry["task"]["task_id"]: Task.model_validate(entry["task"])
        for entry in prepared["selection"]["selected"]
    }
    candidates = read_jsonl(paths.candidates, Candidate)
    seen_hashes = _old_hashes(paths) | {candidate.code_sha256 for candidate in candidates}
    sandbox = DockerSandbox(paths, config["sandbox"])
    progress = Progress(sum(not _attempt_path(paths, attempt).exists() for attempt in plan))
    with stage_log(paths, "assertion-candidate-acquisition"):
        with model_session(paths, config, "proposer") as client:
            for task_id in task_order:
                attempts = [attempt for attempt in plan if attempt["task_id"] == task_id]
                _generate_task(paths, client, config, attempts, candidates, seen_hashes, progress)
                _execute_task(paths, sandbox, config, tasks[task_id], candidates)
                found = [
                    candidate
                    for candidate in candidates
                    if candidate.n_passed == 1
                    and json.loads(_execution_path(paths, candidate).read_text(encoding="utf-8"))[
                        "load_ok"
                    ]
                ]
                accepted_here = sum(candidate.task_id == task_id for candidate in candidates)
                found_here = sum(candidate.task_id == task_id for candidate in found)
                found_tasks = len({candidate.task_id for candidate in found})
                print(
                    f"{task_id}: {accepted_here} unique accepted, "
                    f"{found_here} importable 1/3; total {len(found)} "
                    f"across {found_tasks} tasks",
                    flush=True,
                )
                if has_diverse_pair([{"task_id": candidate.task_id} for candidate in found]):
                    break
    print("Acquisition stage complete; run analyze for readiness.", flush=True)


def analyze(paths: AcquisitionPaths) -> dict:
    prepared = prepare(paths)
    if prepared["status"] != "READY":
        raise ValueError("Task selection blocked.")
    task_order = [entry["task"]["task_id"] for entry in prepared["selection"]["selected"]]
    plan = prepared["attempts"]["attempts"]
    responses = [
        json.loads(_attempt_path(paths, attempt).read_text(encoding="utf-8"))
        for attempt in plan
        if _attempt_path(paths, attempt).exists()
    ]
    candidates = read_jsonl(paths.candidates, Candidate)
    prior_audit = _load_prior_audit(paths)
    prior_ids = {row["candidate_id"] for row in prior_audit["pool"]}
    prior_hashes = {row["code_sha256"] for row in prior_audit["pool"]}
    freshness_rows = [
        {
            "candidate_id": candidate.cand_id,
            "task_id": candidate.task_id,
            "code_sha256": candidate.code_sha256,
            **freshness_status(candidate.cand_id, candidate.code_sha256, prior_ids, prior_hashes),
        }
        for candidate in candidates
    ]
    freshness_audit = {
        "prior_selection_audit_sha256": PREVIOUS_AUDIT_SHA256,
        "prior_audited_sources": prior_audit["audited_sources"],
        "prior_pool_count": len(prior_audit["pool"]),
        "prior_exposed_candidate_ids": prior_audit["exposed_candidate_ids"],
        "new_candidate_count": len(candidates),
        "rows": freshness_rows,
    }
    _fixed_write(paths.data / "freshness_audit.json", freshness_audit)
    if any(not row["fresh"] for row in freshness_rows):
        raise ValueError("Accepted acquisition candidate overlaps the prior pool.")
    executions = {
        candidate.cand_id: json.loads(_execution_path(paths, candidate).read_text(encoding="utf-8"))
        for candidate in candidates
        if _execution_path(paths, candidate).exists()
    }
    completed_tasks = [
        task_id
        for task_id in task_order
        if sum(response["task_id"] == task_id for response in responses) == 16
        and all(
            candidate.cand_id in executions
            for candidate in candidates
            if candidate.task_id == task_id
        )
    ]
    qualifying = []
    for candidate in candidates:
        execution = executions.get(candidate.cand_id)
        if (
            execution
            and execution["n_passed"] == 1
            and execution["load_ok"]
            and candidate.code_sha256 not in prior_hashes
        ):
            qualifying.append(
                {
                    "candidate_id": candidate.cand_id,
                    "task_id": candidate.task_id,
                    "gen_index": candidate.gen_index,
                    "seed": 1000 + task_order.index(candidate.task_id) * 100 + candidate.gen_index,
                    "code_sha256": candidate.code_sha256,
                    "stdout": execution["stdout"],
                }
            )
    shortlist = choose_shortlist(qualifying, task_order)
    fresh_counts = dict(prior_audit["fresh_counts"])
    for candidate in candidates:
        if candidate.n_passed is not None and candidate.code_sha256 not in prior_hashes:
            fresh_counts[f"{candidate.n_passed}/3"] += 1
    summary = {
        "task_manifest_sha256": _hash_file(paths.data / "task_selection_manifest.json"),
        "attempt_manifest_sha256": _hash_file(paths.data / "generation_attempt_manifest.json"),
        "reference_checks_sha256": _hash_file(paths.data / "reference_docker_checks.json"),
        "freshness_audit_sha256": _hash_file(paths.data / "freshness_audit.json"),
        "completed_task_ids": completed_tasks,
        "completed_proposer_calls": len(responses),
        "accepted_unique_candidates": len(candidates),
        "docker_executions": len(executions),
        "attempt_status_counts": {
            status: sum(response["status"] == status for response in responses)
            for status in ("accepted", "duplicate", "syntax_error")
        },
        "qualifying_one_of_three": sorted(
            qualifying, key=lambda row: (task_order.index(row["task_id"]), row["gen_index"])
        ),
        "selected_shortlist": shortlist,
        "fresh_counts": fresh_counts,
        "ready_for_selection_review": has_diverse_pair(shortlist)
        and all(value >= 2 for value in fresh_counts.values()),
        "task_distributions": {
            task_id: {
                stratum: sum(
                    candidate.task_id == task_id and candidate.n_passed == int(stratum[0])
                    for candidate in candidates
                )
                for stratum in ("0/3", "1/3", "2/3", "3/3")
            }
            | {
                "accepted": sum(candidate.task_id == task_id for candidate in candidates),
                "unusable": sum(
                    candidate.task_id == task_id
                    and executions.get(candidate.cand_id, {}).get("n_passed") is None
                    for candidate in candidates
                ),
            }
            for task_id in completed_tasks
        },
    }
    write_json(paths.data / "analysis.json", summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("prepare", "verify-references", "run", "analyze"))
    stage = parser.parse_args().stage
    paths = AcquisitionPaths(Paths.discover().root, "smoke")
    if stage == "prepare":
        print(prepare(paths)["status"])
    elif stage == "verify-references":
        print(f"Verified {len(verify_references(paths)['rows'])} references in Docker.")
    elif stage == "run":
        run(paths)
    else:
        print(json.dumps(analyze(paths), indent=2))


if __name__ == "__main__":
    main()
