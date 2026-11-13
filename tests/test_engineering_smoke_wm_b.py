"""Pre-inference checks for the isolated WM-B engineering runner."""

from collections import Counter
from pathlib import Path

import pytest

from inert.config import Paths, load_config
from inert.engineering_smoke_wm_b import (
    CONDITIONS,
    EngineeringPaths,
    engineering_config,
    message_hash,
    validate_dataset,
)
from inert.parse import parse_result
from inert.render import render_messages


def test_paths_and_in_memory_override_are_isolated() -> None:
    root = Paths.discover().root
    official = Paths(root, "smoke")
    isolated = EngineeringPaths(root, "smoke")
    assert isolated.data != official.data
    assert isolated.results != official.results
    assert isolated.cache("wm_b") != official.cache("wm_b")
    assert isolated.scores("wm_b") != official.scores("wm_b")
    assert isolated.data.is_relative_to(official.data / "diagnostics")
    assert load_config(official)["scoring_order"] == ["wm_c"]
    assert engineering_config(isolated)["scoring_order"] == ["wm_b"]
    assert load_config(official)["scoring_order"] == ["wm_c"]


def test_frozen_matrix_and_renderer() -> None:
    paths = Paths(Paths.discover().root, "smoke")
    if not paths.items.exists():
        pytest.skip("Ignored local smoke dataset is absent.")
    config = engineering_config(paths)
    tasks, candidates, items = validate_dataset(paths, config)
    assert len(tasks) == 3
    assert len({item.item_id for item in items}) == len(items)
    core = [item for item in items if item.block == "kt_ab"]
    assert len(core) == 198
    assert Counter((item.channel, item.condition) for item in core) == Counter(
        {(channel, condition): 11 for channel in ("C", "D") for condition in CONDITIONS}
    )
    task_map = {task.task_id: task for task in tasks}
    cand_map = {cand.cand_id: cand for cand in candidates}
    for channel in ("C", "D"):
        for condition in CONDITIONS:
            item = next(i for i in core if i.channel == channel and i.condition == condition)
            rendered = render_messages(
                task_map[item.task_id],
                cand_map[item.cand_id],
                channel,
                condition,
                item.text,
                "vendored",
                paths,
            )
            assert item.messages == rendered
            assert message_hash(item) == message_hash(
                item.model_copy(update={"messages": rendered})
            )
    assert config["sampling"]["wm"] == {
        "temperature": 0.0,
        "top_p": 1.0,
        "max_tokens": 1024,
        "seed": 0,
    }
    assert config["server"]["context_size"] == 8192


def test_official_parser_is_strict_about_denominator() -> None:
    assert parse_result("RESULT: 2/3", 3).parse_status == "ok"
    assert parse_result("RESULT: 2/4", 3).parse_status == "fail"
    assert parse_result("No result", 3).parse_status == "fail"


def test_existing_artifacts_are_outside_new_output_directory() -> None:
    root = Paths.discover().root
    isolated = EngineeringPaths(root, "smoke")
    previous = [
        root / "data/smoke/scores/wm_c.jsonl",
        root / "data/smoke/cache/wm_c.sqlite",
        root / "data/smoke/diagnostics/prompt_adaptation_20261113",
    ]
    assert all(not Path(path).is_relative_to(isolated.data) for path in previous)
