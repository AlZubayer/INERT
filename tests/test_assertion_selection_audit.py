"""Selection audit must stop before inference when a truth stratum is absent."""

from inert.config import Paths
from inert.diagnostic_assertion_selection import AuditPaths, build_audit


def test_selection_audit_detects_unavailable_one_pass_stratum() -> None:
    paths = AuditPaths(Paths.discover().root, "smoke")
    first = build_audit(paths)
    second = build_audit(paths)
    assert first == second
    assert first["status"] == "BLOCKED_SELECTION"
    assert first["pool_counts"] == {"0/3": 13, "1/3": 0, "2/3": 7, "3/3": 9}
    assert first["shortage"]["1/3"] == 2
    assert first["selected_candidate_ids"] == []
    assert len(first["pool"]) == 29
    assert first["ordering_rule"] == "candidate_id ascending within each truth stratum"
    assert "assertion_execution_20261112" in str(paths.data)
    assert paths.cache("wm_c") != Paths(paths.root, "smoke").cache("wm_c")


def test_prior_inference_exposure_is_not_called_fresh() -> None:
    paths = AuditPaths(Paths.discover().root, "smoke")
    audit = build_audit(paths)
    exposed = audit["exposed_candidate_ids"]
    assert {"mbpp-440-g00", "mbpp-310-g00", "mbpp-440-g04", "mbpp-265-g01"} <= set(exposed)
    assert all(row["n_passed"] in (0, 2, 3) for row in audit["pool"])
    assert len({row["code_sha256"] for row in audit["pool"]}) == 29
