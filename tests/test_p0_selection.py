import hashlib
from collections import Counter
from pathlib import Path

import pytest

import inert.p0_selection as selection
from inert.audit import StopRequired
from inert.config import Paths, load_config
from inert.schemas import Candidate, Item, Message, Task, write_jsonl


def prepared_fixture(
    tmp_path: Path,
) -> tuple[Paths, dict, list[Task], list[Candidate], list[Item], dict]:
    paths = Paths(tmp_path)
    config = load_config()
    tasks = [
        Task(
            task_id=f"t{i}",
            source="handwritten_fixture",
            prompt="Return x",
            fn_name="f",
            tests=["assert f(0) == 0", "assert f(1) == 1", "assert f(2) == 2"],
            n_tests=3,
            reference_code="def f(x): return x",
        )
        for i in range(12)
    ]
    candidates = []
    items = []
    for task in tasks:
        for index in range(4):
            source = [
                "def f(x): return x",
                "def f(x): return x + 0",
                "def f(x): return x if x == 0 else 99",
                "def f(x): return x if x == 1 else 99",
            ][index]
            candidate = Candidate.from_source(
                f"{task.task_id}-c{index}", task.task_id, index, "proposer", source
            )
            candidate = Candidate(
                **{
                    **candidate.model_dump(),
                    "n_tests": 3,
                    "n_passed": 3 if index < 2 else 1,
                    "R_exec": 1.0 if index < 2 else 1 / 3,
                    "true_pass": index < 2,
                    "harness_output": "RESULT: 3/3\n" if index < 2 else "RESULT: 1/3\n",
                    "in_core_set": True,
                }
            )
            candidates.append(candidate)
            for channel in config["channels"]:
                for condition in config["conditions"]:
                    items.append(
                        Item(
                            item_id=f"{task.task_id}:{candidate.cand_id}:{channel}:{condition}:kt_ab:vendored",
                            task_id=task.task_id,
                            cand_id=candidate.cand_id,
                            channel=channel,
                            condition=condition,
                            block="kt_ab",
                            text="",
                            messages=[
                                Message(
                                    role="user",
                                    content=f"{candidate.cand_id}:{channel}:{condition}",
                                )
                            ],
                            prompt_family="vendored",
                        )
                    )
    model_file = paths.root / "data/models/wm_a/test.Q4_K_M.gguf"
    model_file.parent.mkdir(parents=True)
    model_file.write_bytes(b"handwritten test model metadata")
    registry = {
        "models": {
            "wm_a": {
                "source": "fixture/wm-a",
                "source_revision": "fixture-source",
                "gguf_revision": "fixture-gguf",
                "files": [
                    {
                        "filename": model_file.name,
                        "path": str(model_file.relative_to(paths.root)),
                        "sha256": hashlib.sha256(model_file.read_bytes()).hexdigest(),
                    }
                ],
            }
        }
    }
    write_jsonl(paths.tasks, tasks, Task)
    write_jsonl(paths.candidates, candidates, Candidate)
    write_jsonl(paths.items, items, Item)
    return paths, config, tasks, candidates, items, registry


def test_approved_p0_selection_is_balanced_and_deterministic(tmp_path: Path) -> None:
    _, config, tasks, candidates, items, _ = prepared_fixture(tmp_path)
    task_map, chosen = selection.select_p0_items(tasks, candidates, items, config)
    assert len(task_map) == 12
    assert len(chosen) == 100
    assert len({item.item_id for item in chosen}) == 100
    assert Counter(item.channel for item in chosen) == {"C": 50, "D": 50}
    assert Counter(item.task_id for item in chosen) == {
        **{f"t{i}": 9 for i in range(4)},
        **{f"t{i}": 8 for i in range(4, 12)},
    }
    assert {item.condition for item in chosen} == set(config["conditions"])
    assert [(item.channel, item.condition, item.cand_id) for item in chosen[:3]] == [
        ("C", "T0", "t0-c0"),
        ("D", "NEU_A", "t0-c0"),
        ("C", "NEU_B", "t0-c1"),
    ]


def test_selection_stops_for_missing_task_or_combination(tmp_path: Path) -> None:
    _, config, tasks, candidates, items, _ = prepared_fixture(tmp_path)
    with pytest.raises(StopRequired, match="12 distinct"):
        selection.select_p0_items(tasks[:11], candidates, items, config)
    _, chosen = selection.select_p0_items(tasks, candidates, items, config)
    missing = chosen[0].item_id
    with pytest.raises(StopRequired, match="unavailable"):
        selection.select_p0_items(
            tasks, candidates, [item for item in items if item.item_id != missing], config
        )


def test_manifest_is_frozen_and_checks_source_hashes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths, config, _, _, items, registry = prepared_fixture(tmp_path)
    monkeypatch.setattr(selection, "load_models", lambda _paths: registry)
    manifest = selection.prepare_p0_manifest(paths, config)
    assert manifest["wm_a"]["model_sha256"] == registry["models"]["wm_a"]["files"][0]["sha256"]
    assert len(manifest["assignments"]) == 100
    assert all("messages" in assignment for assignment in manifest["assignments"])
    assert "R_exec" not in paths.p0_manifest.read_text(encoding="utf-8")
    assert selection.prepare_p0_manifest(paths, config) == manifest
    loaded, _, selected = selection.load_p0_manifest(paths, config)
    assert loaded == manifest
    assert [item.item_id for item in selected] == manifest["item_ids"]
    original = paths.p0_manifest.read_bytes()
    changed = items[0].model_copy(update={"text": "altered"})
    write_jsonl(paths.items, [changed, *items[1:]], Item)
    with pytest.raises(StopRequired, match="does not match"):
        selection.load_p0_manifest(paths, config)
    assert paths.p0_manifest.read_bytes() == original
