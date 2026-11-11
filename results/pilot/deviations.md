# Pilot deviations and approved clarifications

## 2026-11-11: clarify unspecified statistical cases

Approved by the project owner in this session before any model scoring:

- Use seed `0`, read from `configs/pilot.yaml`, for KT-C pool draws and tie breaking.
- Classify a KT-C amplification confidence interval entirely below zero as
  `NO_AMPLIFICATION`. The original section 11.5 table did not cover this case.
- Report an endpoint with no usable paired data as unavailable. Do not assign a
  positive or negative verdict from missing data.

These clarify gaps in sections 11.1–11.5. No frozen numerical threshold or text
condition template was changed. No inference, P0, or pilot scoring had run when
these clarifications were recorded.

## 2026-11-12: clarify task tokenization and supplied test imports

Approved by the project owner before task sampling or model scoring:

- Use the `Qwen/Qwen2.5-Coder-7B-Instruct` tokenizer consistently for the
  strictly-under-1,500-token task filter. Count the task prompt, reference
  solution, and complete test code, including all required test imports.
- Prepend MBPP's supplied test imports to each applicable test string. Preserve
  the original assertions and the section 6.6 harness template. Use the same
  imported test strings for every candidate and experimental condition.
- Add boundary and import-dependent task tests, and verify the reference
  solutions inside the Docker sandbox after importing the supplied fixtures.

These clarify section 6.1 and the input to section 6.6. No pre-registered
threshold, condition, seed, or decision rule changed. No task sampling,
inference, P0, or pilot scoring had run when this clarification was recorded.

## 2026-11-12: clarify task weighting for natural-text enrichment

Approved by the project owner before any scoring:

- Rung A `Enrich(N)` is the mean selected-claim proportion across tasks divided
  by the mean claim proportion in each task's candidate pool. Give every task
  equal weight, including tasks with zero claims in both means.
- If the overall denominator is zero, report enrichment as unavailable. Do not
  exclude zero-claim tasks or impute an enrichment value.
- Obtain confidence intervals by the existing task-level clustered bootstrap.
  Record undefined bootstrap replicates in endpoint metadata.

This clarifies aggregation in section 11.5. No threshold or decision rule was
changed. No task sampling, model inference, P0, or pilot scoring had run.

## 2026-11-12: repair vendored Channel-D simulator output adaptation

Approved by the project owner after the isolated WM-C smoke run stopped. Of the
first 20 persisted smoke scores, Channel C parsed 11/11 and Channel D parsed
0/9. Every failed Channel-D raw output echoed the agent's Thought or command
instead of the test harness output. The vendored Simia prompt ended by asking
for the "next message" without a final, explicit instruction to return the
latest tool call's stdout. This is a Section 9.5 prompt-adaptation repair.

The following exact text is appended after substitution of the vendored
Channel-D prompt, for every Channel-D condition:

```text
For the latest run_command tool call, simulate `python run_tests.py` using the solution.py and run_tests.py shown above. Count the passing tests from those files; the agent's Thought is not a test result.
Do not echo the Thought, command, tool-call JSON, or an explanation.
Return only the test harness stdout as one line: RESULT: k/n
```

The source prompt file, task information, executable code, tests, thoughts,
condition text, frozen templates, thresholds, seeds, parser, and decision logic
were not changed. The adaptation supplies no execution result.

Cache-clearing action: archived the interrupted smoke score file and the WM-C
SQLite cache plus its WAL and SHM files under
`data/smoke/audit/channel_d_before_repair_20261112/`, then removed them from
their active locations. The smoke items will be rebuilt before rescoring.
Earlier Channel-D scores cannot be reused. No pilot cache or pilot score file
was touched.

Scoring had already started: isolated WM-C smoke scoring only (20 persisted
records); P0 and pilot KT-A/KT-B/KT-C scoring had not started.

The single repaired smoke rerun was stopped after 30 persisted WM-C scores:
Channel C parsed 16/18 (2 failures; 11.1%) and Channel D parsed 8/12
(4 failures; 33.3%). The four Channel-D failures returned `RESULT: 0/2` or
`RESULT: 1/2` for a task with three tests, so they failed the unchanged
denominator rule. The two Channel-C failures were a 1,024-token repetitive
output without `RESULT` and an output reporting missing files. The repair
improved Channel-D tool-output shape but did not meet the parse threshold.
No second prompt adjustment was made, and the smoke run remains incomplete.

## 2026-11-12: follow-up vendored simulator input-format repair

Approved by the project owner after the interrupted WM-C smoke rerun. The
previous run (30 persisted scores) remains a failed, incomplete smoke run;
none of its scores are experimental results.

- Channel C: the vendored terminal prompt expects a JSON array of actions
  with `keystrokes` and `duration`. The primary message previously sent raw
  shell text with no final Enter. The vendored-only renderer now packages
  the same unmodified shell commands as one JSON action, adds the trailing
  newline needed to execute `python run_tests.py`, and takes the simulation
  duration from the existing `sandbox.wall_seconds` configuration.
  The in-house fallback remains unchanged.
- Channel D: separate the existing appended output instruction from the
  vendored template with two newline characters. Add explicit instruction
  that the denominator `n` is `len(TESTS)` and includes both passing and
  failing entries. This is a prompt-adaptation clarification only; no
  execution result is supplied.
- Add regression tests for the vendored Channel C JSON action and the
  Channel D separator and denominator guidance.

No task, candidate code, test harness, agent thought, text-condition template,
model, seed, scoring threshold, frozen parser, or statistical decision rule
was changed. The vendored source prompt files and their provenance remain
unchanged. These are follow-up repairs to the assembled prompt format, not
evidence that the model will now parse reliably.

