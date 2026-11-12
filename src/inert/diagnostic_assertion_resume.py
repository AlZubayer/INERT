"""Freeze a fresh, outcome-balanced selection without world-model inference."""

import argparse
import ast
import hashlib
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from inert.config import Paths, load_config
from inert.diagnostic_assertion_acquisition import AcquisitionPaths
from inert.diagnostic_assertion_selection import AuditPaths
from inert.harness import render_harness
from inert.pipeline import ExecutionRecord
from inert.sandbox import DockerSandbox
from inert.schemas import Candidate, Item, Score, Task, read_jsonl, write_json

PRIOR_AUDIT_SHA256 = "6def12845d6b69f9179efd649d34d0ac79ac2934df50cd26ed3219f6c4ad2845"
ACQUISITION_ANALYSIS_SHA256 = "c1748f13ecbe4817218493110e0430560b3970ed6437c1ffc46e8190b6daef24"
ACQUISITION_FRESHNESS_SHA256 = "a24bc890f40362a0e6cfcc3851fa52fea954c449fa80d76ced825e48a37ae2e9"
ACQUISITION_TASK_MANIFEST_SHA256 = (
    "463429468e371ac5cb4b9ab2ee3ecf885004f5b5392312ce7c17cf6b302d91e4"
)
ONE_THREE_SHORTLIST = ("acq-mbpp-563-g00", "acq-mbpp-622-g00")
STRATA = ("0/3", "1/3", "2/3", "3/3")


@dataclass(frozen=True)
class ResumePaths(Paths):
    @property
    def data(self) -> Path:
        return self.root / "data/smoke/diagnostics/assertion_execution_20261112/selection_resume"


def _sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _text_sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def ordered_tests_sha256(tests: list[str]) -> str:
    """Hash the complete, ordered test strings, including supplied imports."""
    return _text_sha256(json.dumps(tests, ensure_ascii=False, separators=(",", ":")))


