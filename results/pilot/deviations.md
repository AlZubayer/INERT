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

## 2026-11-12: owner-authorized world-model failure isolation diagnostic

The owner authorized the fixed A–F mechanism-isolation protocol in
`results/pilot/WM_Failure_Isolation_Protocol.md` after the smoke gate failed.
This diagnostic is separate from official smoke, P0, and pilot scoring. A
deterministic 148-case maximum manifest, including the conditional eight-call
F2 variant, was fixed before any diagnostic inference under
`data/smoke/diagnostics/failure_isolation_20261112/`. The WM-C and exact
two-shard WM-B Q4_K_M weights were SHA-256 verified; the WM-B shards were
downloaded from their pinned Hugging Face revision. The diagnostic uses
independent response files and caches and preserves all earlier evidence.

The only intentionally varied diagnostic inputs are the synthetic controls in
A–C, the two existing prompt families in C–E, model size in E, and the
protocol's conditional `--parallel 1` runtime setting in F2. Frozen pilot
thresholds, seeds, text conditions, parsers, candidate code, MBPP tests,
prompt templates, scoring, and decision rules were not changed. No diagnostic
response was inserted into an official score file. Smoke scoring had already
started and failed; P0 and official pilot scoring had not started.

The fixed diagnostic completed A 8/8, B 20/20, C 16/16 plus four Docker
truth checks, D 16/16, E 80/80, and the conditional F2 8/8. F1 inspected
actual server logs and `/props`; the default had four 8,192-token slots, so
F2's `--parallel 1` comparison was required. F3 was not run because an
alternate quantization has no separate approval. WM-B's E calls all parsed,
but only 25/80 matched executed pass counts. The full GitHub-readable audit
is `results/pilot/WM_Failure_Isolation_Results_20261112.md`; exact inputs,
raw responses, cache evidence, and analysis remain under the isolated ignored
`data/` directory. No smoke gate was opened, and P0/pilot scoring remained
unstarted.

## 2026-11-12: owner-authorized direct pass-count diagnostic

The owner authorized one prospective 16-call diagnostic to separate test
counting, pass-count prediction, and terminal/tool interface effects. It
reused the four Docker-verified Stage-C synthetic source/assertion controls
without altering their code, tests, or ground truth. The new fixed system
message and DIRECT_COUNT/FIXED_DENOMINATOR final instructions appear exactly
in `results/pilot/Direct_Pass_Count_Diagnostic_20261112.md`. This interface
was used only in isolated diagnostic calls; no registered prompt, condition,
threshold, parser, seed, or decision rule changed.

The complete manifest was written before inference under
`data/smoke/diagnostics/direct_pass_count_20261112/`, SHA-256
`77f74e1283ff10236e71beb8e1c3c0d7f8ac929312cabee5b45a32c8b7c4b5d9`.
It records exact messages, source and Docker-truth hashes, sampling, server,
and SHA-256-verified WM-C and both WM-B weight shards. Independent caches,
raw API bodies, response metadata, and analysis are in that ignored
directory. All 16 calls were new cache misses; the two models ran
sequentially. Every response was a strict, parser-valid `RESULT` line with
the correct denominator. WM-C had 6/8 exact pass counts; WM-B had 8/8.
Supplying the denominator made no paired difference. No previous diagnostic,
smoke, or official pilot data were modified. The official smoke gate remains
closed; P0 and pilot scoring remain unstarted.

## 2026-11-12: owner-authorized real-candidate direct pass-count diagnostic

The owner authorized one fixed 16-call diagnostic on the four previously
selected, Docker-executed real MBPP candidates. It reused the exact
DIRECT_COUNT and FIXED_DENOMINATOR message templates from the prior synthetic
diagnostic, replacing only `solution.py` code and the three original test
assertions. All inputs were neutral T0. No existing primary or fallback
prompt, misleading-text condition, threshold, seed, parser, scoring rule,
model, or experimental-design definition was changed. This diagnostic is
separate from official smoke, P0, and pilot scoring.

The complete input manifest was written before inference under
`data/smoke/diagnostics/direct_real_candidates_20261112/`, SHA-256
`3ffba5941fdb81138e1d202df2860c3f569e28f4868ecd80cf1bfce35f1579d8`.
Candidate and original test hashes were checked against the smoke dataset
and previous failure-isolation T0 manifest. All four recorded results were
independently reproduced through the network-disabled Docker sandbox;
`docker_truth.json` SHA-256 is
`db0b534449e4c3cbb1d5a12a36c5c34f328f6ef01affb3b95875866ac2f8a310`.
The exact WM-C weight and both WM-B shards were SHA-256 verified. WM-C and
WM-B ran sequentially, with separate ignored caches. All 16 calls were new
cache misses, and raw API bodies, metadata, parsed outputs, and exact input
messages remain in the isolated ignored directory. Existing diagnostics,
smoke records, and pilot records were not overwritten.

All 16 responses were strict one-line `RESULT` outputs, but WM-C had one
wrong-denominator `3/6` response, so only 15/16 parsed. WM-C exact count was
3/8; WM-B exact count was 4/8. Neither model predicted the 2/3 candidate
exactly under either interface. The full evidence and historical T0
comparison are in
`results/pilot/Direct_Real_Candidates_Diagnostic_20261112.md`. The smoke
gate remains closed; P0 and pilot scoring have not begun.

## 2026-11-12: assertion/execution diagnostic blocked at fresh selection

