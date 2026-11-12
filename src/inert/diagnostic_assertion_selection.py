"""Read-only freshness audit for the fixed assertion/execution diagnostic."""

import argparse
import hashlib
import json
import sqlite3
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from inert.config import Paths
from inert.diagnostic_failure_isolation import input_hash
from inert.schemas import Candidate, Item, Message, Score, Task, read_jsonl, write_json

ROOT_NAME = "assertion_execution_20261112"
STUDIED = {"mbpp-440-g00", "mbpp-310-g00", "mbpp-440-g04", "mbpp-265-g01"}
STRATA = ("0/3", "1/3", "2/3", "3/3")


@dataclass(frozen=True)
class AuditPaths(Paths):
    @property
    def data(self) -> Path:
        return self.root / "data" / "smoke" / "diagnostics" / ROOT_NAME


def _sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _rel(paths: Paths, path: Path) -> str:
    return str(path.relative_to(paths.root)).replace("\\", "/")


def _exposures(paths: AuditPaths) -> tuple[dict[str, set[str]], list[dict]]:
    """Match scores, response files, and cache requests to candidate inputs."""
    smoke = paths.root / "data" / "smoke"
    candidates = {
        candidate.cand_id: candidate
        for candidate in read_jsonl(smoke / "candidates.jsonl", Candidate)
    }
    item_ids: dict[str, set[str]] = defaultdict(set)
    prompt_ids: dict[str, set[str]] = defaultdict(set)
    exposures: dict[str, set[str]] = defaultdict(set)
    sources = []

    for file in sorted(smoke.rglob("items.jsonl")):
        if paths.data in file.parents:
            continue
        count = 0
        for item in read_jsonl(file, Item):
            item_ids[item.item_id].add(item.cand_id)
            prompt_ids[input_hash(item.messages)].add(item.cand_id)
            count += 1
        sources.append(
            {"path": _rel(paths, file), "sha256": _sha256(file), "kind": "items", "records": count}
        )

    for file in sorted(smoke.rglob("manifest.json")):
        if paths.data in file.parents:
            continue
        manifest = json.loads(file.read_text(encoding="utf-8"))
        cases = manifest.get("cases", [])
        response_count = 0
        for case in cases:
            candidate_id = case.get("candidate_id")
            if candidate_id not in candidates or not case.get("messages"):
                continue
            messages = [Message.model_validate(message) for message in case["messages"]]
            digest = input_hash(messages)
            if digest != case["input_sha256"]:
                raise ValueError(f"Stored prompt hash differs: {file}: {case['case_id']}")
            prompt_ids[digest].add(candidate_id)
            stage = case.get("stage")
            response = file.parent / "responses" / (stage or "") / (case["case_id"] + ".json")
            if response.exists():
                record = json.loads(response.read_text(encoding="utf-8"))
                if record["case_id"] != case["case_id"] or record["input_sha256"] != digest:
                    raise ValueError(f"Response input mismatch: {response}")
                exposures[candidate_id].add(f"response:{_rel(paths, response)}")
                response_count += 1
        sources.append(
            {
                "path": _rel(paths, file),
                "sha256": _sha256(file),
                "kind": "manifest",
                "candidate_responses": response_count,
            }
        )

    for file in sorted(smoke.rglob("*.jsonl")):
        is_score_file = file.parent.name == "scores" or (
            "audit" in file.parts and file.name.startswith("wm_")
        )
        if paths.data in file.parents or not is_score_file:
            continue
        count = 0
        for score in read_jsonl(file, Score):
            ids = item_ids.get(score.item_id)
            if not ids:
                raise ValueError(f"Scored item cannot be mapped to a candidate: {score.item_id}")
            for candidate_id in ids:
                exposures[candidate_id].add(f"score:{_rel(paths, file)}")
            count += 1
        sources.append(
            {"path": _rel(paths, file), "sha256": _sha256(file), "kind": "scores", "records": count}
        )

    for file in sorted(smoke.rglob("*.sqlite")):
        if paths.data in file.parents or file.stem in ("sandbox", "proposer"):
            continue
        count, mapped, unresolved = 0, 0, 0
        with sqlite3.connect("file:" + file.as_posix() + "?mode=ro", uri=True) as database:
            has_calls = database.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='calls'"
            ).fetchone()
            if not has_calls:
                continue
            for (request_json,) in database.execute("SELECT request FROM calls"):
                request = json.loads(request_json)
                messages = [Message.model_validate(message) for message in request["messages"]]
                digest = input_hash(messages)
                ids = prompt_ids.get(digest, set())
                if not ids:
                    content = "\n".join(message.content for message in messages)
                    representations = (content, content.replace("\\n", "\n"))
                    ids = {
                        identifier
                        for identifier, candidate in candidates.items()
                        if any(candidate.code_stripped in text for text in representations)
                    }
                count += 1
                if ids:
                    mapped += 1
                    for candidate_id in ids:
                        exposures[candidate_id].add(f"cache:{_rel(paths, file)}")
                else:
                    unresolved += 1
        sources.append(
            {
                "path": _rel(paths, file),
                "sha256": _sha256(file),
                "kind": "model_cache",
                "calls": count,
                "mapped": mapped,
                "unresolved": unresolved,
            }
        )

    for identifier in STUDIED:
        exposures[identifier].add("explicit_previous_study")
    return exposures, sources