The previous smoke items and WM-C cached requests must **not** be reused to
represent these new prompt versions. Before any rerun, archive the active
smoke score file and WM-C SQLite cache (including WAL/SHM files) under a new
timestamped `data/smoke/audit/` folder, record the exact paths, and rebuild
all smoke items. No deletion or cache reset was performed by this GitHub
change. Inspect the first outputs and stop at the existing parse-failure gate
without further unapproved prompt changes.

A live smoke rerun and the full local pytest/Ruff suite have not been performed
as part of this remote code change; Codex must run them on the local machine.

## 2026-11-12: archive active smoke artifacts for corrected prompt rerun

After fast-forwarding to `3b2239a03b9623c96c4b2ad6774a9798bb899265`, the
local validation passed (184 pytest tests, Ruff lint, and Ruff format). The
previous active three-task smoke files contained 310 items, 30 persisted
WM-C scores, and 37 cached WM-C responses. With no INERT server lock or
`llama-server.exe` process present, the following files were moved to
`data/smoke/audit/prompt_format_before_rerun_20261111T204010Z/`:

- `data/smoke/items.jsonl` → `data/smoke/audit/prompt_format_before_rerun_20261111T204010Z/items.jsonl`
- `data/smoke/scores/wm_c.jsonl` → `data/smoke/audit/prompt_format_before_rerun_20261111T204010Z/wm_c.jsonl`
- `data/smoke/cache/wm_c.sqlite` → `data/smoke/audit/prompt_format_before_rerun_20261111T204010Z/wm_c.sqlite`
- `data/smoke/cache/wm_c.sqlite-wal` → `data/smoke/audit/prompt_format_before_rerun_20261111T204010Z/wm_c.sqlite-wal`
- `data/smoke/cache/wm_c.sqlite-shm` → `data/smoke/audit/prompt_format_before_rerun_20261111T204010Z/wm_c.sqlite-shm`

Historical archives were preserved. No pilot (non-smoke) cache or score file
was moved. The prior items and cached responses cannot be reused with the
corrected renderer. This records the cache-clearing action required by section
12.3. Scoring had already started in smoke only; P0 and pilot scoring had not.

## 2026-11-12: corrected renderer smoke rerun stopped at parse gate

The approved renderer changes were used to rebuild 310 isolated smoke items.
WM-C `kt_ab` scoring stopped at the existing parse-failure gate: the first
persisted batch had 5 failures among 10 scores (50%). At interruption, the
SQLite cache held 19 completed local calls: Channel C 6 failures in 10 calls,
Channel D 2 in 9, overall 8 in 19 (42.1%). The score file held the first 10;
the remaining nine completed calls are recoverable only from the cache. Full
failure evidence, including raw outputs and finish reasons, is in
`data/smoke/audit/prompt_format_rerun_20261112_failures.json`, and the
verification report is `results/pilot/Smoke_Renderer_Validation_20261112.md`.

Five Channel-C failures reached 1,024 tokens without a valid `RESULT` line,
including repeated commands and one missing-file hallucination. Another
Channel-C output ended with a wrong-denominator `RESULT: 1/1` after a valid
`RESULT: 3/3`; the frozen last-match parser rejected it. Two Channel-D outputs
returned `RESULT: 0/10` for a three-test task. No prompt, threshold, template,
seed, parser, or decision rule was changed in response. Scoring had begun in
the isolated smoke profile only; P0 and pilot scoring had not begun.

## 2026-11-12: controlled in-house prompt diagnostic

The project owner authorized a separate WM-C diagnostic to compare the
existing in-house Channel-C and Channel-D prompt templates with available
vendored smoke outputs. This is **not official pilot scoring** and does not
change the preregistered primary vendored prompt family. Both prompt template
files, all text conditions, parser rules, model settings, candidates, tests,
thoughts, and ground truth remain unchanged.

Diagnostic artifacts are isolated under `data/smoke/diagnostics/inhouse/`.
The fixed selection is recorded in `selection.json`: four existing core-set
candidates (two passing and two failing) across all three smoke tasks, with
`T0`, `NEU_A`, `NEU_B`, `MIS_OUTCOME`, and `MIS_VERIFY` in both channels. The
generated `items.jsonl` has 20 items per channel; `manifest.json` records
source hashes, sampling parameters, and context length. The small
`src/inert/diagnostic_inhouse.py` runner uses a separate WM-C cache and score
file, writing validated records after each call. Prior smoke scores, caches,
items, and audit files are not altered.

Reason: the corrected vendored smoke prompt still exceeded the 10% parse
failure gate; this fixed subset tests whether the prompt family contributes
to failures without tuning prompts. Model scoring had already started in
smoke, but P0 and official pilot scoring had not started.

The fixed 40-call in-house diagnostic completed. Its 20 Channel-C calls had
20 parse failures; its 20 Channel-D calls had 14. The latest corrected
vendored smoke cache supplied 10 Channel-C and 9 Channel-D historical calls
for comparison, with 6 and 2 parse failures respectively. Ten
task/candidate/channel/condition pairs were available across prompt families;
the others were explicitly unpaired. Parsed output was separately checked
against the existing sandbox ground truth. Full counts, overlapping failure
classifications, raw outputs, and pair records are in
`data/smoke/diagnostics/inhouse/analysis.json`. The diagnostic is summarized
in `results/pilot/Inhouse_Prompt_Diagnostic_20261112.md`.

Both prompt families failed substantially. No further model or prompt trial
was started, and no primary prompt-family amendment was made. The diagnostic
does not change frozen conditions, thresholds, seeds, parser rules, or
statistical decision rules. Pilot scoring had still not started.

