import re
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np

from inert.config import Config
from inert.decide import cell_a, cell_c, kt_a, kt_b, kt_c, overall, validity
from inert.planning import model_items
from inert.schemas import Candidate, Endpoint, Item, Score, Task
from inert.selection import SelectionCandidate, selection_bootstrap
from inert.stats import balanced_accuracy, bootstrap


def _dump(value: Any) -> Any:
    if isinstance(value, Endpoint):
        return value.model_dump()
    if isinstance(value, dict):
        return {str(key): _dump(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_dump(item) for item in value]
    return value


def analyze_records(
    tasks: list[Task],
    candidates: list[Candidate],
    items: list[Item],
    scores: list[Score],
    config: Config,
    model_status: dict[str, str] | None = None,
    checkpoint_root: Path | None = None,
) -> dict[str, Any]:
    task_map = {task.task_id: task for task in tasks}
    candidates = [candidate for candidate in candidates if candidate.task_id in task_map]
    cand_map = {cand.cand_id: cand for cand in candidates}
    item_map = {item.item_id: item for item in items}
    if len(item_map) != len(items):
        raise ValueError("Duplicate item IDs.")
    by_model: dict[str, dict[tuple[str, str, str, str], Score]] = defaultdict(dict)
    for score in scores:
        if score.wm_id not in config["scoring_order"]:
            raise ValueError("Score references an unplanned model.")
        item = item_map[score.item_id]
        if item.task_id not in task_map or item.cand_id not in cand_map:
            raise ValueError("Item references missing task or candidate.")
        if score.parse_status == "ok" and score.n_pred != task_map[item.task_id].n_tests:
            raise ValueError("Score denominator does not match task.")
        key = (item.cand_id, item.channel, item.condition, item.block)
        if key in by_model[score.wm_id]:
            raise ValueError("Duplicate score record.")
        by_model[score.wm_id][key] = score
    cells, a_cells, b_cells, c_results = {}, {}, [], []
    counts = {
        "tasks": len(tasks),
        "candidates": len(candidates),
        "core_candidates": sum(c.in_core_set for c in candidates),
        "mutants": sum(c.origin.startswith("mutant:") for c in candidates),
        "empty_natural_text": sum(not c.natural_text for c in candidates),
    }
    executed = [c for c in candidates if c.origin == "proposer" and c.true_pass is not None]
    counts["proposer_pass_rate"] = (
        float(np.mean([c.true_pass for c in executed])) if executed else None
    )
    c_models: dict[str, Any] = {}
    for wm in config["scoring_order"]:
        cells[wm], a_cells[wm] = {}, []
        model_scores = by_model[wm]
        status = (model_status or {}).get(wm)
        planned = model_items(
            items, tasks, candidates, config, wm, "reduced" if status == "REDUCED" else "full"
        )
        allowed = {item.item_id for item in planned}
        model_scores = {
            key: score for key, score in model_scores.items() if score.item_id in allowed
        }
        for channel in config["channels"]:
            if status == "DROPPED" or status == "REDUCED" and channel == "D":
                reason = (
                    "Model explicitly dropped."
                    if status == "DROPPED"
                    else "P0 reduced design omits channel D for WM-A."
                )
                cells[wm][channel] = {"status": "DROPPED", "reason": reason}
                a_cells[wm].append("DROPPED")
                continue
            planned_ids = {
                item.cand_id
                for item in planned
                if item.channel == channel and item.block == "kt_ab"
            }
            core = [c for c in candidates if c.in_core_set and c.cand_id in planned_ids]

            def pairs(
                conditions: list[str],
                population: list[Candidate],
                model_scores: dict = model_scores,
                channel: str = channel,
            ) -> list[tuple[str, tuple]]:
                result = []
                for candidate in population:
                    matched = [
                        model_scores.get((candidate.cand_id, channel, cond, "kt_ab"))
                        for cond in conditions
                    ]
                    if all(s is not None and s.parse_status == "ok" for s in matched):
                        result.append((candidate.task_id, (candidate, matched)))
                return result

            base = pairs(["T0"], core)
            ba = balanced_accuracy(
                [row[1][0].true_pass for row in base], [row[1][1][0].pred_pass for row in base]
            )
            valid = validity(ba, config["thresholds"])
            expected_ids = {
                item.item_id
                for item in planned
                if item.channel == channel and item.block == "kt_ab"
            }
            observed_ids = {s.item_id for s in model_scores.values()}
            missing = len(expected_ids - observed_ids)
            if missing or not expected_ids:
                valid = {
                    "kt_a": "UNAVAILABLE",
                    "kt_b": "UNAVAILABLE",
                    "reason": "Planned scoring is incomplete.",
                }
            failing = [c for c in core if c.true_pass is False]
            triple = pairs(["MIS_OUTCOME", "NEU_A", "NEU_B"], failing)

            def diff(rows: list[tuple], left: int, right: int) -> float | None:
                return (
                    float(
                        np.mean(
                            [
                                float(row[1][1][left].pred_pass) - float(row[1][1][right].pred_pass)
                                for row in rows
                            ]
                        )
                    )
                    if rows
                    else None
                )

            effect = bootstrap(triple, lambda rows: diff(rows, 0, 2), config["statistics"])
            misleading = bootstrap(triple, lambda rows: diff(rows, 0, 1), config["statistics"])
            neutral = bootstrap(triple, lambda rows: diff(rows, 2, 1), config["statistics"])

            def stripping(condition: str, population: list[Candidate]) -> Endpoint:
                paired = pairs([condition, "T0"], population)

                def difference(rows: list[tuple]) -> float | None:
                    truth = [row[1][0].true_pass for row in rows]
                    left = balanced_accuracy(truth, [row[1][1][0].pred_pass for row in rows])
                    right = balanced_accuracy(truth, [row[1][1][1].pred_pass for row in rows])
                    return left - right if left is not None and right is not None else None

                return bootstrap(paired, difference, config["statistics"])

            nat = stripping("NAT", [c for c in core if c.natural_text])
            true = stripping("TRUE", core)
            cell_result = (
                cell_a(effect, config["thresholds"]) if valid["kt_a"] == "VALID" else valid["kt_a"]
            )
            a_cells[wm].append(cell_result)
            if wm in ("wm_a", "wm_b") and valid["kt_b"] == "VALID":
                b_cells.append((nat, true))
            observed_scores = [
                s
                for (cid, ch, _, block), s in model_scores.items()
                if ch == channel and block == "kt_ab"
            ]
            exploratory = {}
            for condition in config["conditions"]:
                paired = pairs([condition, "T0"], core)
                gaps = bootstrap(
                    paired,
                    lambda rows: (
                        float(np.mean([row[1][1][0].R_sim - row[1][1][1].R_sim for row in rows]))
                        if rows
                        else None
                    ),
                    config["statistics"],
                )
                mis_pairs = pairs([condition, "NEU_A", "NEU_B"], failing)
                passing_pairs = pairs(
                    [condition, "NEU_A", "NEU_B"], [c for c in core if c.true_pass]
                )
                flip_pairs = pairs([condition, "NEU_A"], failing)
                exploratory[condition] = {
                    "narrative_gap": gaps,
                    "false_positive_rate": bootstrap(
                        pairs([condition], failing),
                        lambda rows: (
                            float(np.mean([r[1][1][0].pred_pass for r in rows])) if rows else None
                        ),
                        config["statistics"],
                    ),
                    "effect": bootstrap(
                        mis_pairs, lambda rows: diff(rows, 0, 2), config["statistics"]
                    ),
                    "flip_rate": bootstrap(
                        flip_pairs,
                        lambda rows: (
                            float(
                                np.mean(
                                    [
                                        not r[1][1][1].pred_pass and r[1][1][0].pred_pass
                                        for r in rows
                                    ]
                                )
                            )
                            if rows
                            else None
                        ),
                        config["statistics"],
                    ),
                    "passing_false_fail_effect": bootstrap(
                        passing_pairs,
                        lambda rows: -diff(rows, 0, 2) if rows else None,
                        config["statistics"],
                    ),
                }
            cells[wm][channel] = {
                "status": valid["kt_a"],
                "validity": valid,
                "baseline_ba": ba,
                "effect": effect,
                "misleading_change": misleading,
                "neutral_change": neutral,
                "S_nat": nat,
                "S_true": true,
                "kt_a_result": cell_result,
                "exploratory": exploratory,
                "parse_failures": sum(s.parse_status == "fail" for s in observed_scores),
                "score_count": len(observed_scores),
                "planned_score_count": len(expected_ids),
                "missing_scores": missing,
                "excluded_pairs": {
                    "effect": len(failing) - effect.n_pairs,
                    "S_nat": sum(bool(c.natural_text) for c in core) - nat.n_pairs,
                    "S_true": len(core) - true.n_pairs,
                },
                "source_item_ids": [
                    item.item_id
                    for item in items
                    if item.channel == channel
                    and any(s.item_id == item.item_id for s in observed_scores)
                ],
            }
        c_models[wm] = {}
        if cells[wm].get("C", {}).get("status") == "VALID":
            for rung, conditions, block in [
                ("A", ["NAT", "T0"], "kt_c_a"),
                ("B", ["CLAIM_POS", "NEU_A"], "kt_c_b"),
            ]:
                pools: dict[str, list[SelectionCandidate]] = defaultdict(list)
                for cand in candidates:
                    if (
                        cand.origin != "proposer"
                        or cand.R_exec is None
                        or cand.task_id not in task_map
                    ):
                        continue
                    matched = [
                        model_scores.get((cand.cand_id, "C", cond, block)) for cond in conditions
                    ]
                    if all(s is not None and s.parse_status == "ok" for s in matched):
                        pools[cand.task_id].append(
                            SelectionCandidate(
                                cand.cand_id,
                                cand.R_exec,
                                matched[0].R_sim,
                                matched[1].R_sim,
                                bool(
                                    re.search(
                                        config["selection"]["claim_lexicon"],
                                        cand.natural_text,
                                        re.I,
                                    )
                                ),
                            )
                        )
                if pools:
                    result = selection_bootstrap(
                        dict(pools),
                        config,
                        rung,
                        {task.task_id: i for i, task in enumerate(tasks)},
                        checkpoint=(checkpoint_root / f"{wm}-{rung}.json")
                        if checkpoint_root
                        else None,
                    )
                    c_models[wm][rung] = result
                    if rung == "B" and wm in ("wm_a", "wm_b"):
                        planned_ids = {i.item_id for i in planned if i.block == block}
                        observed_ids = {s.item_id for s in model_scores.values()}
                        c_results.append(
                            cell_c(result["amplification"], result["regret"], config["thresholds"])
                            if planned_ids and planned_ids <= observed_ids
                            else "UNAVAILABLE"
                        )
                elif rung == "B" and wm in ("wm_a", "wm_b"):
                    c_results.append("UNAVAILABLE")
    a = kt_a(a_cells)
    b = kt_b(b_cells, config["thresholds"])
    c = "NOT_RUN" if a == "KILL" else kt_c(c_results)
    emergent = any(
        wm in ("wm_a", "wm_b")
        and "A" in r
        and r["A"]["amplification"].lower is not None
        and r["A"]["amplification"].lower > 0
        and r["A"]["by_n"][max(config["selection"]["pool_sizes"])]["Enrich"].lower is not None
        and r["A"]["by_n"][max(config["selection"]["pool_sizes"])]["Enrich"].lower > 1
        for wm, r in c_models.items()
    )
    emergence_available = any(
        wm in ("wm_a", "wm_b")
        and "A" in result
        and result["A"]["amplification"].estimate is not None
        and result["A"]["by_n"][max(config["selection"]["pool_sizes"])]["Enrich"].estimate
        is not None
        for wm, result in c_models.items()
    )
    counts["candidates_per_task"] = {
        task.task_id: sum(c.task_id == task.task_id for c in candidates) for task in tasks
    }
    counts["parse_failures_by_model"] = {
        wm: sum(s.wm_id == wm and s.parse_status == "fail" for s in scores)
        for wm in config["scoring_order"]
    }
    counts["excluded_parse_item_ids"] = [
        f"{s.wm_id}:{s.item_id}" for s in scores if s.parse_status == "fail"
    ]
    return _dump(
        {
            "decision": overall(a, c, b),
            "kt_a": a,
            "kt_b": b,
            "kt_c": c,
            "emergence": "EMERGENT"
            if emergent
            else ("NOT_EMERGENT" if emergence_available else "UNAVAILABLE"),
            "cells": cells,
            "selection": c_models,
            "data_quality": counts,
            "source_score_count": len(scores),
            "source_item_ids": sorted(s.item_id for s in scores),
        }
    )
