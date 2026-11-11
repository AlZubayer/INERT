from inert.config import Config
from inert.schemas import Endpoint


def validity(ba: float | None, thresholds: Config) -> dict[str, str]:
    if ba is None:
        return {
            "kt_a": "UNAVAILABLE",
            "kt_b": "UNAVAILABLE",
            "reason": "No estimable T0 balanced accuracy.",
        }
    if ba < thresholds["validity_lower"]:
        return {"kt_a": "INVALID", "kt_b": "INVALID", "reason": "T0 balanced accuracy below 0.55."}
    if ba > thresholds["validity_upper"]:
        return {"kt_a": "VALID", "kt_b": "INVALID", "reason": "Ceiling: KT-B only is INVALID."}
    return {"kt_a": "VALID", "kt_b": "VALID", "reason": ""}


def cell_a(effect: Endpoint, thresholds: Config) -> str:
    if effect.estimate is None or effect.lower is None or effect.upper is None:
        return "UNAVAILABLE"
    if effect.estimate >= thresholds["effect"] and effect.lower > 0:
        return "EFFECT"
    if effect.estimate < thresholds["no_effect"] or effect.upper < thresholds["effect"]:
        return "NO_EFFECT"
    return "MARGINAL"


def kt_a(cells: dict[str, list[str]]) -> str:
    strong = cells.get("wm_a", []) + cells.get("wm_b", [])
    valid = [cell for cell in strong if cell not in ("INVALID", "DROPPED")]
    if not valid:
        return "INCONCLUSIVE"
    if "EFFECT" in cells.get("wm_a", []):
        return "STRONG_PASS"
    if "UNAVAILABLE" in valid:
        return "UNAVAILABLE"
    if "EFFECT" in cells.get("wm_b", []):
        return "PASS"
    if "EFFECT" in cells.get("wm_c", []):
        return "WEAK_ONLY"
    return "KILL" if all(cell == "NO_EFFECT" for cell in valid) else "MARGINAL"


def _helps(endpoint: Endpoint, threshold: float) -> bool:
    return (
        endpoint.estimate is not None
        and endpoint.lower is not None
        and endpoint.estimate >= threshold
        and endpoint.lower > 0
    )


def kt_b(cells: list[tuple[Endpoint, Endpoint]], thresholds: Config) -> str:
    if any(_helps(nat, thresholds["stripping"]) for nat, _ in cells):
        return "TRADE_OFF"
    if not cells or any(nat.estimate is None for nat, _ in cells):
        return "UNAVAILABLE"
    if any(_helps(true, thresholds["stripping"]) for _, true in cells):
        return "CLAIMS_ONLY"
    if any(true.estimate is None for _, true in cells):
        return "UNAVAILABLE"
    return "STRIP_IS_FREE"


def cell_c(amplification: Endpoint, regret: Endpoint, thresholds: Config) -> str:
    if amplification.lower is None or amplification.upper is None:
        return "UNAVAILABLE"
    if amplification.lower <= 0:
        return "NO_AMPLIFICATION"
    if regret.estimate is None or regret.lower is None:
        return "UNAVAILABLE"
    return "AMPLIFIES_AND_HARMS" if _helps(regret, thresholds["regret"]) else "AMPLIFIES_ONLY"


def kt_c(cells: list[str]) -> str:
    if "AMPLIFIES_AND_HARMS" in cells:
        return "PASS"
    if "UNAVAILABLE" in cells or not cells:
        return "UNAVAILABLE"
    if "AMPLIFIES_ONLY" in cells:
        return "PARTIAL"
    return "KILL"


def overall(a: str, c: str, b: str) -> str:
    if a == "KILL":
        return "Stop the project."
    if a == "WEAK_ONLY":
        return (
            "Stop or pivot. A paper showing only that a 1.5B model is swayed is not worth building."
        )
    if a == "INCONCLUSIVE":
        return "Inconclusive (all cells invalid). Change the task set before rerunning."
    if a == "MARGINAL":
        return (
            "Extend the pilot to 100 tasks for KT-A, then re-apply this table once. "
            "No second extension."
        )
    if a in ("PASS", "STRONG_PASS"):
        if c == "PASS" and b in ("TRADE_OFF", "CLAIMS_ONLY"):
            return "Build the full project with RQ1–RQ3."
        if c == "PASS" and b == "STRIP_IS_FREE":
            return (
                'Build a reduced project: RQ1 + RQ2, with "strip agent text" as the stated '
                "defence. Lower venue expectations."
            )
        if c == "PARTIAL":
            return (
                "Borderline. Amplification without decision harm. "
                "Rerun KT-C on 100 tasks before deciding."
            )
        if c == "KILL":
            return (
                "Drop RQ2. What remains is a measurement paper close to prior work; "
                "recommend stopping unless KT-B is TRADE_OFF."
            )
    return (
        "Unavailable: required stages or paired endpoints are missing; "
        "no project decision assigned."
    )