def _read_verified(path: Path, expected_sha256: str) -> dict:
    if _sha256(path) != expected_sha256:
        raise ValueError(f"Source evidence checksum changed: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _fixed_write(path: Path, payload: dict) -> None:
    if path.exists():
        if json.loads(path.read_text(encoding="utf-8")) != payload:
            raise ValueError(f"Frozen selection artifact differs: {path}")
    else:
        write_json(path, payload)


def select_balanced(rows: list[dict], shortlist: tuple[str, str]) -> list[dict]:
    """Select two fresh candidates per stratum with the authorized 1/3 rule."""
    if len({row["candidate_id"] for row in rows}) != len(rows):
        raise ValueError("Pool candidate IDs are not unique.")
    available = {row["candidate_id"]: row for row in rows if not row["exposed"]}
    if any(identifier not in available for identifier in shortlist):
        raise ValueError("A shortlisted 1/3 candidate is missing or exposed.")
    if any(available[identifier]["stratum"] != "1/3" for identifier in shortlist):
        raise ValueError("A shortlisted candidate does not have 1/3 Docker truth.")
    if available[shortlist[0]]["task_id"] == available[shortlist[1]]["task_id"]:
        raise ValueError("The shortlisted 1/3 candidates do not span two tasks.")
    selected = []
    for stratum in STRATA:
        if stratum == "1/3":
            chosen = [available[identifier] for identifier in shortlist]
        else:
            chosen = sorted(
                (row for row in available.values() if row["stratum"] == stratum),
                key=lambda row: row["candidate_id"],
            )[:2]
        if len(chosen) != 2:
            raise ValueError(f"Insufficient fresh candidates in {stratum} stratum.")
        rank_start = len(selected)
        selected.extend(
            {**row, "selection_rank": rank_start + index + 1} for index, row in enumerate(chosen)
        )
    if len(selected) != 8 or len({row["candidate_id"] for row in selected}) != 8:
        raise ValueError("Balanced selection does not have eight unique IDs.")
    if len({row["code_sha256"] for row in selected}) != 8:
        raise ValueError("Balanced selection does not have eight unique code hashes.")
    return selected


def _present_in_input(candidate: Candidate, content: str) -> bool:
    representations = (content, content.replace("\\n", "\n"))
    return any(
        candidate.cand_id in text
        or candidate.code_sha256 in text
        or candidate.code_stripped in text
        or candidate.raw_source in text
        for text in representations
    )


def _scan_historical_inputs(root: Path, prior: dict, candidates: list[Candidate]) -> dict:
    """Look for new source/ID/hash exposure in scored items and actual WM calls."""
    hits: dict[str, list[str]] = {candidate.cand_id: [] for candidate in candidates}
    sources = prior["audited_sources"]
    expected_caches = {root / entry["path"] for entry in sources if entry["kind"] == "model_cache"}
    current_caches = {
        path
        for path in (root / "data/smoke").rglob("*.sqlite")
        if path.stem not in ("sandbox", "proposer")
    }
    if current_caches != expected_caches:
        raise ValueError("Model-response cache inventory differs from historical audit.")
    scored_item_ids = set()
    for entry in sources:
        if entry["kind"] != "scores":
            continue
        path = root / entry["path"]
        if _sha256(path) != entry["sha256"]:
            raise ValueError(f"Historical score file changed: {path}")
        scored_item_ids.update(score.item_id for score in read_jsonl(path, Score))
    checked_calls = 0
    for entry in sources:
        path = root / entry["path"]
        if _sha256(path) != entry["sha256"]:
            raise ValueError(f"Historical inference source changed: {path}")
        kind = entry["kind"]
        if kind == "items":
            for item in read_jsonl(path, Item):
                if item.item_id not in scored_item_ids:
                    continue
                content = "\n".join(message.content for message in item.messages)
                for candidate in candidates:
                    if item.cand_id == candidate.cand_id or _present_in_input(candidate, content):
                        hits[candidate.cand_id].append(
                            f"scored_item:{entry['path']}:{item.item_id}"
                        )
        elif kind == "manifest":
            manifest = json.loads(path.read_text(encoding="utf-8"))
            for case in manifest.get("cases", []):
                stage = case.get("stage") or ""
                response = path.parent / "responses" / stage / (case["case_id"] + ".json")
                if not response.exists():
                    continue
                content = "\n".join(message["content"] for message in case.get("messages", []))
                for candidate in candidates:
                    if case.get("candidate_id") == candidate.cand_id or _present_in_input(
                        candidate, content
                    ):
                        hits[candidate.cand_id].append(
                            f"response:{entry['path']}:{case['case_id']}"
                        )
        elif kind == "model_cache":
            with sqlite3.connect("file:" + path.as_posix() + "?mode=ro", uri=True) as database:
                for row_index, (request_json,) in enumerate(
                    database.execute("SELECT request FROM calls")
                ):
                    request = json.loads(request_json)
                    content = "\n".join(message["content"] for message in request["messages"])
                    checked_calls += 1
                    for candidate in candidates:
                        if _present_in_input(candidate, content):
                            hits[candidate.cand_id].append(f"cache:{entry['path']}:{row_index}")
    return {
        "audited_source_count": len(sources),
        "model_cache_count": sum(entry["kind"] == "model_cache" for entry in sources),
        "scanned_model_calls": checked_calls,
        "hits": {identifier: evidence for identifier, evidence in hits.items() if evidence},
    }


def _line_locations(root: Path, path: Path, key: str) -> dict[str, str]:
    locations = {}
    relative = path.relative_to(root).as_posix()
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        record = json.loads(line)
        locations[record[key]] = f"{relative}:{number}"
    return locations


def _source_pool(
    paths: ResumePaths,
) -> tuple[list[dict], dict[str, Candidate], dict[str, Task], dict]:
    root = paths.root
    smoke = Paths(root, "smoke")
    acquisition = AcquisitionPaths(root, "smoke")
    prior = _read_verified(
        AuditPaths(root, "smoke").data / "selection_audit.json", PRIOR_AUDIT_SHA256
    )
    analysis = _read_verified(acquisition.data / "analysis.json", ACQUISITION_ANALYSIS_SHA256)
    freshness = _read_verified(
        acquisition.data / "freshness_audit.json", ACQUISITION_FRESHNESS_SHA256
    )
    task_manifest = _read_verified(
        acquisition.data / "task_selection_manifest.json", ACQUISITION_TASK_MANIFEST_SHA256
    )
    old = read_jsonl(smoke.candidates, Candidate)
    new = read_jsonl(acquisition.candidates, Candidate)
    if len(old) != 29 or len(new) != 79 or analysis["accepted_unique_candidates"] != len(new):
        raise ValueError("Old or acquired candidate count differs from published evidence.")
    candidates = {candidate.cand_id: candidate for candidate in [*old, *new]}
    if (
        len(candidates) != 108
        or len({candidate.code_sha256 for candidate in candidates.values()}) != 108
    ):
        raise ValueError("Candidate ID or stripped-code hash overlaps across source pools.")
    tasks = {task.task_id: task for task in read_jsonl(smoke.tasks, Task)}
    for entry in task_manifest["selected"]:
        task = Task.model_validate(entry["task"])
        if _text_sha256(task.model_dump_json()) != entry["task_sha256"]:
            raise ValueError(f"Acquired task provenance differs: {task.task_id}")
        tasks[task.task_id] = task
    prior_rows = {row["candidate_id"]: row for row in prior["pool"]}
    fresh_rows = {row["candidate_id"]: row for row in freshness["rows"]}
    if len(prior_rows) != 29 or len(fresh_rows) != 79:
        raise ValueError("Exposure audit does not cover the complete source pool.")
    old_executions = {
        record.cand_id: record
        for record in read_jsonl(smoke.data / "executions.jsonl", ExecutionRecord)
    }
    if len(old_executions) != 29:
        raise ValueError("Old Docker execution archive is incomplete.")
    new_executions = {}
    for candidate in new:
        file = acquisition.data / "executions" / f"{candidate.cand_id}.json"
        new_executions[candidate.cand_id] = json.loads(file.read_text(encoding="utf-8"))
    if len(new_executions) != 79:
        raise ValueError("Acquired Docker execution archive is incomplete.")
    for candidate in old:
        task = tasks[candidate.task_id]
        record = old_executions[candidate.cand_id]
        identity = _text_sha256(candidate.code_stripped + render_harness(task.tests))
        audit = prior_rows[candidate.cand_id]
        if (
            candidate.n_tests != 3
            or task.n_tests != 3
            or record.status != "ok"
            or record.source_sha256 != identity
            or record.stdout != candidate.harness_output
            or audit["code_sha256"] != candidate.code_sha256
            or audit["n_passed"] != candidate.n_passed
        ):
            raise ValueError(
                f"Old candidate provenance or Docker truth differs: {candidate.cand_id}"
            )
    for candidate in new:
        task = tasks[candidate.task_id]
        record = new_executions[candidate.cand_id]
        audited = fresh_rows[candidate.cand_id]
        if (
            candidate.n_tests != 3
            or task.n_tests != 3
            or record["status"] != "ok"
            or record["returncode"] != 0
            or record["stderr"]
            or record["code_sha256"] != candidate.code_sha256
            or record["n_passed"] != candidate.n_passed
            or record["stdout"] != candidate.harness_output
            or not audited["fresh"]
            or audited["candidate_id_overlap"]
            or audited["code_sha256_overlap"]
        ):
            raise ValueError(
                f"Acquired candidate provenance or Docker truth differs: {candidate.cand_id}"
            )
    if analysis["selected_shortlist"] != [
        {
            "candidate_id": identifier,
            "task_id": candidates[identifier].task_id,
            "gen_index": candidates[identifier].gen_index,
            "seed": 1000
            + [entry["task"]["task_id"] for entry in task_manifest["selected"]].index(
                candidates[identifier].task_id
            )
            * 100
            + candidates[identifier].gen_index,
            "code_sha256": candidates[identifier].code_sha256,
            "stdout": candidates[identifier].harness_output,
        }
        for identifier in ONE_THREE_SHORTLIST
    ]:
        raise ValueError("The 1/3 acquisition shortlist changed.")
    for identifier in ONE_THREE_SHORTLIST:
        record = new_executions[identifier]
        if (
            record["stdout"] != "RESULT: 1/3\n"
            or not record["load_ok"]
            or record["import_probe"] != {"stdout": "RESULT: 1/1\n", "stderr": "", "returncode": 0}
        ):
            raise ValueError(f"Shortlisted 1/3 Docker/import proof failed: {identifier}")
    new_scan = _scan_historical_inputs(root, prior, new)
    rows = []
    for candidate in [*old, *new]:
        previous = prior_rows.get(candidate.cand_id)
        evidence = (
            previous["exposure_evidence"]
            if previous
            else new_scan["hits"].get(candidate.cand_id, [])
        )
        rows.append(
            {
                "candidate_id": candidate.cand_id,
                "task_id": candidate.task_id,
                "stratum": f"{candidate.n_passed}/3",
                "code_sha256": candidate.code_sha256,
                "exposed": bool(evidence),
                "exposure_evidence": evidence,
            }
        )
    audit = {
        "prior_selection_audit_sha256": PRIOR_AUDIT_SHA256,
        "acquisition_freshness_audit_sha256": ACQUISITION_FRESHNESS_SHA256,
        "historical_input_scan": new_scan,
        "pool_size": len(rows),
        "exposed_count": sum(row["exposed"] for row in rows),
        "rows": sorted(rows, key=lambda row: row["candidate_id"]),
    }
    return rows, candidates, tasks, audit


def freeze(paths: ResumePaths) -> dict:
    """Write an immutable eight-candidate selection and separate Docker oracle."""
    rows, candidates, tasks, audit = _source_pool(paths)
    selected = select_balanced(rows, ONE_THREE_SHORTLIST)
    root = paths.root
    smoke = Paths(root, "smoke")
    acquisition = AcquisitionPaths(root, "smoke")
    old_candidate_lines = _line_locations(root, smoke.candidates, "cand_id")
    old_task_lines = _line_locations(root, smoke.tasks, "task_id")
    old_execution_lines = _line_locations(root, smoke.data / "executions.jsonl", "cand_id")
    new_candidate_lines = _line_locations(root, acquisition.candidates, "cand_id")
    task_indices = {
        entry["task"]["task_id"]: index
        for index, entry in enumerate(
            json.loads(
                (acquisition.data / "task_selection_manifest.json").read_text(encoding="utf-8")
            )["selected"]
        )
    }
    source_rows, manifest_rows, oracle_rows = [], [], []
    sandbox_config = load_config(paths)["sandbox"]
    sandbox = DockerSandbox(paths, sandbox_config)
    existing_oracle = paths.data / "oracle.json"
    old_oracle = (
        json.loads(existing_oracle.read_text(encoding="utf-8"))
        if existing_oracle.exists()
        else None
    )
    for row in selected:
        identifier = row["candidate_id"]
        candidate = candidates[identifier]
        task = tasks[candidate.task_id]
        acquired = identifier.startswith("acq-")
        source_rows.append(
            {
                "candidate_id": identifier,
                "task_id": task.task_id,
                "task_prompt": task.prompt,
                "fn_name": task.fn_name,
                "raw_source": candidate.raw_source,
                "code_stripped": candidate.code_stripped,
                "tests": task.tests,
            }
        )
        recorded_path = (
            f"data/smoke/diagnostics/assertion_candidate_acquisition_20261112/executions/{identifier}.json"
            if acquired
            else old_execution_lines[identifier]
        )
        if old_oracle is None:
            result = sandbox.run(
                candidate.code_stripped, render_harness(task.tests), use_cache=False
            )
            if result.returncode != 0 or result.stderr or result.stdout != candidate.harness_output:
                raise ValueError(f"Fresh aggregate Docker recheck differs: {identifier}")
            rerun = {
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode,
            }
        else:
            matching = [
                entry for entry in old_oracle["rows"] if entry["candidate_id"] == identifier
            ]
            if len(matching) != 1:
                raise ValueError(f"Saved oracle missing candidate: {identifier}")
            rerun = matching[0]["aggregate_docker_recheck"]
            if rerun != {"stdout": candidate.harness_output, "stderr": "", "returncode": 0}:
                raise ValueError(f"Saved Docker recheck differs: {identifier}")
        oracle_rows.append(
            {
                "candidate_id": identifier,
                "task_id": task.task_id,
                "n_passed": candidate.n_passed,
                "n_tests": 3,
                "recorded_stdout": candidate.harness_output,
                "recorded_execution_location": recorded_path,
                "aggregate_docker_recheck": rerun,
            }
        )
        manifest_rows.append(
            {
                "selection_rank": row["selection_rank"],
                "candidate_id": identifier,
                "task_id": task.task_id,
                "outcome_stratum": row["stratum"],
                "candidate_record_location": (
                    new_candidate_lines[identifier] if acquired else old_candidate_lines[identifier]
                ),
                "task_record_location": (
                    f"data/smoke/diagnostics/assertion_candidate_acquisition_20261112/task_selection_manifest.json#selected[{task_indices[task.task_id]}].task"
                    if acquired
                    else old_task_lines[task.task_id]
                ),
                "recorded_execution_location": recorded_path,
                "raw_source_sha256": _text_sha256(candidate.raw_source),
                "code_stripped_sha256": candidate.code_sha256,
                "original_tests_sha256": ordered_tests_sha256(task.tests),
                "task_record_sha256": _text_sha256(task.model_dump_json()),
                "prior_exposure_evidence": row["exposure_evidence"],
                "source_has_top_level_assert": any(
                    isinstance(node, ast.Assert) for node in ast.parse(candidate.raw_source).body
                ),
            }
        )
    source_archive = {
        "purpose": "future prompt inputs; contains no Docker truth or selection annotations",
        "rows": source_rows,
    }
    oracle = {
        "purpose": "evaluation only; never include in world-model prompts",
        "sandbox_config": sandbox_config,
        "docker_image_id": old_oracle["docker_image_id"] if old_oracle else sandbox.image_id,
        "rows": oracle_rows,
    }
    _fixed_write(paths.data / "source_archive.json", source_archive)
    _fixed_write(existing_oracle, oracle)
    _fixed_write(paths.data / "exposure_audit.json", audit)
    manifest = {
        "status": "FROZEN_READY_FOR_48_CALL_DIAGNOSTIC",
        "selection_rule": {
            "strata_order": list(STRATA),
            "per_stratum": 2,
            "one_three": "owner-authorized acquisition shortlist, distinct tasks, fixed order",
            "other_strata": "fresh candidates in ascending candidate ID within each stratum",
            "shortlist": list(ONE_THREE_SHORTLIST),
            "diagnostic_only_clarification": True,
        },
        "source_files": {
            "old_candidates_sha256": _sha256(smoke.candidates),
            "old_tasks_sha256": _sha256(smoke.tasks),
            "old_executions_sha256": _sha256(smoke.data / "executions.jsonl"),
            "prior_selection_audit_sha256": PRIOR_AUDIT_SHA256,
            "acquisition_candidates_sha256": _sha256(acquisition.candidates),
            "acquisition_task_manifest_sha256": ACQUISITION_TASK_MANIFEST_SHA256,
            "acquisition_analysis_sha256": ACQUISITION_ANALYSIS_SHA256,
            "acquisition_freshness_sha256": ACQUISITION_FRESHNESS_SHA256,
        },
        "source_archive_sha256": _sha256(paths.data / "source_archive.json"),
        "oracle_sha256": _sha256(existing_oracle),
        "exposure_audit_sha256": _sha256(paths.data / "exposure_audit.json"),
        "selected": manifest_rows,
    }
    _fixed_write(paths.data / "selection_manifest.json", manifest)
    digest = _sha256(paths.data / "selection_manifest.json")
    _fixed_write(
        paths.data / "selection_manifest_checksum.json",
        {"path": "selection_manifest.json", "sha256": digest},
    )
    return {"status": manifest["status"], "manifest_sha256": digest, "selected": manifest_rows}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("freeze",))
    parser.parse_args()
    result = freeze(ResumePaths(Paths.discover().root, "smoke"))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
