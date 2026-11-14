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

## 2026-11-12: owner-authorized frozen assertion diagnostic execution

The owner authorized the previously selected eight-candidate assertion-reading
and execution-reasoning diagnostic as a separate 48-call local study. This
diagnostic execution is outside the original pilot stage order and does not
change any frozen pilot condition, threshold, seed, parser, prompt template,
or decision rule. The frozen selection manifest SHA-256 was
`3aed60838f4c44dc5a8fa76b0bcf858ffb37f5d8de5c5ab8d267d0a50add37eb`.
The exact source and aggregate oracle archives passed their published checksums.

The separate network-disabled Docker per-assertion oracle verified eight
three-test vectors against all eight frozen aggregate outputs. Its SHA-256 is
`305c33612c6ab146c32c31d85ce27b1b776acc85c755d36f5915b3260955e3a8`.
All 48 Stage A/B/C prompts for WM-B and WM-C were frozen before inference in
`data/smoke/diagnostics/assertion_execution_20261112/run_48/manifest.json`,
SHA-256 `426b455f3b371d62fbaf483a900cc4489e626cff12b8bfec332dc1a61f4a0e9a`.
The local Q4_K_M GGUF hashes, server binary, and frozen decoding settings were
verified. The 48 calls completed with no cache hits; raw requests, responses,
Docker evidence, and derived analysis remain isolated in the ignored `run_48/`
directory. No historical or official score or cache was overwritten.

The GitHub-readable report is
`results/pilot/Assertion_Execution_Diagnostic_Run_20261112.md`. WM-B had 4/8
strict exact assertion extractions, 0/8 format-valid individual-test responses,
and 2/8 correct aggregate counts. WM-C had 0/8 strict bare-JSON extractions,
8/8 format-valid individual-test responses, 12/24 correct individual outcomes,
0/8 exact three-test vectors, and 2/8 correct aggregate counts. These are
diagnostic observations, not pilot results. The official smoke gate remains
closed; P0 and pilot scoring remain unstarted.


## 2026-11-13: prompt-adaptation diagnostic for the vendored channels

During the debugging session requested by the project owner, one isolated
diagnostic compared the current vendored message assembly with assemblies
closer to the upstream pipelines. It is outside the pilot stage order and is
not smoke, P0, or pilot scoring. `src/inert/render.py`, both vendored prompt
files, the in-house prompts, text conditions, sampling parameters, parser,
thresholds, seeds, and decision rules were not changed.

New vendored text: `prompts/vendored/wm_terminal_turn.txt` holds the user-turn
layout and instruction suffix that Qwen-AgentWorld's `eval/eval.py` sends from
the `Qwen/AgentWorldBench` dataset (revision
`6b8d28437042434dcdd168434227ca0de408c5ba`, Apache-2.0). Text only was copied,
after reading the first 3 MB of `terminal_test.jsonl` as data. It is used only
by the diagnostic. The 2026-11-14 audit corrected its metadata header to
`prompts[turn_idx-1]`, matching pinned `eval/eval.py`; the prompt body and
archived inference messages were unchanged. The diagnostic-only renderer
normalizes CRLF checkout line endings to preserve those exact messages on
Windows; no official renderer was modified.

The frozen manifest under
`data/smoke/diagnostics/prompt_adaptation_20261113/` contains 594 unique
prompt cases (11 smoke core-set candidates, nine conditions, variants
C0/C1/C2 and D0/D1/D2). WM-C completed all 594 assignments, and WM-B
completed another 264 (conditions T0, NEU_A, NEU_B, MIS_OUTCOME): **858
model-call records total**, comprising 846 new calls and 12 exact cache hits
for identical T0/NAT messages. The models ran one at a time with separate
isolated caches. No earlier score, cache, or diagnostic file was modified.

