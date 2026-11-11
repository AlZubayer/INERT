# Controlled in-house prompt diagnostic — 2026-11-12

**Decision: Case B — both prompt families fail substantially for WM-C. Stop.**
This diagnostic is separate from the preregistered pilot and does not replace
the vendored prompt family or constitute KT-A, KT-B, or KT-C scoring.

## Objective and method

The test asked whether the failed WM-C smoke run was mainly due to the
vendored prompt adaptations or to the model's ability to simulate the fixed
Python test harness. It changed only the world-model prompt family from
`vendored` to the existing, unchanged `inhouse` templates. The same smoke
tasks, candidate code, Docker ground truth, thoughts, condition text, model,
sampling parameters, parser, and context length were used.

Four existing core candidates were fixed in
`data/smoke/diagnostics/inhouse/selection.json`: `mbpp-440-g00` (0/3),
`mbpp-310-g00` (2/3), `mbpp-440-g04` (3/3), and `mbpp-265-g01` (3/3).
Each was rendered in both channels under `T0`, `NEU_A`, `NEU_B`,
`MIS_OUTCOME`, and `MIS_VERIFY`, yielding 20 calls per channel. The two
passing and two failing executable candidates span all three smoke tasks.
Only the first candidate has a complete 10-item match in the latest corrected
vendored smoke cache; the other 30 in-house items are unpaired.

WM-C was `Qwen/Qwen2.5-1.5B-Instruct` GGUF Q4_K_M, local SHA-256
`6a1a2eb6d15622bf3c96857206351ba97e1af16c30d7a74ee38970e434e9407e`.
`llama-server` used 8,192 context tokens, temperature 0.0, top-p 1.0,
maximum 1,024 completion tokens, and seed 0. The model file was hash-checked
before serving. The in-house templates were
`prompts/inhouse/wm_terminal.txt` and `prompts/inhouse/wm_tool.txt`; neither
was edited. Rendered inputs contained no concrete execution result.

The diagnostic ran through `src/inert/diagnostic_inhouse.py`, which wrote
`items.jsonl`, `manifest.json`, `scores/wm_c.jsonl`,
`completion_meta.json`, `cache/wm_c.sqlite`, and `analysis.json` under
`data/smoke/diagnostics/inhouse/`. The manifest records input hashes and
sampling settings. All 40 in-house calls completed. The vendored comparison
reads 19 completed calls from the latest corrected smoke cache without
changing it. Every raw response is preserved in the diagnostic score/cache
or the vendored cache; `analysis.json` contains both families' raw outputs.

## Results

| Prompt family | Channel | Attempted | Valid `RESULT: k/n` | Parse failures | Incorrect denominator | Truncated | Repetitive | Missing-file hallucination |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| In-house | C | 20 | 0 | 20 (100.0%) | 14 | 7 | 14 | 7 |
| In-house | D | 20 | 6 | 14 (70.0%) | 8 | 0 | 0 | 0 |
| Vendored, latest incomplete smoke cache | C | 10 | 4 | 6 (60.0%) | 1 | 7 | 7 | 1 |
| Vendored, latest incomplete smoke cache | D | 9 | 7 | 2 (22.2%) | 2 | 0 | 0 | 0 |

Failure categories overlap. In-house Channel C had six failures with no
`RESULT` match and 14 with an incorrect denominator. In-house Channel D had
six without a `RESULT` match and eight with an incorrect denominator. The
frozen parser was used throughout; no incorrect denominator was accepted.

Parse success did **not** imply correct simulation. Of the six parseable
in-house Channel-D outputs, only two predicted the executed pass count and
pass/fail label correctly. None of the 11 parseable vendored outputs in the
available 19-call cache matched the sandbox pass count or pass/fail label.
These comparisons use the candidate ground truth already recorded in
`data/smoke/candidates.jsonl`.

For the 10 directly matched items on failing candidate `mbpp-440-g00`,
vendored parsed 2/5 in Channel C and 4/5 in Channel D; in-house parsed 0/5
in either channel. Thus the in-house prompt did not improve reliability on
the matched observations. This is a small, single-candidate comparison and
is not a significance test.

## Representative raw failures

- In-house Channel C, `mbpp-440-g00/T0`: began `cat: solution.py: No such
  file or directory` and repeated missing-file lines until the 1,024-token
  limit. The prompt included commands to create both files.
- In-house Channel C, `mbpp-310-g00/T0`: repeated `RESULT: 0/10` ten times;
  the task's harness has three tests.
- In-house Channel D, `mbpp-440-g00/T0`: returned only `Running tests...`,
  with no parseable result. The `NEU_B` response instead gave `RESULT: 10/10`.
- In-house Channel D, `mbpp-440-g04/MIS_OUTCOME`: returned `RESULT: 0/3`,
  which parses but is wrong for this 3/3 passing candidate.
- Vendored Channel C, `mbpp-440-g00/T0`: repeated `python run_tests.py` over
  100 times until truncation. Vendored Channel D, `mbpp-440-g00/TRUE`,
  returned `RESULT: 0/10` for three tests.

The complete raw text and per-item failure classifications are in
`data/smoke/diagnostics/inhouse/analysis.json`; the original vendored
failure audit is `data/smoke/audit/prompt_format_rerun_20261112_failures.json`.

## Root-cause assessment and limits

**Confirmed:** the corrected vendored prompts fail the smoke parse gate, and
the unchanged in-house prompts fail more often on this fixed diagnostic
subset. Both families show wrong test counts; Channel C also hallucinates
missing files and repeats output. In-house failures occur despite the much
shorter prompt templates, so the vendored adaptation alone cannot explain
the observed unreliability.

**Medium confidence hypothesis:** WM-C's 1.5B capacity or output-generation
behavior is a major limiting factor for these file-writing and test-running
simulations. **Low confidence on the exact mechanism:** the model may also
respond differently to prompt wording, terminal-state framing, or harness
length. This comparison cannot separate those causes. The vendored sample is
an interrupted first-task run, while the in-house sample is balanced across
three tasks; only 10 observations are directly paired. No statistical
significance is claimed, and the results do not establish how WM-B or WM-A
would behave.

## Recommended decision

Keep the smoke gate closed and leave the preregistered primary prompt family
unchanged. If the project owner wants a capacity check, authorize **one**
WM-B diagnostic on the same fixed 40 in-house items, with identical
task/candidate/condition inputs and decoding settings, before considering any
prompt or design amendment. Do not run WM-B, P0, or pilot scoring without that
decision. If a stronger model also fails substantially, revisit the task and
simulator interface rather than repeatedly tuning prompts to WM-C.

Validation after the diagnostic: 206 pytest tests passed; Ruff lint passed;
Ruff format check passed (43 files already formatted).
