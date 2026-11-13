import ast
import hashlib
import json
import re
import sqlite3
from collections import Counter
from contextlib import closing

import pytest

from inert.config import Paths, load_config
from inert.diagnostic_prompt_adaptation import (
    DiagnosticPaths,
    Response,
    _responses,
    multiline_harness,
    prepare,
    render_c_upstream,
    render_d_upstream,
)
from inert.harness import render_harness
from inert.parse import parse_result
from inert.render import _prompt, render_messages
from inert.schemas import Candidate, Task, read_jsonl, write_json


def _tests(source: str) -> list[str]:
    assign = next(node for node in ast.parse(source).body if isinstance(node, ast.Assign))
    return ast.literal_eval(assign.value)


def test_multiline_harness_changes_only_the_tests_layout() -> None:
    tests = ["import math\nassert f(\"a b\")==('a', 'b')", "assert f([1, 2])==[1]", "assert f('x')"]
    single, multi = render_harness(tests, 5), multiline_harness(tests, 5)
    assert _tests(multi) == _tests(single) == tests
    start, end = multi.index("TESTS = ["), multi.index("]\n\nclass _Timeout")
    assert multi[:start] == single[: single.index("TESTS = [")]
    assert multi[end:] == single[single.index("]\n\nclass _Timeout") :]
    assert multi[start:end].count("\n") == len(tests) + 1


def test_adapted_prompts_keep_source_tests_and_no_execution_truth(tmp_path) -> None:
    paths = Paths.discover()
    task = Task(
        task_id="fixture",
        source="fixture",
        prompt="Return x unchanged.",
        fn_name="f",
        tests=["assert f(1) == 1", "assert f(2) == 2", "assert f(3) == 3"],
        n_tests=3,
        reference_code="def f(x): return x",
    )
    candidate = Candidate.from_source(
        "fixture-g00", "fixture", 0, "proposer", "# natural note\ndef f(x): return x"
    )
    harness = render_harness(task.tests, load_config(paths)["sandbox"]["test_seconds"])
    current_c = render_messages(task, candidate, "C", "T0", "", "vendored", paths)
    adapted_c = render_c_upstream(task, candidate, "T0", "", harness, paths, 20)
    assert current_c[0] == adapted_c[0]
    action = json.loads(adapted_c[1].content.split("```json\n", 1)[1].split("\n```", 1)[0])
    assert action == json.loads(current_c[1].content)
    assert action[0]["keystrokes"].endswith("python run_tests.py\n")
    assert "RESULT: 3/3" not in adapted_c[1].content
    cloned = Paths(tmp_path, "smoke")
    directory = cloned.prompts / "vendored"
    directory.mkdir(parents=True)
    (directory / "wm_terminal.txt").write_bytes(
        (paths.prompts / "vendored" / "wm_terminal.txt").read_bytes()
    )
    turn = (paths.prompts / "vendored" / "wm_terminal_turn.txt").read_text(encoding="utf-8")
    (directory / "wm_terminal_turn.txt").write_bytes(turn.replace("\n", "\r\n").encode())
    crlf_c = render_c_upstream(task, candidate, "T0", "", harness, cloned, 20)
    assert crlf_c == adapted_c

    adapted_d = render_d_upstream(candidate, "Ready to test.", harness, paths)
    assert len(adapted_d) == 1
    content = adapted_d[0].content
    assert "No reference conversation" in content
    assert "Assistant: <tool_call>" in content
    assert "User/Tool response: Files written: solution.py, run_tests.py" in content
    assert "Thought: Ready to test." in content
    calls = [
        json.loads(value) for value in re.findall(r"<tool_call>\n(.+?)\n</tool_call>", content)
    ]
    assert len(calls) == 2
    assert calls[0]["arguments"]["files"] == {
        "solution.py": candidate.code_stripped,
        "run_tests.py": harness,
    }
    assert calls[1] == {"name": "run_command", "arguments": {"command": "python run_tests.py"}}
    assert "RESULT: 3/3" not in content


def test_upstream_turn_template_has_frozen_provenance() -> None:
    path = Paths.discover().prompts / "vendored" / "wm_terminal_turn.txt"
    source = path.read_text(encoding="utf-8")
    metadata = json.loads(source.split("<!--", 1)[1].split("-->", 1)[0])
    template = _prompt(path).replace("\r\n", "\n")
    assert metadata["repository"] == "Qwen/AgentWorldBench (Hugging Face dataset)"
    assert metadata["commit"] == "6b8d28437042434dcdd168434227ca0de408c5ba"
    assert metadata["license"] == "Apache-2.0"
    assert "prompts[turn_idx-1]" in metadata["adaptations"]
    assert hashlib.sha256(template.encode()).hexdigest() == metadata["prompt_sha256"]
    suffix = template[template.index("\n\nPlease analyze") :]
    assert hashlib.sha256(suffix.encode()).hexdigest() == metadata["instruction_suffix_sha256"]
    assert "{current_state}" in template and "{action_json}" in template