The tested upstream-style Channel-C turn worsened parser validity: WM-C
failures rose from 58/99 to 99/99; WM-B failures rose from 0/44 to 8/44.
The multiline C2 layout had 99/99 and 13/44 failures respectively. D1
changed role labels, the empty-reference placeholder, and formatting
together; WM-C failures fell from 64/99 to 42/99 but still exceeded the
frozen 10% gate. The label effect alone is not identifiable. WM-B's three
Channel-D variants had 0/44 parse failures and byte-identical raw outputs.
The C1/C2 upstream suffix also asks for reasoning and tagged observations,
which does not directly match the frozen `RESULT: k/n` parser; its parse
failures cannot be attributed solely to the turn header or action formatting.
No official renderer change was made. The small, three-task diagnostic does
not establish pilot model validity or KT-A endpoints; full findings and
limitations are in `results/pilot/Prompt_Adaptation_Diagnostic_20261113.md`.

Scoring had already started in smoke only. The smoke gate remains closed; P0
and pilot scoring remain unstarted.

## 2026-11-14: owner-authorized isolated WM-B engineering smoke, blocked before inference

The owner authorized an engineering-only WM-B substitution to test the existing
three-task smoke pipeline after repeated WM-C parsing failures. The registered
smoke configuration remains WM-C; this preparation used an in-memory WM-B
override and a separate ignored directory at
`data/smoke/diagnostics/wm_b_engineering_smoke_20261114/`. The original WM-C
failure evidence and scores remain in place. This substitution does not drop
WM-C from scientific scoring and does not reopen the original smoke gate.
No registered threshold, prompt, parser, text condition, primary endpoint,
seed, or decision rule was changed. P0 and official pilot scoring remain
unstarted.

The three-task dataset, 310 existing rendered items, and local WM-B model
were validated. The frozen engineering manifest SHA-256 is
`68e97583b023e9acec815c0e14c9db97343afec6b0375c5f94b7eadbe71a552d`.
Before any WM-B inference, the full pytest run changed one inventoried
historical file:
`data/smoke/diagnostics/assertion_execution_20261112/run_48/cache/sandbox.sqlite`
from SHA-256 `7722ab53d01b60f2af5f56597d913ea932e194abcabf37e652ce1ee54022c246`
to `0a02c5112a63710576970d47596fea6b914cfd205a15912d2369b7318ce96697`.
A pre-existing Docker oracle test wrote through the historical sandbox cache
even with `use_cache=False`. That test now uses a temporary cache. The other
586 inventoried files retained their hashes, and a second full test run made
no further historical changes. The original SQLite bytes are unavailable for
restoration, so the inventory was not silently rebaselined. The engineering
run stopped with **0/198 core calls** and no WM-B server start. The published
report `results/pilot/WM_B_Engineering_Smoke_20261114.md` records the blocker.

## 2026-11-14: accepted prospective baseline and sandbox cache repair

The owner explicitly approved recovery from the one historical cache
preservation failure with status
`HISTORICAL_PRESERVATION_EXCEPTION_ACCEPTED`. The original before-test
inventory and its failed hash comparison remain in the ignored engineering
directory. A separate prospective inventory adopts the current hash only for
`data/smoke/diagnostics/assertion_execution_20261112/run_48/cache/sandbox.sqlite`;
it does not relabel the original preservation check as passed. The current
database, an exact byte copy, a SQLite-consistent backup, and incident metadata
are retained under `data/smoke/diagnostics/wm_b_engineering_smoke_20261114/`.
The database passed `integrity_check` with 18 execution records. The earlier
per-assertion oracle evidence also survives in separate JSON records. No
trustworthy pre-test byte copy was found, so none was reconstructed.

`DockerSandbox.run(..., use_cache=False)` now executes Docker without opening
or writing a cache. Docker regression tests use temporary paths, and pytest
no longer opens historical diagnostic SQLite caches; exported response
accounting remains tested.
The full suite passed with 244 tests, and the prospective 587-file inventory
showed zero additional historical-file changes after validation. The frozen
198-call WM-B core manifest and pinned local model identities verified before
inference. The official smoke configuration remains WM-C; this approved
substitution stays engineering-only. No frozen scientific parameter changed.

