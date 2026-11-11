import json
from typing import Any

from inert.config import Paths
from inert.schemas import Candidate, Item, Score, atomic_text


def _number(value: Any) -> str:
    if value is None:
        return "unavailable"
    if isinstance(value, dict) and "estimate" in value:
        if value["estimate"] is None:
            return "unavailable: " + (value.get("reason") or "no paired data")
        return (
            f"{value['estimate']:.4f} [{value['lower']:.4f}, {value['upper']:.4f}] "
            f"(n={value['n_pairs']}; valid resamples "
            f"{value['n_valid_resamples']}/{value['n_resamples']})"
        )
    return str(value)


def _code(text: str, language: str = "") -> str:
    import re

    fence = chr(96) * max(3, 1 + max((len(x) for x in re.findall(r"`+", text)), default=0))
    return fence + language + "\n" + text + "\n" + fence


def write_report(
    paths: Paths,
    summary: dict[str, Any],
    environment: dict[str, Any],
    items: list[Item],
    scores: list[Score],
    candidates: list[Candidate] | None = None,
) -> None:
    lines = [
        summary["decision"],
        "",
        "## Verdict table",
        "",
        "| Gate | Verdict |",
        "| --- | --- |",
        "| P0 | " + summary.get("p0", {}).get("decision", "NOT_RUN") + " |",
    ]
    for key in ["kt_a", "kt_b", "kt_c", "emergence"]:
        lines.append(f"| {key.upper()} | {summary[key]} |")
    lines += ["", "P0: " + summary.get("p0", {}).get("decision", "NOT_RUN"), ""]
    lines += [
        "",
        "## Environment",
        "",
        _code(
            json.dumps(
                {
                    "step0": environment,
                    "p0": summary.get("p0", {"decision": "NOT_RUN"}),
                    "scoring": summary.get("scoring_environment", {}),
                },
                indent=2,
                ensure_ascii=False,
            ),
            "json",
        ),
        "",
    ]
    for label, metrics in [
        ("KT-A", ["effect", "misleading_change", "neutral_change"]),
        ("KT-B", ["S_nat", "S_true"]),
    ]:
        lines += [
            f"## {label}",
            "",
            "| WM | Channel | Status | Endpoint | Estimate [95% interval] |",
            "| --- | --- | --- | --- | --- |",
        ]
        for wm, channels in summary["cells"].items():
            for channel, cell in channels.items():
                status = cell.get("validity", {}).get(
                    "kt_b" if label == "KT-B" else "kt_a", cell["status"]
                )
                for metric in metrics:
                    lines.append(
                        f"| {wm} | {channel} | {status} | {metric} | {_number(cell.get(metric))} |"
                    )
        lines += ["", "Exploratory results (do not determine the verdict):", ""]
        if label == "KT-A":
            for wm, channels in summary["cells"].items():
                for channel, cell in channels.items():
                    for condition, metrics_dict in cell.get("exploratory", {}).items():
                        lines.append(
                            f"- {wm}/{channel}/{condition}: "
                            + "; ".join(
                                f"{name} = {_number(value)}" for name, value in metrics_dict.items()
                            )
                        )
    lines += ["", "## KT-C", "", "Primary endpoints use rung B. Rung A is exploratory.", ""]
    for wm, rungs in summary["selection"].items():
        for rung, metrics in rungs.items():
            lines += [
                f"{wm}, rung {rung}: amplification = {_number(metrics['amplification'])}; "
                f"regret = {_number(metrics['regret'])}.",
                "",
            ]
            for n, row in metrics["by_n"].items():
                lines.append(
                    f"- N={n}: "
                    + "; ".join(f"{name} = {_number(val)}" for name, val in row.items())
                )
    lines += [
        "",
        "## Data quality",
        "",
        _code(json.dumps(summary["data_quality"], indent=2), "json"),
        "",
    ]
    for wm, channels in summary["cells"].items():
        for channel, cell in channels.items():
            lines.append(
                f"- {wm}/{channel}: {cell['status']}; parse failures "
                f"{cell.get('parse_failures', 'unavailable')}/"
                f"{cell.get('score_count', 'unavailable')}; "
                + cell.get("reason", cell.get("validity", {}).get("reason", ""))
            )
    lines += ["", "## Ten example items", ""]
    mapping = {item.item_id: item for item in items}
    truths = {candidate.cand_id: candidate for candidate in candidates or []}
    lookup = {
        (
            s.wm_id,
            mapping[s.item_id].cand_id,
            mapping[s.item_id].channel,
            mapping[s.item_id].condition,
        ): s
        for s in scores
    }
    examples: dict[bool, list[tuple[Item, Score]]] = {True: [], False: []}
    for score in scores:
        item = mapping[score.item_id]
        if not item.condition.startswith("MIS_") or score.parse_status != "ok":
            continue
        base = lookup.get((score.wm_id, item.cand_id, item.channel, "NEU_A"))
        if base is not None and base.parse_status == "ok":
            flipped = base.pred_pass != score.pred_pass
            if len(examples[flipped]) < 5:
                examples[flipped].append((item, score))
    for flipped, selected in examples.items():
        lines += [
            f"{'Flipped' if flipped else 'Did not flip'}: "
            f"{len(selected)} available of 5 requested.",
            "",
        ]
        for item, score in selected:
            baseline = lookup[(score.wm_id, item.cand_id, item.channel, "NEU_A")]
            truth = truths.get(item.cand_id)
            lines += [
                f"### {score.wm_id}: {item.item_id}",
                "",
                "Rendered messages:",
                "",
                _code(
                    json.dumps([m.model_dump() for m in item.messages], ensure_ascii=False), "json"
                ),
                "",
                "Raw output:",
                "",
                _code(score.raw_output),
                "",
                f"NEU_A baseline: {baseline.item_id}",
                "",
                _code(baseline.raw_output),
                "",
                "Executed harness output:",
                "",
                _code(truth.harness_output)
                if truth and truth.harness_output is not None
                else "Unavailable in supplied report inputs.",
                "",
            ]
    lines += [
        "## Deviations from the design",
        "",
        paths.deviations.read_text(encoding="utf-8")
        if paths.deviations.exists()
        else "None recorded.",
        "",
        "## Limits",
        "",
        "This pilot uses short Python functions, local quantized models, and test pass counts. "
        "It does not support claims about frontier models, other environments, or training.",
        "Unavailable endpoints, INVALID cells, parse failures, and unrun stages "
        "are excluded from conclusions.",
        "Every reported score derives from the supplied validated score records.",
    ]
    atomic_text(paths.report, "\n".join(lines) + "\n")
