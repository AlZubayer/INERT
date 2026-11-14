# INERT-INTERFACE-001 — Local World Models as Execution Predictors

## 1. Study identity and status

**Version:** 1.0.0. **Prepared:** 2026-11-14. **Status:** `PROTOCOL_LOCKED_PENDING_OWNER_APPROVAL`. This is a **new prospective engineering-feasibility study**, prepared after the historical INERT diagnostics. The base repository commit is `5226cf42df389d7611d7f0320d7b01bbe49cd649`; the publication commit is identified by Git history for this file. The canonical protocol identity is the SHA-256 of this file's UTF-8 text after CRLF-to-LF normalization, recorded in the ignored manifest and the companion approval request. A repository commit establishes the locked version; it does **not** authorize inference. The analysis plan version is 1.0.0. No study response exists at preparation.

## 2. Motivation from the original pilot

The frozen [pilot design](../../Pilot_Experimental_Design.md) and [viability assessment](INERT_Research_Viability_Assessment_20261114.md) remain unchanged. WM-A Q4 loaded, but its P0 trial stopped at 62/100 calls, with 53/62 unparseable responses; the first-pass median is bounded below by 95.10 s. WM-B parsed 198/198 engineering-smoke assignments but predicted 68/198 exact counts, and its three-task Channel-D T0 balanced accuracy was 0.50. WM-C's official smoke gate is closed. These are historical motivations, **not** results of this study and not formal P0 or KT-A/B/C outcomes. The new study asks whether the local WM-B interface and prediction task are fit for future science before any more INERT scoring.

## 3. Research questions

- **RQ-I1, output validity:** Does WM-B produce a completed, machine-parseable test pass count, as distinct from a result embedded in unfinished reasoning, a truncated response, a malformed answer, or a wrong denominator?
- **RQ-I2, execution discrimination:** Does it identify failing candidates more reliably than an always-pass predictor?
- **RQ-I3, interface effect:** Does one explicit execution-prediction interface improve finalized-answer validity or discrimination relative to the unchanged vendored interface on paired assignments?
- **RQ-I4, operations:** Can a cell meet the preregistered accuracy/format criteria inside the bounded local compute allocation?

## 4. Scope and exclusions

One local model, two interface families, two channels, T0 only, 24 tasks, one passing and one failing core candidate per task. There are 48 development and 144 held-out assignments, **192 maximum**. No misleading or neutral text conditions are varied. This study does not test inert-text influence, stripping cost, selection regret, WM-A, WM-C, training, hosted inference, or generated-code execution. Its categories cannot alter the original P0 or assign KT-A/B/C or Section 11.6 verdicts.

## 5. Model and environment

Use only `Qwen/Qwen2.5-7B-Instruct`, source revision `a09a35458c702b33eeacc393d103063234e8bc28`, Apache-2.0, official Q4_K_M GGUF revision `bb5d59e06d9551d752d08b292a50eb208b07ab1f`. The two local shards must hash to `dfce12e3862a5283ccfb88221b48480e58745165de856439950d0f22590580db` and `539cf93f78e887edea1c04e2d7d8cdaca9d01dae9c9025bcb8accbe29df3d72a`. Their archived combined model identity is `c15612e12f1910d8008f894b772c7836a875cbf29911036c17c665ba519b2dfa`. The local llama-server binary must hash to `00d50686815af38249d0218c91558fbd0e9093ac8c074bac86196907f4305e31` (build `b12110`, commit `cd959bae9`). Bind to `127.0.0.1:8080`; context 8,192; 99 GPU layers; `--jinja --reasoning-format none`; temperature 0, top-p 1, seed 0, max completion tokens 1,024; request timeout 300 s. Use one server at a time. Exact server flags and arguments are copied from the verified WM-B engineering manifest into the new manifest. Identity mismatch stops before a request. No new model or decoding setting is permitted within version 1.0.0.

## 6. Interface definitions

**A, unchanged vendored baseline:** For each task/candidate/channel, render the existing `T0` official `kt_ab` messages with `src/inert/render.py`. Channel C uses the existing vendored terminal system prompt and JSON keystroke action; Channel D uses the existing vendored tool simulator prompt, stripped `solution.py`, fixed `run_tests.py`, no Thought, and `python run_tests.py`. The exact rendered messages must equal the corresponding existing `data/items.jsonl` T0 records. Do not edit `prompts/vendored/` or any appended official renderer instruction.