The authorized 198-call WM-B core matrix then completed in its isolated
directory: 194 new local requests and four exact duplicate in-run cache hits.
The frozen parser accepted 198/198 responses (99/99 in each channel); there
were no denominator errors, missing result lines, or length finishes. Exact
Docker pass counts were predicted for 68/198 assignments. On the three-task
smoke sample, T0 balanced accuracy was 0.5833 in Channel C and 0.5000 in
Channel D; Channel D is below the registered 0.55 validity floor, while the
all-cells-INVALID stop rule did not fire. The 10% parse stop rule did not fire.
The prospective historical inventory showed zero additional modifications.
These are engineering-only observations, not a pilot verdict or a replacement
for the failed original WM-C smoke gate. No KT-C, P0, WM-A, WM-C, or official
pilot scoring was started.

## 2026-11-14: owner-approved deterministic P0 item selection

Before official pilot input preparation, the owner specified a deterministic
interpretation of design section 10's "100 items from the first 12 ready tasks
(any conditions)." Each task contributes eight KT-A/KT-B items; the first four
contribute one additional item. Core candidates are sorted by generation index
and ID, conditions retain the frozen config order, channels alternate as
specified in the preparation authorization, and the resulting 100 items must
be unique with 50 in each channel. This replaces the implementation's
first-100-in-file-order slice for P0 only. The frozen task sample, text
conditions, endpoints, thresholds, seeds, and pilot scoring populations remain
unchanged. No WM-A or official pilot scoring had started; historical smoke and
engineering diagnostic scoring had occurred.

## 2026-11-14: owner-approved P0 VRAM provenance rule

The owner required P0 peak VRAM to come from a completed live model trial and
to be persisted under a full trial identity before a cache-only restart may
reuse it. The identity includes model and server hashes, quantization, GPU
offload, context, server arguments, inference parameters, and the frozen P0
selection manifest hash. A missing, incomplete, or mismatched measurement
must stop P0 without a decision. This guards against reporting idle GPU memory
from a cache-only replay. The feasibility thresholds, timing data, parser,
sampling parameters, and token-escalation rule are unchanged. No WM-A or
official pilot scoring had started; historical smoke and engineering diagnostic
scoring had occurred.

## 2026-11-14: pilot task-stage historical cache preservation failure

The owner required all existing historical caches to remain unchanged during
P0 input preparation. A SHA-256 baseline was recorded before stages at
`data/p0/preparation_audit_20261114/historical_inventory_before.json`.
After `inert tasks` completed the frozen 50-task sample and 10 reserves,
the pre-existing `data/cache/sandbox.sqlite` changed from SHA-256
`956bbf780edafcc5d31b05461de14403113d92d8ea000703c9f6ea2e6aee7149`
to `5febe62370e779409019f7bef98d4afc63f37f21848dfb59101390f8a15650d2`.
The task stage used its configured pilot sandbox cache for reference checks;
this was an unintended preservation failure. The other 8,851 immutable
historical files matched their baseline hashes. The baseline also included
157 pytest temporary files under `data/pytest-tmp/`; those are classified
separately in the after-check and were not rebaselined.

The changed SQLite file passed `integrity_check` and contains 492 execution
records. An exact byte copy, a consistent SQLite backup, and incident metadata
are preserved under
`data/p0/preparation_audit_20261114/preservation_incident/`. No matching
copy of the original baseline bytes was found, so the original cache cannot
be restored byte for byte from available evidence. This new incident is not
covered by the earlier owner-accepted smoke diagnostic cache exception.
Preparation stopped before proposer inference, candidate execution, thoughts,
item construction, P0, or pilot scoring. The frozen task and reserve records
remain in their prescribed pilot paths; no historical inventory was silently
rebaselined. Owner direction is required before continuing data stages.

## 2026-11-14: second cache incident accepted prospectively

