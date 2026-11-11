from inert.config import Config
from inert.schemas import Candidate, Item, Task


def model_items(
    items: list[Item],
    tasks: list[Task],
    candidates: list[Candidate],
    config: Config,
    model: str,
    p0_decision: str,
) -> list[Item]:
    if model != "wm_a" or p0_decision != "reduced":
        return items
    selected_tasks = {t.task_id for t in tasks[: config["reduced"]["tasks"]]}
    selection_pool = set()
    for task in selected_tasks:
        group = sorted(
            [c for c in candidates if c.task_id == task and c.origin == "proposer"],
            key=lambda c: c.gen_index,
        )
        selection_pool.update(c.cand_id for c in group[: config["reduced"]["candidates"]])
    return [
        item
        for item in items
        if item.task_id in selected_tasks
        and item.channel == "C"
        and (
            item.block == "kt_ab"
            and item.condition in config["reduced"]["conditions"]
            or item.block.startswith("kt_c_")
            and item.cand_id in selection_pool
        )
    ]