**B, one explicit prediction interface:** The three study-specific templates are committed under `prompts/interface_study_001/` and are used verbatim after LF newline normalization and replacement of only the named slots. The full text follows. There are no examples containing selected answers.

System (`interface_b_system.txt`):

```text
You are a local execution-outcome predictor for Python 3.11. The proposed action writes solution.py and run_tests.py and then runs python run_tests.py. Predict how many entries in TESTS will pass when the supplied executable code is used. Base the prediction only on that code and those tests. Do not claim to have run the program.
Return exactly one final line in this form: RESULT: k/n
Use the supplied n, which equals len(TESTS). k must be an integer from 0 through n. Do not include reasoning, a think block, commentary, code fences, a tool transcript, or any other result line.
```

Channel C user (`interface_b_channel_c.txt`):

```text
Channel C proposed terminal action (JSON keystrokes; no preceding files exist):
{action_json}

The test list has n = {n_tests} entries. Predict the number that pass. Return only the final RESULT line.
```

Channel D user (`interface_b_channel_d.txt`):

```text
Channel D proposed tool-use conversation. The latest run_command has not yet returned:
{conversation}

The test list has n = {n_tests} entries. Predict the number that pass. Return only the final RESULT line.
```

For B-C, `{action_json}` is the exact existing T0 Channel-C user JSON. For B-D, `{conversation}` is the exact `render_conversation(task, candidate, "")` with no Thought. `{n_tests}` is the original task's recorded test count, never a result. The system asks for a single final `RESULT: k/n` line. Native server reasoning may still appear in raw output; the validity metric below handles it. B does not receive executed answers or new correctness claims.

## 7. Development and held-out populations

The six development tasks, in the first-six order of the frozen 12-task P0 manifest, are `mbpp-440`, `mbpp-265`, `mbpp-310`, `mbpp-133`, `mbpp-447`, and `mbpp-291`. All had completed prior world-model responses. Development is solely an engineering check and is never pooled into held-out feasibility decisions.

The 18 held-out tasks, selected with `random.Random(20261114).sample(sorted(eligible_ids), 18)` from the official 50-task sample after task-level exposure exclusion and Docker-pair eligibility, are: `mbpp-171`, `mbpp-452`, `mbpp-766`, `mbpp-788`, `mbpp-726`, `mbpp-739`, `mbpp-246`, `mbpp-731`, `mbpp-106`, `mbpp-68`, `mbpp-619`, `mbpp-63`, `mbpp-240`, `mbpp-417`, `mbpp-579`, `mbpp-87`, `mbpp-103`, `mbpp-725`. There are 41 eligible unexposed official tasks before this draw. The split and source identities are fixed in `data/interface_study_001/task_split.json`; no task may be replaced after any development response. A future response involving a purportedly held-out task before authorization is a protocol violation, not a reason to resample.

## 8. Task and candidate selection

The exposure registry scans completed official smoke scores and caches, archived smoke scores and cached extras, WM-B engineering scores/raw responses, diagnostic world-model response files, the original 62 WM-A cache requests, and the isolated call-62 replay. It records every task ID associated with a completed world-model prediction and the supporting relative source path. The registry finds **11 exposed task IDs overall, nine within the official 50**: `mbpp-125`, `mbpp-133`, `mbpp-265`, `mbpp-291`, `mbpp-310`, `mbpp-440`, `mbpp-447`, `mbpp-633`, `mbpp-794`. The remaining two exposed IDs are `mbpp-563` and `mbpp-622`, outside the official 50. The output-prediction definition of exposure intentionally excludes proposer-only code generation: the proposer necessarily saw all official task prompts while creating candidates, but was not the WM-B execution predictor. **The owner must approve this definition before inference.** Planned but unrun P0 assignments are not prior model responses.

For each selected task, sort registered core candidates by `(gen_index, cand_id)`. Choose the first Docker-verified passing candidate and the first Docker-verified failing candidate. A candidate is eligible only when its typed record has a complete truth tuple and its saved `harness_output` matches a unique successful `data/executions.jsonl` Docker record. No candidate is generated, mutated, re-executed, or chosen by model behavior. This uses truth only to balance the sample; all truth labels stay in `data/interface_study_001/evaluation_truth.json`, separate from the model-facing manifest. If any selected task lacks a valid pair, stop with `BLOCKED_PROTOCOL_PREPARATION` before inference. No replacement after the split freezes.