The owner explicitly approved `HISTORICAL_PRESERVATION_EXCEPTION_ACCEPTED_2`
for the distinct pilot task-stage sandbox cache incident above. The original
failed SHA-256 comparison remains in the unmodified inventory. A separate
prospective inventory at
`data/p0/preparation_audit_20261114/historical_inventory_prospective.json`
accepts the current SHA-256
`5febe62370e779409019f7bef98d4afc63f37f21848dfb59101390f8a15650d2`
only for `data/cache/sandbox.sqlite`. The other 8,851 protected historical
files retain their original hashes. The changed database passes SQLite
`integrity_check` with 492 records; all 13 archived import-dependent reference
checks remain present with matching source, harness, stdout, stderr, and return
code. The exact byte copy and consistent SQLite backup remain in the ignored
preservation-incident directory. The owner authorized a separate sandbox cache
for remaining pilot preparation and local proposer inference; no previous
history or original cache bytes were reconstructed. P0 and official pilot
scoring had not started.

The owner also clarified design section 10 timing: P0 decision latency is the
HTTP request-to-completed-response interval, excluding one-time server startup.
Startup is measured and reported separately. Live and cache-hit calls remain
distinct, and cache lookup time is not substituted for inference latency.
The 20- and 50-second P0 decision thresholds are unchanged. This clarification
was approved before any WM-A P0 call.

## 2026-11-14: resumed pilot input preparation and transient file-write interruption

The owner-approved prospective cache exception was applied only to
`data/cache/sandbox.sqlite`. The remaining preparation stages used an explicit
isolated Docker cache at
`data/p0/preparation_audit_20261114/sandbox_cache/sandbox.sqlite`; the original
cache retained prospective SHA-256
`5febe62370e779409019f7bef98d4afc63f37f21848dfb59101390f8a15650d2`.
The original failed hash comparison remains recorded above. All 8,852
protected files matched the prospective inventory after each stage. The
isolation and inventory correction did not change sandbox execution, cache
keys, model prompts, seeds, conditions, or decision thresholds.

The registered core-set reserve mechanism activated nine reserves in order:
`mbpp-593` to `mbpp-240`, `mbpp-253` to `mbpp-167`, `mbpp-611` to
`mbpp-457`, `mbpp-624` to `mbpp-417`, `mbpp-292` to `mbpp-230`, `mbpp-230`
to `mbpp-566`, `mbpp-90` to `mbpp-580`, `mbpp-118` to `mbpp-233`, and
`mbpp-750` to `mbpp-788`. These were prescribed replacements, not a changed
selection rule. Fifty tasks are core ready; one reserve remains.

The first `build-items` process stopped when Windows returned `WinError 5`
while atomically replacing `data/inertness.jsonl`. Its 948 completed checks
were schema-valid, unique, and PASS. No inertness failure occurred. The
registered stage was rerun once with the same inputs and isolated cache; it
reused passed-check records and completed 5,316 items with 3,678 PASS
Channel-C inertness records. No parser, harness, template, or scientific rule
was altered to handle the I/O interruption.

The frozen P0 input manifest is
`data/p0/selection_manifest.json`, SHA-256
`81431897467fe7a62821c44967c888bfd1b9bec9ae8520538470fe35051827e0`.
It selects 12 ready tasks and 100 existing items, 50 per channel, with all
nine registered conditions. The ignored source and final audits are under
`data/p0/preparation_audit_20261114/`. P0 itself and pilot scoring did not
run; the original WM-C smoke gate remains closed.

## 2026-11-14: owner-authorized P0 with WM-C smoke gate closed

**Status: `OWNER_AUTHORIZED_P0_WITH_WM_C_SMOKE_GATE_CLOSED`.** The official
three-task WM-C-only smoke failed the frozen parsing gate; its raw responses,
scores, caches, and failure records remain intact. The separately authorized
WM-B engineering smoke completed 198/198 core assignments with zero parse
failures, but does not replace or retroactively pass the WM-C smoke. The
official 50-task pilot inputs and frozen 100-assignment P0 manifest have now
been prepared. The project owner explicitly authorizes **WM-A P0 feasibility
only** despite the unresolved WM-C gate. This exception does not imply WM-C
validity or authorize WM-B, WM-C, KT-A, KT-B, KT-C, or full pilot scoring.
No preregistered threshold, endpoint, prompt, parser, condition, seed, or
decision rule changes. WM-A P0 had not started when this entry was recorded;
historical smoke and diagnostic scoring had already occurred.