The owner authorized a fixed eight-candidate, three-stage assertion-reading
and execution-reasoning diagnostic. The required selection was two previously
unseen candidates in each executed-result stratum (0/3, 1/3, 2/3, 3/3).
The existing three-task smoke pool has 29 unique candidates, with stratum
counts 13, **0**, 7, and 9 respectively. An audit of prior smoke scores,
archived items, diagnostic manifests/responses, and model-response caches
found five previously exposed candidate IDs; after those exclusions the
counts are 11, **0**, 6, and 7. The 1/3 shortage exists even before
exclusions. The deterministic selection therefore stopped with zero selected
candidates and **0/48 model calls**. No per-assertion Docker oracle was run.

The full selection audit is isolated under
`data/smoke/diagnostics/assertion_execution_20261112/selection_audit.json`,
SHA-256 `6def12845d6b69f9179efd649d34d0ac79ac2934df50cd26ed3219f6c4ad2845`.
Two preliminary audit snapshots were preserved alongside it. One was
refined to resolve nine historical cache requests whose code was JSON-escaped
inside tool-call text; the next was expanded to include archived score files.
Neither refinement changed the exposed set or the 1/3 shortage. The
GitHub-readable blocked-selection report is
`results/pilot/Assertion_Execution_Diagnostic_20261112.md`. No frozen
parameter, prompt, condition, parser, threshold, seed, or decision rule was
changed. Prior diagnostic artifacts and official score files were preserved.
The smoke gate remains closed; P0 and pilot scoring remain unstarted.

## 2026-11-12: owner-authorized fresh candidate acquisition for blocked assertion diagnostic

The owner authorized an isolated acquisition stage to remedy the empty fresh
`1/3` stratum that blocked the previously approved assertion/execution
diagnostic. This preparation is a deviation from the original pilot stage
order, not official pilot generation or scoring. No frozen condition,
threshold, seed, text template, parser, or decision rule was changed. The
unchanged pinned MBPP sanitized dataset, local Qwen2.5-Coder-7B-Instruct
Q4_K_M proposer, original proposer prompt, and network-disabled Docker
sandbox were used. All outputs and caches are isolated under
`data/smoke/diagnostics/assertion_candidate_acquisition_20261112/`; historical
smoke, diagnostic, and pilot records were preserved.

The complete 392-task eligible-unused list was sorted, shuffled with
`random.Random(20261111)`, and the first eight task IDs and all 128 possible
attempts were frozen before inference. The task-selection manifest SHA-256
is `463429468e371ac5cb4b9ab2ee3ecf885004f5b5392312ce7c17cf6b302d91e4`;
the attempt manifest SHA-256 is
`e558de4d853f2537e894bd6eb3f7b10cf166ca27af5a80f5fba080d9824906eb`.
All eight reference solutions passed `3/3` in a fresh Docker check. Five
complete task batches were processed, with 80 proposer calls, 79 unique
accepted candidates, and 79 original-three-test Docker executions. Six
importable `1/3` candidates were found across two tasks, so the authorized
early-stop condition fired after the fifth batch. The new Docker distribution
was 43 `0/3`, 6 `1/3`, 6 `2/3`, and 24 `3/3`; no result was unusable. The
freshness audit SHA-256 is
`a24bc890f40362a0e6cfcc3851fa52fea954c449fa80d76ced825e48a37ae2e9`.
The combined fresh pool now has 54, 6, 12, and 31 candidates in those
respective strata. Its status is `READY_FOR_SELECTION_REVIEW`, not a completed
diagnostic or a passed smoke gate. Full details and selected candidate hashes
are in `results/pilot/Assertion_Candidate_Acquisition_20261112.md`. The
48-call WM-B/WM-C diagnostic was not run; official smoke, P0, and pilot
scoring remain unstarted.

## 2026-11-12: owner-authorized balanced assertion diagnostic selection

The owner authorized resuming **only** the previously blocked selection stage
after fresh candidate acquisition. For this diagnostic alone, the `1/3`
stratum uses the predeclared two-candidate acquisition shortlist from
different tasks (`acq-mbpp-563-g00`, `acq-mbpp-622-g00`). The original
ascending-candidate-ID rule continues for `0/3`, `2/3`, and `3/3`. This is an
explicit prospective clarification of the diagnostic selection rule. It does
not alter the frozen pilot design, text conditions, thresholds, parser, seeds,
or statistical decisions.

The resumed selection independently reconciled all 29 original and 79 new
candidate records with their source, task, three original tests, Docker
executions, code hashes, and exposure audits. It rechecked all eight selected
aggregate outcomes through the network-disabled Docker sandbox, without a
per-assertion oracle. Historical inference sources (three item files, four
diagnostic manifests, four score files, 17 WM caches, including 300 cached
requests) were scanned; no acquired candidate ID, code hash, or source was
found in prior WM inputs. The selected eight have two per Docker result
stratum and three source tasks. One selected generated source contains a
top-level assertion, which was preserved and disclosed.

The ignored frozen manifest is
`data/smoke/diagnostics/assertion_execution_20261112/selection_resume/selection_manifest.json`,
SHA-256 `3aed60838f4c44dc5a8fa76b0bcf858ffb37f5d8de5c5ab8d267d0a50add37eb`.
Full source, exposure, and Docker evidence are in separate files in that
directory; `results/pilot/Assertion_Execution_Selection_20261112.md` is the
GitHub-readable report. No WM-B/WM-C diagnostic calls were made in this
selection stage, and no prior score, cache, diagnostic audit, official smoke
record, P0 record, or pilot result was overwritten. The original smoke gate
remains closed; P0 and pilot scoring remain unstarted.