## 9. Leakage safeguards

The development and held-out sets are disjoint by task ID. All tasks with prior completed world-model responses, regardless of which local WM or interface produced them, are excluded from held-out evaluation. The manifest and split are frozen **before** development inference. No held-out output may be inspected during development because none is authorized then. Every model-facing message is scanned for a literal numeric `RESULT: k/n`; a found numeric answer stops preparation. The harness's source-level `print(f"RESULT: 0/{len(TESTS)}")` is code, not an executed outcome. The study-specific templates include only the test count, not the correct count. `evaluation_truth.json` must never be loaded into a serving request. The original pilot and diagnostic caches are read-only provenance sources, never study score caches.

## 10. Prompt rendering and hashes

The canonical serializer is UTF-8 JSON with sorted keys, no extra whitespace, and non-ASCII characters preserved. Each complete message list has a SHA-256 in the ignored manifest; the manifest itself hashes its content excluding the `manifest_sha256` field. Interface B template hashes after LF normalization are: system `01f37dd7d3a0ba24aeb1a805749e821fd46401d7e395b3f0c973d6abc51d00d7`, C user `4f31a5fc4a3df7b8fabe539beba69b087fe813bd250c80d2d42200a583675fe5`, D user `7a143264acb21e6a14ec9289c6fbc46597059fe37ff383b4527c56ff4fab3f76`. Interface A's source-file hashes, current renderer/parser hashes, pilot config hash, all selected candidate code hashes, test-list hashes, and complete model/server identity are in the manifest. An execution runner, if later authorized, must compare every request's messages, parameters, model/server identity and hash to this manifest before inference. Any mismatch stops; no ad hoc rerendering is allowed. All 192 message lists are frozen as exact values under `data/interface_study_001/manifest.json`.

The substantive A/B difference is the prompt interface: A asks for a simulated terminal/tool observation, B asks directly for a count. The same stripped code, original asserts, task, candidate, channel, and inference settings are used within each pair. B explicitly supplies `n_tests`, whereas A's denominator is only recoverable from `TESTS`; this is a **deliberate interface difference** and may improve format independently of reasoning accuracy. C and D retain different action packaging by design. Input length, wording, and transcript structure also differ between A and B, so the paired comparison estimates the bundled interface effect, not the causal effect of any single sentence.

## 11. Primary and secondary measurements

For every interface/channel cell, use all 36 assigned held-out responses (18 tasks × passing/failing). **Primary feasibility metrics are assignment-level**: invalid or missing finalized predictions count as unsuccessful for exact count, binary correctness, passing sensitivity, and failing specificity. There is no imputation of `k` or reward. Report the following separately for development and held-out:

1. **Legacy validity:** call the unchanged `src/inert/parse.py:parse_result` with the task's actual `n_tests`; report accepted/assigned.
2. **Finalized-answer validity (new study metric):** call the pure `finalized_result` function in `src/inert/interface_study_001.py`. It requires `finish_reason == "stop"`; at most one complete `<think>...</think>` span and no unclosed reasoning; exactly one numeric `RESULT: k/n` outside reasoning on its own line; the correct denominator; `0 ≤ k ≤ n`; and no trailing content except whitespace or one terminal-prompt line of the form `user@host:path#` or `user@host:path$`. Numeric strings inside a complete reasoning span do not count. Any `length` finish fails even if an earlier numeric result appears. Missing result, malformed/non-standalone result, wrong denominator, out-of-range numerator, multiple numeric results, unfinished reasoning, and nonfinal trailing text receive distinct status codes. A's terminal transcript may precede the one result; B's stricter one-line contract compliance is also tabulated separately. This metric does **not** replace the legacy pilot parser.
3. **Exact count:** fraction of assigned responses whose finalized `k` equals Docker `n_passed`; also report conditional exact accuracy among finalized-valid outputs.
4. **Binary pass/fail:** `pred_pass = (k == n)`, compared to the candidate's recorded `true_pass`; report assignment-level and conditional accuracies.
5. **Balanced accuracy:** mean of passing-candidate sensitivity and failing-candidate specificity, with invalid predictions counted wrong in their true stratum. Also show conditional balanced accuracy when both strata have valid outputs, otherwise `unavailable`.
6. **Failure discrimination:** correctly identified failing candidates / 18, false-pass predictions / 18, share predicted all-pass among valid outputs and all assignments, and the always-pass baseline. “Always-pass collapse” means all finalized-valid outputs predict `k=n` or specificity is zero; report both flags, not a post-hoc threshold.
7. **Operations:** live HTTP latency, completion tokens, finish reason, length-limit share, cache hits, distinct live requests, VRAM samples and peak with provenance, server start time separately, timeouts, and missing measurements. Never substitute idle VRAM for live GPU evidence or a cache lookup for live latency.

