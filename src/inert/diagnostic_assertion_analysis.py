"""Analyze the frozen 48-call assertion diagnostic without changing pilot rules."""

# ruff: noqa: E501  # Keep the generated Markdown evidence rows readable in source.

import argparse
import html
import json
import re
from collections import Counter

from inert.config import Paths
from inert.diagnostic_assertion_run import (
    ROLES,
    SELECTED_IDS,
    STAGES,
    RunPaths,
    _fixed_write,
    _sha256,
    response_path,
)
from inert.parse import parse_result
from inert.schemas import atomic_text


def parse_extraction(raw: str, expected: list[str]) -> dict:
    """Require a bare JSON array with three strings, preserving exact text."""
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return {
            "valid_json": False,
            "valid_structure": False,
            "exact": False,
            "decoded": None,
            "missing": None,
            "invented": None,
            "reordered": False,
            "duplicated": False,
        }
    valid = (
        isinstance(value, list) and len(value) == 3 and all(isinstance(item, str) for item in value)
    )
    if not valid:
        return {
            "valid_json": True,
            "valid_structure": False,
            "exact": False,
            "decoded": value,
            "missing": None,
            "invented": None,
            "reordered": False,
            "duplicated": False,
        }
    missing = list((Counter(expected) - Counter(value)).elements())
    invented = list((Counter(value) - Counter(expected)).elements())
    return {
        "valid_json": True,
        "valid_structure": True,
        "exact": value == expected,
        "decoded": value,
        "missing": missing,
        "invented": invented,
        "reordered": not missing and not invented and value != expected,
        "duplicated": len(set(value)) < 3,
    }


def parse_individual(raw: str) -> dict:
    """Require the complete fixed Stage-B one-line response."""
    match = re.fullmatch(r"TEST_RESULTS: ([PF]),([PF]),([PF])", raw.strip())
    return {"valid_format": match is not None, "vector": list(match.groups()) if match else None}


def parse_aggregate(raw: str) -> dict:
    """Preserve frozen parser acceptance while measuring strict display format."""
    parsed = parse_result(raw, 3)
    return {
        "strict_format": re.fullmatch(r"RESULT: \d+/\d+", raw.strip()) is not None,
        "parser_status": parsed.parse_status,
        "k_pred": parsed.k_pred,
        "n_pred": parsed.n_pred,
        "denominator_matches": parsed.n_pred == 3,
    }