## 2026-11-14: P0 load-attempt audit completion before WM-A inference

Pre-inference review found that the P0 runner logged failed offload layers but
did not persist their startup duration, server arguments, GPU observations,
and shutdown status as a structured record. This prevented the owner-requested
load audit. A narrow implementation change now writes
`data/p0/load_attempts.json` before and after each attempted setting. The
local server lifecycle attaches exact startup duration and log path to a
startup error and exposes successful startup and shutdown evidence. Each
record distinguishes OOM from non-OOM errors and cache-only replay; an absent
Q3 file is never marked as a tested failure. Regression tests use only fakes
and temporary files. No WM-A inference or P0 call had started when this repair
was made. The frozen model parameters, prompt, parser, thresholds, sample,
truncation rule, and decision table are unchanged.

## 2026-11-14: P0 process interrupted after 18 recorded calls

The local session stopped while the first Q4_K_M, 41-layer, 1,024-token
P0 trial was in progress. The WM-A cache contains 18 complete responses and
the matching live-measurement record contains exactly 18 observations; the
19th request was not completed or cached. The original llama-server process
with PID 31240 was no longer running, and port 8080 was free. Its stale lock
contained PID 31240 and was copied to
`data/p0/run_audit_20261114/stale_server_lock_31240.txt` (SHA-256
`79f785da0b1593cc0df17355122c2560e79289701938c03c2db1bcc120442777`)
before removal. The old server log and cache were retained. This is an
operational interruption, not a P0 outcome; the completed requests will be
reused with their original live latencies. The interrupted in-flight request
may be issued once on resumption because it left no recorded completion.

## 2026-11-14: P0 stopped on incomplete live GPU-memory evidence

The resumed Q4_K_M, 41-layer, 1,024-token P0 trial stopped at 62/100 cached
responses. `nvidia-smi` returned no valid single-GPU memory reading during
the 62nd request, and the runner raised `StopRequired` rather than inventing
a peak. The response for item `mbpp-633:mbpp-633-g10:D:NAT:kt_ab:vendored`
is cached under request key
`675281ba380346155c537838d325bf18de2e58f24b8b38dea854a5389e41478d`,
but only 61 of 62 calls have matching persisted live VRAM observations.
The cache and incomplete measurement record are preserved under `data/`;
the exact raw output remains in the cache. The single invalid `nvidia-smi`
stdout/stderr sample was not captured by the existing monitor, so its
underlying cause cannot be established. The server shut down and its lock
was removed. No 100-call trial, 2,048-token escalation, parse gate, or P0
decision was completed. No cache entry was deleted or replayed to fill the
measurement gap. This requires an owner-approved recovery protocol before
further P0 inference; no prompts, parser rules, settings, or thresholds were
changed in response.

## 2026-11-14: historical inventory excludes two generated bytecode files

The post-run immutable inventory initially reported zero changed protected
files and two added `statistics.cpython-311.pyc` files under the two vendored
Python `Lib/__pycache__/` directories. Both were created at 08:00:07 UTC by
the local audit script's `statistics` import, after the inventory freeze;
they are interpreter bytecode, not input data or historical evidence. The
ignored inventory script now excludes only those two exact paths and retains
the original hashes and scope for every frozen artifact. The first failed
inventory result was preserved in this record; the check is rerun below.

## 2026-11-14: owner-authorized isolated P0 call-62 telemetry replay

**Status: `OWNER_AUTHORIZED_P0_CALL62_TELEMETRY_REPLAY`.** The prior WM-A P0
trial stopped with 62/100 cached responses but only 61 matching live
latency/VRAM measurement observations. The original call-62 response for
`mbpp-633:mbpp-633-g10:D:NAT:kt_ab:vendored` remains in the original cache;
its missing VRAM value cannot be reconstructed. The owner authorizes at most
one independent replay of the exact request for telemetry validation, in a
separate cache and supplemental measurement record. The original request,
raw output, API response, latency, and incomplete measurement file must not
be altered, deleted, or silently completed. The replay output must be
compared byte for byte with the original. Any replay VRAM reading remains
separate evidence and is not adopted as the original reading without a
further owner-approved rule. This authorization does not permit P0 calls
63-100, the 2,048-token escalation, a P0 decision, or pilot scoring. It is
a measurement-protocol exception, not a change to the frozen scientific
design; WM-A P0 scoring had already begun before this entry.