The always-pass comparator predicts `k=n` for every assignment: on this balanced held-out sample its binary balanced accuracy is 0.50 and failing specificity is 0. Its exact-count accuracy is 18/36 (50%) because every passing candidate passes all tests and every selected failing candidate does not. This baseline is a deterministic comparator, not an inference run.

## 12. Statistical analysis

The task is the independent resampling unit. For each held-out cell, compute the point estimates above on the 18 prespecified tasks and percentile 95% intervals from **10,000 task-cluster bootstrap resamples** with `numpy.random.default_rng(0)`. Resample complete task pairs; preserve their candidate/interface/channel relationships. Use the same sampled task indices for paired A–B differences. If an estimator is undefined in a replicate, omit that replicate and report the valid-replicate count; do not fill a missing value. Do not use these descriptive intervals as hypothesis tests. No multiplicity-adjusted claim is planned. Development metrics are descriptive engineering checks only and never pooled with held-out estimates.

## 13. Feasibility thresholds and decision categories

These are **new-study proposed thresholds**, subject to owner approval; none modifies the original pilot. A held-out interface/channel cell qualifies only when it has finalized-answer validity **≥95%**, assignment-level balanced accuracy **≥0.65**, correctly identifies **≥50%** of the 18 failing candidates, assignment-level exact-count accuracy **≥50%**, and no unresolved truth or measurement-integrity failure. For 36 assignments, the validity threshold requires at least 35 finalized-valid responses. The validity requirement limits missingness; the balanced-accuracy and specificity requirements exceed the always-pass baseline; the exact-count floor requires at least 18/36 but is intentionally insufficient alone. The cutoffs are engineering go/no-go criteria, not power-calibrated hypothesis tests. Report task-cluster intervals beside each estimate without moving a cutoff based on an interval.

- `INTERFACE_READY`: at least one held-out cell meets **all** criteria. Name only the qualifying channel(s) and interface(s).
- `INTERFACE_LIMITED`: no cell is ready, but at least one has balanced accuracy ≥0.65 and failing specificity ≥0.50 with complete integrity. Name every criterion it misses.
- `INTERFACE_NOT_READY`: all planned measurements are complete and no cell meets the limited or ready definitions.
- `INCONCLUSIVE`: planned data are incomplete, a protocol violation occurred, or unresolved measurement/ground-truth integrity prevents intended assessment. This supersedes the other labels.

These categories are evaluated **only after** the held-out stage is separately authorized and completed. They never become KT-A/B/C verdicts.

## 14. Stop rules and stage gates

Before any request, stop on a model/shard/server hash mismatch, wrong server arguments or settings, altered prompt/message/manifest hash, task leakage, missing Docker truth, candidate/code/test mismatch, unexpected historical-file modification, inertness violation, or unrecoverable local server/Docker infrastructure error. During development, stop if **any of the four interface/channel cells has more than 10% finalized-answer failures** after its 12 prespecified assignments (two or more failures), or if required latency/VRAM provenance is missing. Do not change a prompt or run a replacement assignment. At the 48-assignment development boundary, verify every raw response and cache key, publish a development audit, then **stop**. Passing that engineering gate does not unlock held-out work. A second explicit owner authorization is required to run the frozen 144 held-out assignments. During held-out work, stop for integrity/infrastructure/budget reasons, but **not** for an accuracy signal from a few responses. Do not inspect held-out outcome accuracy until all 144 are complete. If a development gate fails, write a revised protocol as a new version for separate approval; this version ends.

## 15. Resource budget

