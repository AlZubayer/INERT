import hashlib
import json
import random
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

import numpy as np

from inert.audit import Progress
from inert.config import Config
from inert.schemas import Endpoint, write_json
from inert.stats import from_resamples


@dataclass(frozen=True)
class SelectionCandidate:
    cand_id: str
    executed: float
    full: float
    neutral: float
    claim: bool


def selection_metrics(
    pool: list[SelectionCandidate], config: Config, rng: np.random.Generator, rung: str = "A"
) -> dict[int, dict[str, float | None]]:
    if not pool:
        raise ValueError("Cannot select from an empty pool.")
    repetitions = config["repetitions"]
    order = np.argsort(rng.random((repetitions, len(pool))), axis=1)
    priorities = rng.random((repetitions, len(pool)))
    executed = np.array([x.executed for x in pool])
    full = np.array([x.full for x in pool])
    neutral = np.array([x.neutral for x in pool])
    claims = np.array([x.claim for x in pool])
    result = {}
    for n in config["pool_sizes"]:
        selected = order[:, : min(n, len(pool))]
        tie = np.take_along_axis(priorities, selected, axis=1)
        full_scores, neutral_scores = full[selected], neutral[selected]
        full_idx = np.argmax(
            np.where(full_scores == full_scores.max(axis=1, keepdims=True), tie, -1), axis=1
        )
        neutral_idx = np.argmax(
            np.where(neutral_scores == neutral_scores.max(axis=1, keepdims=True), tie, -1), axis=1
        )
        rows = np.arange(repetitions)
        chosen, neutral_chosen = selected[rows, full_idx], selected[rows, neutral_idx]
        denominator = config["assignment_probability"] if rung == "B" else float(claims.mean())
        result[n] = {
            "A": float(np.mean(full[chosen] - neutral[chosen])),
            "Regret": float(np.mean(executed[neutral_chosen] - executed[chosen])),
            "Gap_full": float(np.mean(full[chosen] - executed[chosen])),
            "Gap_neutral": float(np.mean(neutral[neutral_chosen] - executed[neutral_chosen])),
            "Enrich": float(claims[chosen].mean() / denominator) if denominator else None,
            "selected_claim_proportion": float(claims[chosen].mean()),
            "pool_claim_proportion": float(claims.mean()),
        }
    return result


def selection_bootstrap(
    tasks: dict[str, list[SelectionCandidate]],
    config: Config,
    rung: Literal["A", "B"],
    task_indices: dict[str, int] | None = None,
    checkpoint: Path | None = None,
) -> dict[str, Endpoint | dict]:
    selection, stats = config["selection"], config["statistics"]
    if selection["seed"] is None:
        raise ValueError("KT-C selection seed requires owner clarification.")
    keys = sorted(key for key, pool in tasks.items() if pool)
    sizes = selection["pool_sizes"]
    if not keys:
        missing = from_resamples(None, [], 0, 0, stats)
        return {"amplification": missing, "regret": missing, "by_n": {}}
    # Pool order is stable. Each bootstrap occurrence redraws assignments and 1,000 trials.
    draws = np.random.default_rng(selection["seed"])
    clusters = np.random.default_rng(stats["bootstrap_seed"])

    def evaluate(
        task_keys: list[str], observed: bool = False
    ) -> dict[int, dict[str, float | None]]:
        all_metrics = []
        for key in task_keys:
            pool = tasks[key]
            if rung == "B":
                if observed:
                    task_index = task_indices[key] if task_indices is not None else keys.index(key)
                    assign = random.Random(selection["assignment_seed_base"] + task_index)
                    planted = [assign.random() < selection["assignment_probability"] for _ in pool]
                else:
                    planted = draws.random(len(pool)) < selection["assignment_probability"]
                pool = [
                    SelectionCandidate(
                        x.cand_id,
                        x.executed,
                        x.full if planted[i] else x.neutral,
                        x.neutral,
                        bool(planted[i]),
                    )
                    for i, x in enumerate(pool)
                ]
            all_metrics.append(selection_metrics(pool, selection, draws, rung))
        combined = {
            n: {
                metric: float(
                    np.mean([m[n][metric] for m in all_metrics if m[n][metric] is not None])
                )
                if any(m[n][metric] is not None for m in all_metrics)
                else None
                for metric in ("A", "Regret", "Gap_full", "Gap_neutral", "Enrich")
            }
            for n in sizes
        }
        for n in sizes:
            numerator = float(
                np.mean([metric[n]["selected_claim_proportion"] for metric in all_metrics])
            )
            denominator = (
                selection["assignment_probability"]
                if rung == "B"
                else float(np.mean([metric[n]["pool_claim_proportion"] for metric in all_metrics]))
            )
            combined[n]["Enrich"] = numerator / denominator if denominator else None
        return combined

    identity = hashlib.sha256(
        json.dumps(
            {
                "pools": {key: [asdict(x) for x in tasks[key]] for key in keys},
                "config": config,
                "rung": rung,
                "task_indices": task_indices,
                "implementation_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            },
            sort_keys=True,
        ).encode()
    ).hexdigest()
    observed = evaluate(keys, True)
    samples = []
    if checkpoint is not None and checkpoint.exists():
        saved = json.loads(checkpoint.read_text(encoding="utf-8"))
        if saved["identity"] == identity:
            observed = {int(n): row for n, row in saved["observed"].items()}
            samples = [{int(n): row for n, row in sample.items()} for sample in saved["samples"]]
            draws.bit_generator.state = saved["draw_state"]
            clusters.bit_generator.state = saved["cluster_state"]

    def save_checkpoint() -> None:
        if checkpoint is not None:
            write_json(
                checkpoint,
                {
                    "identity": identity,
                    "observed": observed,
                    "samples": samples,
                    "draw_state": draws.bit_generator.state,
                    "cluster_state": clusters.bit_generator.state,
                },
            )

    save_checkpoint()
    progress = Progress(stats["bootstrap_resamples"], every=100)
    progress.done = len(samples)
    for _ in range(len(samples), stats["bootstrap_resamples"]):
        samples.append(evaluate([keys[i] for i in clusters.integers(len(keys), size=len(keys))]))
        if len(samples) % stats["checkpoint_every"] == 0:
            save_checkpoint()
        progress.advance()
    save_checkpoint()
    n_pairs = sum(len(tasks[key]) for key in keys)

    def summarize(value: float | None, values: list[float | None]) -> Endpoint:
        return from_resamples(
            value, [x for x in values if x is not None], n_pairs, len(keys), stats
        )

    first, last = min(sizes), max(sizes)
    by_n = {
        n: {
            metric: summarize(observed[n][metric], [s[n][metric] for s in samples])
            for metric in observed[n]
        }
        for n in sizes
    }
    return {
        "amplification": summarize(
            observed[last]["A"] - observed[first]["A"],
            [s[last]["A"] - s[first]["A"] for s in samples],
        ),
        "regret": by_n[last]["Regret"],
        "by_n": by_n,
    }
