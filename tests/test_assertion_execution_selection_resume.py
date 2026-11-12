"""Selection-only controls for the resumed assertion/execution diagnostic."""

import hashlib
import json

import pytest

from inert.config import Paths
from inert.diagnostic_assertion_resume import (
    ResumePaths,
    _fixed_write,
    ordered_tests_sha256,
    select_balanced,
)


def _row(identifier: str, stratum: str, *, exposed: bool = False) -> dict:
    return {
        "candidate_id": identifier,
        "task_id": "task-" + identifier,
        "stratum": stratum,
        "code_sha256": "hash-" + identifier,
        "exposed": exposed,
    }


def test_fixed_balance_and_ascending_id_after_exposure_exclusion() -> None:
    rows = [
        _row("z0", "0/3"),
        _row("a0", "0/3", exposed=True),
        _row("b0", "0/3"),
        _row("a2", "2/3"),
        _row("b2", "2/3"),
        _row("a3", "3/3"),
        _row("b3", "3/3"),
        _row("a1", "1/3"),
        _row("b1", "1/3"),
        _row("c1", "1/3"),
    ]
    selected = select_balanced(rows, ("a1", "b1"))
    assert [row["candidate_id"] for row in selected] == [
        "b0",
        "z0",
        "a1",
        "b1",
        "a2",
        "b2",
        "a3",
        "b3",
    ]
    assert [row["selection_rank"] for row in selected] == list(range(1, 9))
    assert select_balanced(list(reversed(rows)), ("a1", "b1")) == selected


def test_selection_rejects_shortage_exposure_and_duplicate_hash() -> None:
    rows = [
        _row(f"{stratum[0]}-{index}", stratum)
        for stratum in ("0/3", "1/3", "2/3", "3/3")
        for index in (0, 1)
    ]
    with pytest.raises(ValueError, match="fresh candidates"):
        select_balanced(rows[:-1], ("1-0", "1-1"))
    rows[2]["exposed"] = True
    with pytest.raises(ValueError, match="shortlisted"):
        select_balanced(rows, ("1-0", "1-1"))
    rows[2]["exposed"] = False
    rows[3]["code_sha256"] = rows[2]["code_sha256"]
    with pytest.raises(ValueError, match="code hashes"):
        select_balanced(rows, ("1-0", "1-1"))


def test_original_test_hash_is_order_sensitive() -> None:
    a = ["import re\nassert f(1) == 1", "assert f(2) == 2", "assert f(3) == 3"]
    assert ordered_tests_sha256(a) == ordered_tests_sha256(list(a))
    assert ordered_tests_sha256(a) != ordered_tests_sha256(list(reversed(a)))


def test_frozen_manifest_write_is_stable_and_refuses_changes(tmp_path) -> None:
    path = tmp_path / "manifest.json"
    _fixed_write(path, {"selected": ["a", "b"]})
    first = hashlib.sha256(path.read_bytes()).hexdigest()
    _fixed_write(path, {"selected": ["a", "b"]})
    assert hashlib.sha256(path.read_bytes()).hexdigest() == first
    with pytest.raises(ValueError, match="Frozen selection artifact"):
        _fixed_write(path, {"selected": ["b", "a"]})


def test_local_frozen_selection_provenance_if_available() -> None:
    """Check ignored real-run evidence locally; CI without data skips it."""
    directory = ResumePaths(Paths.discover().root, "smoke").data
    if not (directory / "selection_manifest.json").exists():
        pytest.skip("Ignored local diagnostic selection archive is absent")
    files = {
        name: json.loads((directory / f"{name}.json").read_text(encoding="utf-8"))
        for name in (
            "selection_manifest",
            "selection_manifest_checksum",
            "source_archive",
            "oracle",
            "exposure_audit",
        )
    }
    manifest = files["selection_manifest"]
    checksum = hashlib.sha256((directory / "selection_manifest.json").read_bytes()).hexdigest()
    assert checksum == files["selection_manifest_checksum"]["sha256"]
    assert checksum == "3aed60838f4c44dc5a8fa76b0bcf858ffb37f5d8de5c5ab8d267d0a50add37eb"
    selected = manifest["selected"]
    assert len(selected) == 8
    assert [row["outcome_stratum"] for row in selected] == [
        "0/3",
        "0/3",
        "1/3",
        "1/3",
        "2/3",
        "2/3",
        "3/3",
        "3/3",
    ]
    assert len({row["candidate_id"] for row in selected}) == 8
    assert len({row["code_stripped_sha256"] for row in selected}) == 8
    assert all(not row["prior_exposure_evidence"] for row in selected)
    assert len(files["source_archive"]["rows"]) == 8
    assert len(files["oracle"]["rows"]) == 8
    assert files["exposure_audit"]["historical_input_scan"]["hits"] == {}
    for selected_row, source_row, oracle_row in zip(
        selected, files["source_archive"]["rows"], files["oracle"]["rows"], strict=True
    ):
        assert selected_row["candidate_id"] == source_row["candidate_id"]
        assert selected_row["candidate_id"] == oracle_row["candidate_id"]
        assert (
            hashlib.sha256(source_row["raw_source"].encode()).hexdigest()
            == selected_row["raw_source_sha256"]
        )
        assert (
            hashlib.sha256(source_row["code_stripped"].encode()).hexdigest()
            == selected_row["code_stripped_sha256"]
        )
        assert ordered_tests_sha256(source_row["tests"]) == selected_row["original_tests_sha256"]
        assert len(source_row["tests"]) == 3
        assert oracle_row["aggregate_docker_recheck"]["stdout"] == oracle_row["recorded_stdout"]
        assert oracle_row["aggregate_docker_recheck"]["returncode"] == 0
        assert not ({"n_passed", "outcome_stratum", "selection_rank"} & source_row.keys())