Proposed maximum: **192 assignments and three cumulative GPU-hours of live HTTP inference**, excluding documented server startup, setup, and offline verification. Development permits at most 48; held-out at most 144 after separate unlock. Enforce a 10,800-second cumulative live-request budget across both phases; reserve the configured 300-second request timeout before starting the next call, so no call begins with less than 300 seconds remaining. Stop when the cap is exhausted; do not treat the incomplete study as a negative result. One WM-B server process at a time. The prior engineering run's 194 distinct WM-B requests used 545.22 aggregate HTTP seconds, with median 2.45 s and P90 6.23 s (`data/smoke/diagnostics/wm_b_engineering_smoke_20261114/scores/wm_b.jsonl`). At that empirical P90, 192 requests would take about 0.33 HTTP hours; the B prompt and selected tasks may differ materially, so the three-hour cap is a conservative allocation, **not a runtime promise**. Record startup and concurrent memory-monitoring overhead separately. No inference is authorized by this document.

## 16. Paired analysis and reporting plan

On identical held-out task/candidate/channel assignments, report B minus A for finalized validity, assignment-level exact-count accuracy, assignment-level balanced accuracy, failing-case specificity, and HTTP latency. Use the task-cluster bootstrap above. The latency endpoint is the median of paired, completed HTTP duration differences; report omitted pairs and timeouts separately, without imputation. Report absolute cell competence before interpreting improvement: B can improve yet remain unusable, or A can qualify without B improving. Report per-task and aggregate confusion tables, numerator/denominator distributions, invalid-reason counts, finish reasons, representative raw failures with IDs, and all exclusions. Do not select a favorable endpoint after seeing results. A future report must label development and held-out data separately and state the exact decision category, or `INCONCLUSIVE` with the violated requirement.

## 17. Threats to validity

The prior three-task sample may not predict 18-task performance. The held-out sample is balanced by executed truth rather than natural candidate prevalence, so prevalence-based accuracy will not generalize directly. Candidates within a task share assertions and code family; task-cluster resampling addresses that dependence but 18 tasks still yield wide intervals. B bundles instruction, count hint, and framing, so a paired difference cannot isolate which component mattered. Interface A was designed to produce a terminal/tool observation rather than a one-line answer; the finalized metric permits its terminal transcript but may still favor B's explicit final-answer contract. Native model reasoning may ignore B's no-reasoning request. The source tasks and candidates were generated before this study, and all tasks were seen by a different proposer; held-out means unexposed to **world-model outcome prediction**, not globally unseen to every model. Public MBPP tasks may have appeared in pretraining, which cannot be audited here. Quantization and local hardware limit transfer. No raw model output is available at protocol lock, so no new-study result is claimed.

## 18. Future amendments

After owner approval, changes to the task split, exposure definition, candidate choices, model/server/settings, template bytes, outcome definitions, thresholds, stopping rules, or analysis plan require a **numbered amendment** with timestamp, reason, prior responses already observed, new hashes, and separate owner approval before additional inference. If development fails, preserve its records and issue version 2.0.0 (or another explicitly numbered version); do not overwrite this lock. Held-out tasks must never be reselected after viewing study responses. A protocol amendment cannot retroactively turn this study into the frozen pilot.

## 19. Reproducibility and preservation

Run `.venv\Scripts\python.exe -m inert.interface_study_001` offline from this commit to verify source files, scan exposure, select tasks/candidates, render all 192 messages, verify Interface A identity and leakage, and create or compare the ignored `data/interface_study_001/` artifacts. It is a preparation tool only; it contains no inference loop, HTTP call, server startup, Docker run, or candidate execution. It refuses to overwrite an existing study artifact with different bytes. The manifest contains exact messages, model/server identity, source/prompt hashes, task split hash, protocol hash and ordered assignment IDs; truth is a separate file. Confirm source hashes, Git commit, cache integrity, and historical baselines again before any later authorized stage. No original pilot manifest, cache, prompt, parser, condition, threshold, seed, or decision rule is changed.

## 20. Owner approval

**Pending.** The owner must explicitly decide whether to (1) accept world-model-response exposure as the held-out exclusion rule while treating proposer-only exposure separately, (2) approve the one new B template and the finalized-answer metric, (3) approve the new feasibility cutoffs and three-hour/192-assignment ceiling, and (4) authorize **development only** under the frozen manifest. Held-out evaluation requires a second explicit authorization after reviewing the 48-assignment development audit. A commit or this document alone grants neither permission.