The historical inventory's ignored runtime-artifact scope now also excludes
only `data/p0/telemetry_recovery_20261114/`, where the authorized replay
must write its separate cache and audit files. The frozen baseline hashes,
original WM-A cache, original 61-observation measurement file, pilot inputs,
and all other protected paths remain covered by their previous checks.
The same scope also excludes the new ignored
`data/p0/telemetry_attempts.jsonl` audit stream for any later authorized P0
continuation. The stream records raw polling attempts and does not alter the
original 61-observation measurement record.

Before the isolated replay, `gpu_telemetry.py` was added to serialize all
polling paths in one process and to audit every actual `nvidia-smi` attempt
with UTC and monotonic times, argv, return code, raw stdout/stderr, duration,
parse result, value, and acceptance. A poll allows one initial attempt and
at most two retries with a fixed 0.1-second delay. A positive integer from
the single detected GPU is required. Future authorized P0 polling passes an
explicit ignored audit path; the original P0 measurement record is not
modified. The one-call recovery command uses a separate SQLite cache, a
durable one-attempt guard, and a supplemental measurement file. Its request
key is checked against the original before inference. None of the frozen
prompts, parser, sampling values, seeds, thresholds, or decision logic was
changed. The pre-inference full suite passed 281 tests, and both Ruff checks
passed.

The earlier feasibility report abbreviated the original measurement filename
in prose. The actual unchanged file is
`data/p0/measurements/b9d09428692151008470b2de80be43b9cf5092093dee2d9ad70199d4db987099.json`
(SHA-256 `b7d7bb3744a12136b315d12cfdf13a6a5ce84f352107fab6a8f3ddb953587a46`).
The prior report is preserved; this entry records the path correction.

The isolated replay was claimed once and made exactly one new live HTTP
completion request with the original key
`675281ba380346155c537838d325bf18de2e58f24b8b38dea854a5389e41478d`.
The raw output matched the original byte for byte (SHA-256
`0efa5258550aa36b1b405032959e77bca7b6a6f9597be41d58a6388d00419db0`).
The replay API body hash was
`bb0453a20923513b875d439ca55630939562366f7d39f73d9a2cbeb3fdc4e59b`,
different from the original API body hash; these full response bodies were
preserved separately. Replay latency was 96.56296379998093 s versus the
original 106.37190800003009 s. Its independently sampled live peak was
15,774 MiB from 652 live samples; one additional accepted idle preflight
sample was recorded. All 653 telemetry invocations returned valid values,
so the bounded retry path was covered by mocks but was not exercised live.
No rejected telemetry attempt occurred. The replay cache contains one row,
the original cache still contains 62, and the original 61-observation
measurement file SHA-256 remains
`b7d7bb3744a12136b315d12cfdf13a6a5ce84f352107fab6a8f3ddb953587a46`.
An actual second invocation of the recovery command returned from the
one-replay guard without starting a server or another live request. The
replay measurement remains supplemental; it was not inserted into the
original P0 record. No P0 decision or subsequent scoring occurred.

The first post-report historical inventory check found no changed protected
file, but identified the new recovery report as an added file because that
path did not exist at the pre-P0 freeze. The ignored inventory helper now
excludes only the new report path in addition to the explicitly scoped new
runtime artifacts. It still compares the same 8,882 frozen current files
and 8,852 historical files against their original SHA-256 baselines. The
initial failed check is retained in this deviation record.
The corrected inventory rerun passed with 8,882/8,852 protected files; the
post-replay full test suite passed 281 tests, both Ruff checks passed, and
the WM-A server was stopped with no residual lock.