def build_audit(paths: AuditPaths) -> dict:
    """Inventory the fixed local pool; produce no selection when balance fails."""
    source = Paths(paths.root, "smoke")
    tasks = {task.task_id: task for task in read_jsonl(source.tasks, Task)}
    candidates = list(read_jsonl(source.candidates, Candidate))
    if len({candidate.cand_id for candidate in candidates}) != len(candidates):
        raise ValueError("Duplicate candidate ID in local pool.")
    if len({candidate.code_sha256 for candidate in candidates}) != len(candidates):
        raise ValueError("Duplicate stripped code hash in local pool.")
    exposures, sources = _exposures(paths)
    pool = []
    for candidate in sorted(candidates, key=lambda value: value.cand_id):
        task = tasks[candidate.task_id]
        if candidate.n_tests != 3 or task.n_tests != 3 or candidate.n_passed is None:
            raise ValueError(f"Candidate missing three-test Docker truth: {candidate.cand_id}")
        expected = f"RESULT: {candidate.n_passed}/3\n"
        if candidate.harness_output != expected:
            raise ValueError(
                f"Candidate Docker output differs from pass count: {candidate.cand_id}"
            )
        pool.append(
            {
                "candidate_id": candidate.cand_id,
                "task_id": candidate.task_id,
                "n_passed": candidate.n_passed,
                "n_tests": candidate.n_tests,
                "code_sha256": candidate.code_sha256,
                "exposure_evidence": sorted(exposures.get(candidate.cand_id, set())),
            }
        )
    pool_counts = {
        stratum: sum(f"{row['n_passed']}/3" == stratum for row in pool) for stratum in STRATA
    }
    fresh_counts = {
        stratum: sum(
            f"{row['n_passed']}/3" == stratum and not row["exposure_evidence"] for row in pool
        )
        for stratum in STRATA
    }
    shortage = {stratum: max(0, 2 - fresh_counts[stratum]) for stratum in STRATA}
    return {
        "status": "BLOCKED_SELECTION" if any(shortage.values()) else "READY_FOR_SELECTION",
        "reason": "Insufficient fresh candidates in at least one required pass-count stratum"
        if any(shortage.values())
        else None,
        "base_commit": "c1a26304302eb1c8045d0cfe7fb3c421ce7d163e",
        "ordering_rule": "candidate_id ascending within each truth stratum",
        "pool_source": "data/smoke/candidates.jsonl",
        "pool_source_sha256": _sha256(source.candidates),
        "task_source_sha256": _sha256(source.tasks),
        "pool_counts": pool_counts,
        "fresh_counts": fresh_counts,
        "required_counts": {stratum: 2 for stratum in STRATA},
        "shortage": shortage,
        "exposed_candidate_ids": sorted(
            identifier
            for identifier in exposures
            if identifier in {candidate.cand_id for candidate in candidates}
        ),
        "selected_candidate_ids": [],
        "pool": pool,
        "audited_sources": sources,
    }


def prepare(paths: AuditPaths) -> dict:
    audit = build_audit(paths)
    target = paths.data / "selection_audit.json"
    if target.exists():
        if json.loads(target.read_text(encoding="utf-8")) != audit:
            raise ValueError("Existing selection audit differs; refusing overwrite.")
    else:
        write_json(target, audit)
    return audit


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("audit",))
    parser.parse_args()
    result = prepare(AuditPaths(Paths.discover().root, "smoke"))
    print(result["status"], result["pool_counts"], result["fresh_counts"], result["shortage"])


if __name__ == "__main__":
    main()