def analyze(paths: RunPaths) -> dict:
    """Read only the frozen manifest, Docker oracle, source and 48 raw responses."""
    manifest_path = paths.data / "manifest.json"
    oracle_path = paths.data / "per_assertion_oracle.json"
    source_path = paths.data.parent / "selection_resume/source_archive.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    oracle = json.loads(oracle_path.read_text(encoding="utf-8"))
    source = json.loads(source_path.read_text(encoding="utf-8"))["rows"]
    if len(manifest["cases"]) != 48 or len(oracle["rows"]) != 8:
        raise ValueError("The diagnostic evidence is incomplete.")
    expected = {row["candidate_id"]: row for row in oracle["rows"]}
    tests = {row["candidate_id"]: row["tests"] for row in source}
    records: dict[str, dict] = {}
    for case in manifest["cases"]:
        path = response_path(paths, case)
        response = json.loads(path.read_text(encoding="utf-8"))
        if (
            response["case_id"] != case["case_id"]
            or response["input_sha256"] != case["input_sha256"]
        ):
            raise ValueError(f"Response provenance differs: {case['case_id']}")
        candidate, stage = case["candidate_id"], case["stage"]
        raw = response["raw_output"]
        truth = expected[candidate]
        if stage == "A":
            parsed = parse_extraction(raw, tests[candidate])
            parsed["correct"] = parsed["exact"]
            parsed["expected"] = tests[candidate]
        elif stage == "B":
            parsed = parse_individual(raw)
            vector = parsed["vector"]
            parsed["expected"] = truth["vector"]
            parsed["correct_tests"] = (
                sum(a == b for a, b in zip(vector, truth["vector"], strict=True)) if vector else 0
            )
            parsed["exact"] = vector == truth["vector"] if vector else False
            parsed["implied_k"] = vector.count("P") if vector else None
            parsed["correct"] = parsed["exact"]
        else:
            parsed = parse_aggregate(raw)
            parsed["expected_k"] = truth["n_passed"]
            parsed["correct"] = (
                parsed["parser_status"] == "ok" and parsed["k_pred"] == truth["n_passed"]
            )
            parsed["label_correct"] = parsed["parser_status"] == "ok" and (
                parsed["k_pred"] == 3
            ) == (truth["n_passed"] == 3)
        records[case["case_id"]] = {
            "case_id": case["case_id"],
            "stage": stage,
            "model_role": case["model_role"],
            "candidate_id": candidate,
            "task_id": case["task_id"],
            "input_sha256": case["input_sha256"],
            "raw_output": raw,
            "parsed": parsed,
            "prompt_tokens": response["prompt_tokens"],
            "completion_tokens": response["completion_tokens"],
            "finish_reason": response["finish_reason"],
            "cache_hit": response["cache_hit"],
        }
    pairs = []
    for role in ROLES:
        for candidate in SELECTED_IDS:
            a, b, c = (records[f"{stage}-{role}-{candidate}"] for stage in STAGES)
            av, bv, cv = a["parsed"], b["parsed"], c["parsed"]
            correct_b = bv["exact"]
            correct_c = cv["correct"]
            flags = {
                "type_1": not av["exact"],
                "type_2": av["exact"] and bv["valid_format"] and not correct_b,
                "type_3": correct_b and not correct_c,
                "type_4": bv["valid_format"] and not correct_b and correct_c,
                "type_5": correct_b and correct_c,
                "type_6": bv["valid_format"]
                and cv["parser_status"] == "ok"
                and bv["implied_k"] != cv["k_pred"],
            }
            pairs.append(
                {
                    "model_role": role,
                    "candidate_id": candidate,
                    "task_id": a["task_id"],
                    "truth_vector": expected[candidate]["vector"],
                    "truth_k": expected[candidate]["n_passed"],
                    "a_exact": av["exact"],
                    "b_vector": bv["vector"],
                    "b_implied_k": bv["implied_k"],
                    "c_pred_k": cv["k_pred"] if cv["parser_status"] == "ok" else None,
                    "flags": flags,
                }
            )
    summary = {}
    for role in ROLES:
        rp = [pair for pair in pairs if pair["model_role"] == role]
        aa = [records[f"A-{role}-{candidate}"]["parsed"] for candidate in SELECTED_IDS]
        bb = [records[f"B-{role}-{candidate}"]["parsed"] for candidate in SELECTED_IDS]
        cc = [records[f"C-{role}-{candidate}"]["parsed"] for candidate in SELECTED_IDS]
        confusion = {f"{truth}->{pred}": 0 for truth in "PF" for pred in "PF"}
        for pair in rp:
            if pair["b_vector"]:
                for truth, pred in zip(pair["truth_vector"], pair["b_vector"], strict=True):
                    confusion[f"{truth}->{pred}"] += 1
        conditional = [b for a, b in zip(aa, bb, strict=True) if a["exact"]]
        summary[role] = {
            "calls": 24,
            "a_valid_json": sum(x["valid_json"] for x in aa),
            "a_valid_structure": sum(x["valid_structure"] for x in aa),
            "a_exact": sum(x["exact"] for x in aa),
            "b_valid_format": sum(x["valid_format"] for x in bb),
            "b_correct_tests": sum(x["correct_tests"] for x in bb),
            "b_test_denominator_assigned": 24,
            "b_test_denominator_parsed": 3 * sum(x["valid_format"] for x in bb),
            "b_exact_vectors": sum(x["exact"] for x in bb),
            "b_conditional_correct_tests": sum(x["correct_tests"] for x in conditional),
            "b_conditional_test_denominator": 3 * len(conditional),
            "b_conditional_exact_vectors": sum(x["exact"] for x in conditional),
            "b_conditional_vector_denominator": len(conditional),
            "b_all_pass": sum(x["vector"] == ["P"] * 3 for x in bb),
            "b_all_fail": sum(x["vector"] == ["F"] * 3 for x in bb),
            "b_confusion": confusion,
            "c_parser_valid": sum(x["parser_status"] == "ok" for x in cc),
            "c_strict_format": sum(x["strict_format"] for x in cc),
            "c_denominator_matches": sum(x["denominator_matches"] for x in cc),
            "c_exact_count": sum(x["correct"] for x in cc),
            "c_label_correct": sum(x["label_correct"] for x in cc),
            "c_predicted_fractional": sum(
                x["k_pred"] in (1, 2) for x in cc if x["parser_status"] == "ok"
            ),
            "finish_lengths": Counter(
                records[f"{stage}-{role}-{candidate}"]["finish_reason"]
                for stage in STAGES
                for candidate in SELECTED_IDS
            ),
            "type_counts": {
                name: sum(pair["flags"][name] for pair in rp) for name in rp[0]["flags"]
            },
        }
        summary[role]["finish_lengths"] = dict(summary[role]["finish_lengths"])
    result = {
        "manifest_sha256": _sha256(manifest_path),
        "per_assertion_oracle_sha256": _sha256(oracle_path),
        "responses": [records[case["case_id"]] for case in manifest["cases"]],
        "pairs": pairs,
        "summary": summary,
    }
    _fixed_write(paths.data / "analysis.json", result)
    return result


