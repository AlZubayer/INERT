from collections import defaultdict
from collections.abc import Callable, Sequence
from typing import TypeVar

import numpy as np

from inert.config import Config
from inert.schemas import Endpoint

T = TypeVar("T")


def balanced_accuracy(truth: Sequence[bool], prediction: Sequence[bool]) -> float | None:
    if len(truth) != len(prediction):
        raise ValueError("Truth and predictions must have equal lengths.")
    strata = [
        [float(t == p) for t, p in zip(truth, prediction, strict=True) if t == level]
        for level in (False, True)
    ]
    if not all(strata):
        return None
    return float(np.mean([np.mean(values) for values in strata]))


def from_resamples(
    estimate: float | None,
    resamples: list[float],
    n_pairs: int,
    n_tasks: int,
    config: Config,
    reason: str | None = None,
) -> Endpoint:
    if estimate is None or not resamples:
        return Endpoint(
            estimate=None,
            lower=None,
            upper=None,
            n_pairs=n_pairs,
            n_tasks=n_tasks,
            n_resamples=config["bootstrap_resamples"],
            n_valid_resamples=0,
            reason=reason or "No usable paired data or estimable bootstrap resamples.",
        )
    alpha = (1 - config["confidence"]) / 2
    lower, upper = np.quantile(resamples, [alpha, 1 - alpha])
    return Endpoint(
        estimate=float(estimate),
        lower=float(lower),
        upper=float(upper),
        n_pairs=n_pairs,
        n_tasks=n_tasks,
        n_resamples=config["bootstrap_resamples"],
        n_valid_resamples=len(resamples),
    )


def bootstrap(
    rows: list[tuple[str, T]],
    statistic: Callable[[list[tuple[str, T]]], float | None],
    config: Config,
) -> Endpoint:
    groups: dict[str, list[tuple[str, T]]] = defaultdict(list)
    for row in rows:
        groups[row[0]].append(row)
    keys = sorted(groups)
    estimate = statistic(rows) if rows else None
    values = []
    rng = np.random.default_rng(config["bootstrap_seed"])
    if estimate is not None:
        for _ in range(config["bootstrap_resamples"]):
            sampled = [
                row for i in rng.integers(len(keys), size=len(keys)) for row in groups[keys[i]]
            ]
            value = statistic(sampled)
            if value is not None and np.isfinite(value):
                values.append(value)
    return from_resamples(estimate, values, len(rows), len(keys), config)