def test_duplicate_response_ids_fail_instead_of_being_overwritten(tmp_path) -> None:
    paths = DiagnosticPaths(tmp_path, "smoke")
    response = Response(
        case_id="one:T0:C0",
        model="wm_c",
        raw_output="RESULT: 0/3",
        finish_reason="stop",
        completion_tokens=7,
        latency_s=0.1,
        cache_hit=False,
        timestamp="2026-11-13T00:00:00+00:00",
    )
    write_json(paths.data / "responses/wm_c.json", [response.model_dump()] * 2)
    with pytest.raises(ValueError, match="Duplicate diagnostic response IDs"):
        _responses(paths, "wm_c")


def test_local_archive_accounting_without_inference() -> None:
    paths = DiagnosticPaths(Paths.discover().root, "smoke")
    if not (paths.data / "manifest.json").exists():
        pytest.skip("Ignored local diagnostic archive is absent.")
    cases = prepare(paths)
    assert len(cases) == len({case.case_id for case in cases}) == 594
    expected = {case.case_id: case for case in cases}
    truth = {
        candidate.cand_id: candidate.n_passed
        for candidate in read_jsonl(Paths(paths.root, "smoke").candidates, Candidate)
    }
    totals = Counter()
    groups: dict[tuple[str, str], Counter] = {}
    for model, assigned in (("wm_c", 594), ("wm_b", 264)):
        responses = _responses(paths, model)
        assert len(responses) == assigned
        assert set(responses) <= set(expected)
        assert all(response.model == model for response in responses.values())
        totals["records"] += len(responses)
        totals["cache_hits"] += sum(row.cache_hit for row in responses.values())
        for identifier, row in responses.items():
            assert row.finish_reason in ("stop", "length")
            assert row.completion_tokens is not None and row.completion_tokens <= 1024
            parsed = parse_result(row.raw_output, 3)
            totals["valid" if parsed.parse_status == "ok" else "invalid"] += 1
            case = expected[identifier]
            group = groups.setdefault((model, case.variant), Counter())
            group["calls"] += 1
            group["hits"] += row.cache_hit
            group["length"] += row.finish_reason == "length"
            group["valid"] += parsed.parse_status == "ok"
            group["exact"] += parsed.parse_status == "ok" and parsed.k_pred == truth[case.cand_id]
            group["wrong_n"] += parsed.parse_status == "fail" and parsed.n_pred is not None
        db_path = (paths.data / "cache" / f"{model}.sqlite").resolve().as_posix()
        with closing(sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)) as database:
            cached = database.execute("SELECT count(*) FROM calls").fetchone()[0]
            records = database.execute("SELECT key, request, response, completion FROM calls")
            requests = {}
            for key, request, body, completion in records:
                assert hashlib.sha256(request.encode()).hexdigest() == key
                payload = json.loads(request)
                assert all(
                    payload[name] == value
                    for name, value in load_config(paths)["sampling"]["wm"].items()
                )
                assert payload["server_flags_that_affect_output"]["context_size"] == 8192
                requests[json.dumps(payload["messages"], sort_keys=True)] = (
                    json.loads(body),
                    json.loads(completion),
                )
            for identifier, row in responses.items():
                messages = [message.model_dump() for message in expected[identifier].messages]
                body, completion = requests[json.dumps(messages, sort_keys=True)]
                assert completion["raw_output"] == row.raw_output
                assert completion["finish_reason"] == row.finish_reason
                assert body["choices"][0]["message"]["content"] == row.raw_output
        assert cached == assigned - sum(row.cache_hit for row in responses.values())
    assert totals == Counter({"records": 858, "cache_hits": 12, "valid": 425, "invalid": 433})
    assert groups[("wm_c", "C0")] == Counter(
        {"calls": 99, "hits": 2, "length": 82, "valid": 41, "exact": 15, "wrong_n": 37}
    )
    assert groups[("wm_c", "D1")] == Counter(
        {"calls": 99, "hits": 2, "length": 0, "valid": 57, "exact": 24, "wrong_n": 42}
    )
    assert groups[("wm_b", "C1")] == Counter(
        {"calls": 44, "hits": 0, "length": 34, "valid": 36, "exact": 13, "wrong_n": 0}
    )