def _cell(value: object) -> str:
    return html.escape(str(value), quote=False).replace("|", "&#124;").replace("\n", "<br>")


def render_report(paths: RunPaths, analysis: dict) -> str:
    """Create a self-contained GitHub review artifact from archived evidence."""
    manifest = json.loads((paths.data / "manifest.json").read_text(encoding="utf-8"))
    oracle = json.loads((paths.data / "per_assertion_oracle.json").read_text(encoding="utf-8"))
    lines = [
        "# Assertion-reading and execution-reasoning diagnostic — 2026-11-12",
        "",
        "## Executive finding",
        "",
        "**Complete: 48/48 local calls; the official smoke gate remains closed.** All eight Docker per-assertion vectors reproduced the frozen aggregate counts. The models show distinct format and reasoning failures; this diagnostic does not establish general ability from three tasks.",
        "",
        "## Frozen selection and Docker oracle",
        "",
        f"Selection manifest SHA-256: `{manifest['selection_manifest_sha256']}`. Source archive SHA-256: `{manifest['source_archive_sha256']}`. Frozen aggregate oracle SHA-256: `{manifest['aggregate_oracle_sha256']}`. Per-assertion oracle SHA-256: `{analysis['per_assertion_oracle_sha256']}`. Docker image: `{oracle['docker_image_id']}`. All eight source and ordered test hashes were verified before inference; eight code hashes were distinct.",
        "",
        "| Candidate | Task | Code SHA-256 | Tests SHA-256 | Import | Docker vector | Aggregate |",
        "|---|---|---|---|---|---|---|",
    ]
    for row in oracle["rows"]:
        lines.append(
            f"| `{row['candidate_id']}` | `{row['task_id']}` | `{row['code_sha256']}` | `{row['tests_sha256']}` | {row['load_status']} | {','.join(row['vector'])} | {row['aggregate_stdout'].strip()} |"
        )
    lines.extend(
        [
            "",
            "Every import succeeded. The detailed Docker runs distinguished assertion failure, other exception and timeout; all observed failed tests in this selection raised `AssertionError`. The original aggregate Docker output matched each frozen output exactly.",
            "",
            "## Inference provenance",
            "",
            f"Input manifest SHA-256: `{analysis['manifest_sha256']}`; 48 case-bound input hashes covering 24 distinct prompt messages, each assigned to both models and frozen before inference. Sampling: `{manifest['sampling']}`; context size: `{manifest['context_size']}`. Server: `{manifest['server']['path']}`; SHA-256 `{manifest['server']['sha256']}`; configured build `{manifest['server']['configured_build']}` and commit `{manifest['server']['configured_commit']}`; `--version` output `{_cell(manifest['server']['version_stdout'].strip() or manifest['server']['version_stderr'].strip())}`. One local model server was active at a time. Raw API responses and prompts are retained under ignored `data/smoke/diagnostics/assertion_execution_20261112/run_48/`. All 48 calls were new cache misses.",
            "",
        ]
    )
    for role in ROLES:
        model = manifest["models"][role]
        files = ", ".join(f"`{file['path']}` SHA-256 `{file['sha256']}`" for file in model["files"])
        lines.append(
            f"- **{role.upper()}**: `{model['source']}` revision `{model['source_revision']}`; pinned GGUF revision `{model['gguf_revision']}`; license `{model['license']}`; resolved identity `{model['resolved_identity']}`; {files}."
        )
    lines.extend(
        [
            "",
            "## Complete 48-call evidence",
            "",
            "Stage A expects the exact ordered three-string assertion array. Stage B expects the exact `TEST_RESULTS: P,F,P` form, with values varying by candidate. Stage C uses the frozen pilot parser; strict display format is measured separately. `Correct` means exact extraction, exact vector, or exact count for stages A, B, or C respectively. An invalid B output has no scored vector.",
            "",
            "| Model | Candidate | Stage | Complete raw output | Parsed output | Docker expected | Valid | Correct | Tokens prompt/completion | Finish |",
            "|---|---|---|---|---|---|---|---|---|---|",
        ]
    )
    for row in analysis["responses"]:
        p = row["parsed"]
        stage = row["stage"]
        if stage == "A":
            observed = (
                _cell(json.dumps(p["decoded"], ensure_ascii=False))
                if p["decoded"] is not None
                else "—"
            )
            expected = _cell(json.dumps(p["expected"], ensure_ascii=False))
            valid = p["valid_json"] and p["valid_structure"]
        elif stage == "B":
            observed = ",".join(p["vector"]) if p["vector"] else "—"
            expected = ",".join(p["expected"])
            valid = p["valid_format"]
        else:
            observed = f"{p['k_pred']}/{p['n_pred']}" if p["k_pred"] is not None else "—"
            expected = f"{p['expected_k']}/3"
            valid = p["parser_status"] == "ok"
        raw = _cell(row["raw_output"])
        lines.append(
            f"| {row['model_role'].upper()} | `{row['candidate_id']}` | {stage} | <code>{raw}</code> | {observed} | {expected} | {valid} | {p['correct']} | {row['prompt_tokens']}/{row['completion_tokens']} | {row['finish_reason']} |"
        )
    lines.extend(
        [
            "",
            "## Accuracy and failure mechanisms",
            "",
            "All denominators below are assigned candidates or assertions unless explicitly described as parsed-only. Invalid responses count as incorrect for coverage-adjusted accuracy; they do not enter the per-test confusion matrix.",
            "",
            "| Measure | WM-B | WM-C |",
            "|---|---:|---:|",
        ]
    )
    measures = [
        ("Stage A valid bare JSON", "a_valid_json", "/8"),
        ("Stage A valid three-string array", "a_valid_structure", "/8"),
        ("Stage A exact ordered extraction", "a_exact", "/8"),
        ("Stage B valid format", "b_valid_format", "/8"),
        ("Stage B correct assertions, assigned", "b_correct_tests", "/24"),
        ("Stage B exact vectors, assigned", "b_exact_vectors", "/8"),
        ("Stage C parser valid", "c_parser_valid", "/8"),
        ("Stage C strict display format", "c_strict_format", "/8"),
        ("Stage C denominator correct", "c_denominator_matches", "/8"),
        ("Stage C exact counts", "c_exact_count", "/8"),
        ("Stage C pass/fail labels", "c_label_correct", "/8"),
        ("Stage C fractional counts", "c_predicted_fractional", "/8"),
    ]
    for label, key, denominator in measures:
        lines.append(
            f"| {label} | {analysis['summary']['wm_b'][key]}{denominator} | {analysis['summary']['wm_c'][key]}{denominator} |"
        )
    for role in ROLES:
        s = analysis["summary"][role]
        lines.extend(
            [
                "",
                f"**{role.upper()} detail.** Among correctly extracted candidates, Stage B scored {s['b_conditional_correct_tests']}/{s['b_conditional_test_denominator']} individual assertions and {s['b_conditional_exact_vectors']}/{s['b_conditional_vector_denominator']} exact vectors. Among valid B responses it scored {s['b_correct_tests']}/{s['b_test_denominator_parsed']} assertions. Parsed all-PASS vectors: {s['b_all_pass']}/8; all-FAIL: {s['b_all_fail']}/8. Per-test confusion (truth→prediction): {s['b_confusion']}. Completion reasons: {s['finish_lengths']}.",
                "",
            ]
        )
    lines.extend(
        [
            "WM-B's four exact A outputs were all `mbpp-125`. One other A response was valid JSON but copied an incorrect second `mbpp-622` assertion; the three `mbpp-563` responses had unescaped quotation marks and were invalid JSON. No valid A array was reordered or duplicated. WM-C wrapped every A answer in a Markdown code fence, making all eight invalid as bare JSON; several also changed or failed to copy assertion text. These format failures prevent an unconditional claim that WM-C cannot identify assertions.",
            "",
            "All eight WM-B B responses stopped normally but omitted required syntax: seven visibly expressed all-PASS and one all-FAIL, yet none matched `TEST_RESULTS: P,F,P` structure. These visible strings are qualitative evidence only. WM-C gave eight valid B vectors, 12/24 correct individual outcomes and no exact vector. All 16 C responses were strict `RESULT: k/3`, with no denominator mismatch or truncation; both models got only the two 3/3 candidates' counts right.",
            "",
            "Conditional accuracy with a 0/0 denominator is undefined, not a measured zero percent. The WM-B per-test confusion matrix is empty because no B response met the fixed format.",
            "",
        ]
    )
    lines.extend(
        [
            "## Cross-stage comparison",
            "",
            "Types can overlap. Type 1: extraction incorrect. Type 2: extraction correct but B vector wrong. Type 3: B vector correct but C count wrong. Type 4: B vector wrong but C count right. Type 5: both right. Type 6: B implied count disagrees with C. Invalid B outputs do not yield a scored implied count; invalid A can coexist with a valid B vector.",
            "",
            "| Model | Candidate | Task | Docker vector/count | A exact | B vector/implied count | C count | Types |",
            "|---|---|---|---|---|---|---|---|",
        ]
    )
    for pair in analysis["pairs"]:
        types = (
            ", ".join(name.replace("type_", "") for name, active in pair["flags"].items() if active)
            or "—"
        )
        bv = ",".join(pair["b_vector"]) if pair["b_vector"] else "invalid"
        bk = pair["b_implied_k"] if pair["b_implied_k"] is not None else "—"
        ck = pair["c_pred_k"] if pair["c_pred_k"] is not None else "invalid"
        lines.append(
            f"| {pair['model_role'].upper()} | `{pair['candidate_id']}` | `{pair['task_id']}` | {','.join(pair['truth_vector'])} / {pair['truth_k']} | {pair['a_exact']} | {bv} / {bk} | {ck} | {types} |"
        )
    for role in ROLES:
        lines.append(
            f"\n{role.upper()} type counts (overlapping): {analysis['summary'][role]['type_counts']}."
        )
    lines.extend(
        [
            "",
            "## Partial-pass audit and task dependence",
            "",
            "The four partial-pass candidates are `mbpp-563-g00` (P,F,F), `mbpp-622-g00` (P,F,F), `mbpp-563-g10` (F,P,P), and `mbpp-563-g13` (F,P,P). WM-B produced no strictly valid B vector on these four; its raw B outputs were `TEST_RESULTS:PPP` for all three `mbpp-563` candidates and `P,P,P` for `mbpp-622-g00`. All four WM-B C calls predicted `RESULT: 3/3`. WM-C B returned `P,F,P` for `mbpp-563-g00` and `P,P,F` for the other three; none matched Docker. The B implied count of 2 agrees with the actual count for the two 2/3 candidates only by positional coincidence. All four WM-C C calls predicted `RESULT: 3/3`.",
            "",
            "Task-grouped candidate outcomes: `mbpp-125` has four candidates (two 0/3, two 3/3); `mbpp-563` has three (one 1/3, two 2/3); `mbpp-622` has one (1/3). Within `mbpp-125` the tests are identical while candidate code varies from 0/3 to 3/3. Within `mbpp-563` the tests are identical while code varies from 1/3 to 2/3. This outcome-balanced selection confounds some outcome strata with task identity. The 48 calls are repeated measurements on eight implementations from only three tasks, not 48 independent reasoning trials.",
            "",
            "| Model | Task | Candidates | A exact | B valid | B correct tests | B exact vectors | C exact counts |",
            "|---|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for role in ROLES:
        for task in ("mbpp-125", "mbpp-563", "mbpp-622"):
            pairs = [
                pair
                for pair in analysis["pairs"]
                if pair["model_role"] == role and pair["task_id"] == task
            ]
            by_case = {row["case_id"]: row["parsed"] for row in analysis["responses"]}
            a = [by_case[f"A-{role}-{pair['candidate_id']}"] for pair in pairs]
            b = [by_case[f"B-{role}-{pair['candidate_id']}"] for pair in pairs]
            c = [by_case[f"C-{role}-{pair['candidate_id']}"] for pair in pairs]
            lines.append(
                f"| {role.upper()} | `{task}` | {len(pairs)} | {sum(x['exact'] for x in a)}/{len(a)} | {sum(x['valid_format'] for x in b)}/{len(b)} | {sum(x['correct_tests'] for x in b)}/{3 * len(b)} | {sum(x['exact'] for x in b)}/{len(b)} | {sum(x['correct'] for x in c)}/{len(c)} |"
            )
    lines.extend(
        [
            "",
            "## Concrete failure examples",
            "",
            "- For `acq-mbpp-563-g00`, WM-C predicted `TEST_RESULTS: P,F,P`; Docker observed P,F,F. Its independent C output was `RESULT: 3/3`, versus actual 1/3. The generated source also contains a top-level assertion, but the Stage A outputs did not validly substitute it into the original test list.",
            "- For `acq-mbpp-125-g06`, WM-B copied all three assertions exactly in Stage A, then returned `F,F,F` without the required Stage B prefix. Its C output was `RESULT: 2/3`; Docker observed F,F,F and 0/3.",
            "- For `acq-mbpp-622-g00`, WM-B's Stage A JSON changed the second assertion's list from `[7, 13, 19, 28]` to `[7, 13, 17, 30, 45]`. Its B output was the invalid `P,P,P` and C output `RESULT: 3/3`, versus Docker P,F,F and 1/3.",
            "",
            "## Mechanism assessment and limitations",
            "",
            "Stage A format validity and exact-copy accuracy measure input extraction. They do not prove semantic understanding. Stage B measures per-assertion reasoning only when the fixed output is parseable; malformed but visually suggestive responses remain invalid. Stage C used the existing frozen parser. B and C are independent calls, so Type 3 and Type 6 indicate cross-call inconsistency, not proven arithmetic failure. The small, selected, task-dependent sample supports diagnosis only and does not revise any official pilot verdict or open the smoke gate.",
            "",
            "",
        ]
    )
    validation_path = paths.data / "validation.json"
    if validation_path.exists():
        validation = json.loads(validation_path.read_text(encoding="utf-8"))
        lines.extend(["## Validation", ""])
        for check in validation["results"]:
            lines.append(
                f"- `{_cell(' '.join(check['command']))}`: exit {check['returncode']}; "
                f"{_cell(check['output'].strip().splitlines()[-1]) if check['output'].strip() else 'no output'}."
            )
        lines.append("")
    lines.extend(
        [
            "**Next recommendation:** Review the Stage B format failures and the 1/3–2/3 execution predictions as a single owner decision on whether to authorize a separately preregistered diagnostic; keep official scoring paused.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("analyze", "report"))
    stage = parser.parse_args().stage
    paths = RunPaths(Paths.discover().root, "smoke")
    result = analyze(paths)
    if stage == "report":
        destination = paths.root / "results/pilot/Assertion_Execution_Diagnostic_Run_20261112.md"
        atomic_text(destination, render_report(paths, result))
        print(f"Wrote {destination}")
    else:
        print(
            f"Analyzed {len(result['responses'])} calls and {len(result['pairs'])} model-candidate pairs."
        )


if __name__ == "__main__":
    main()
