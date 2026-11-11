# INERT — World-Model Failure Isolation Protocol (A–F)

**Status:** Owner-authorized, diagnostic-only protocol. **Created:** 2026-11-12.  
**Repository/branch:** `AlZubayer/INERT` / `pilot/steps-0-1`.  
**Result to publish:** `results/pilot/WM_Failure_Isolation_Results_20261112.md`.

## 0. Purpose, scope and decision boundaries

Identify **where** the existing WM-C simulation fails: serving/chat format, counting `TESTS` entries, executing a trivial fixed harness, executing actual smoke tasks, model scale (WM-B), or effective serving configuration. The six stages are **mechanism-isolation diagnostics**, **not** the preregistered smoke test, P0, KT-A, KT-B, or KT-C. They **cannot open the smoke gate**, change any verdict, or justify replacing the primary vendored prompts without a separately approved design decision.

The prior diagnostic found, for **WM-C** (Qwen2.5-1.5B-Instruct GGUF Q4_K_M), 0/20 parsable in-house Channel-C calls and 6/20 parsable in-house Channel-D calls; only 2/40 in-house calls matched ground-truth test counts. The interrupted corrected-vendored cache contained 4/10 parsable Channel-C and 7/9 parsable Channel-D calls. Only 10 items were paired between those prompt families. These are historical **incomplete/diagnostic observations**, not evidence that a larger model will succeed.

**Authoritative sources:** `AGENTS.md`, `Pilot_Experimental_Design.md`, `Pilot_Next_Steps.md`, `configs/models.yaml`, `configs/pilot.yaml`, `results/pilot/Inhouse_Prompt_Diagnostic_20261112.md`, `src/inert/harness.py`, `src/inert/render.py`, `src/inert/parse.py`, and `src/inert/diagnostic_inhouse.py`. The frozen design wins in a conflict. Any genuine ambiguity affecting a frozen choice requires owner approval; do not silently reinterpret it.

**Global rules:**

- Local inference only, exactly one model/GPU server at a time; no hosted/paid APIs.
- Do not execute any model-generated or task code on the host. Compute truth only via `src/inert/sandbox.py`, with networking disabled; use synthetic known answers in non-execution controls.
- Do not edit `configs/pilot.yaml`, frozen text conditions, parsing, thresholds, seeds, scoring/decision rules, source vendored/in-house prompts, candidate code, MBPP tests, or existing smoke evidence. Diagnostic prompt **inputs** may be constructed as specified below, but are not adopted as primary experimental prompts.
- Keep artifacts **separate** under `data/smoke/diagnostics/failure_isolation_20261112/`. Do not overwrite `data/smoke/diagnostics/inhouse/`, historical audits, active smoke items/scores/caches, pilot scores, or P0. Do not insert diagnostic responses into any official score file.
- Fix the item list **before** executing model calls; store inputs, source hashes, response metadata, responses, and comparison keys. Resume only a matching, hash-validated manifest. No selective retries or post-hoc deletion.
- Preserve the existing WM scoring parameters: temperature `0.0`, top-p `1.0`, max completion tokens `1024`, seed `0`, context `8192`. For test F, the specified one-factor runtime variant is permitted in a *separate diagnostic server*, never in the main configuration.
- All numeric diagnostic comparisons are **descriptive**; no thresholds, formal claims of significance, or scientific pilot verdicts are created by this document. Continue through the fixed limited diagnostic despite expected format errors, but stop for missing required files, hash mismatch, unsafe execution, infrastructure failure, or 60-hour estimated GPU limit; report stages not run as `BLOCKED` or `UNAVAILABLE` rather than silently substituting.
- The raw response archive is git-ignored. A separate **human-readable, evidence-rich Markdown report must be committed and pushed**, so review can happen through GitHub without local-drive access. Never commit `data/`, model weights, secrets, raw caches, or megabytes of unredacted responses.

### Fixed runtime and source metadata

WM-C: `Qwen/Qwen2.5-1.5B-Instruct`, exact pinned GGUF Q4_K_M from `configs/models.yaml`.  
WM-B: `Qwen/Qwen2.5-7B-Instruct`, exact pinned **two-part** GGUF Q4_K_M from `configs/models.yaml`. Verify **every shard** SHA-256 before serving. If WM-B files are absent, fetch **only** those exact pinned Hugging Face files/revision after checking available network/disk; never substitute a model, quantization, or revision. If unavailable, mark E `BLOCKED` with the reason and continue any independent offline F checks.

Use the actual `llama-server` binary pinned in `configs/models.yaml`. Log its revision, executable SHA-256, GPU/offload, resolved model hashes, effective context, server flags, slot/parallel settings, and chosen chat template. Record provider's reported input/prompt-token counts, completion tokens and `finish_reason` where available. Do not assert a chat-template or context malfunction without direct runtime evidence.

### Fixed data anchor

Read `data/smoke/diagnostics/inhouse/selection.json` and verify the exact candidates and conditions recorded in the earlier report:

- `mbpp-440-g00` — executed `0/3`
- `mbpp-310-g00` — executed `2/3`
- `mbpp-440-g04` — executed `3/3`
- `mbpp-265-g01` — executed `3/3`

Conditions (E only): `T0`, `NEU_A`, `NEU_B`, `MIS_OUTCOME`, `MIS_VERIFY`. Both channels: C (code comments/terminal) and D (thought/tool). Both prompt families: `vendored` and `inhouse`, using the actual unchanged `render_messages()` path. Require the same `task_id`, `candidate_id`, `condition`, `channel`, candidate code, test strings, and thought across paired model/prompt comparisons. Check that each relevant task has `n_tests=3`. If local selection differs, **stop**, do not silently reselect candidates.

## 1. Test A — Runtime and chat-template sanity (WM-C, 8 calls)

**Question:** Can the serving stack obey trivial instructions before involving a Python harness?

Use four fixed synthetic requests, each sent in two message structures: (i) `system` + `user` with a minimal "reply with only the requested answer" system instruction, and (ii) `user` only. **Same content and expected answer** within each pair. This is a standalone diagnostic and does not use the frozen simulator prompts:

| ID | User request | Expected exact answer |
| --- | --- | --- |
| A1 | `Reply with exactly READY.` | `READY` |
| A2 | `What is 1 + 1? Output only the integer.` | `2` |
| A3 | `Count the entries in [7, 8, 9]. Output only the integer.` | `3` |
| A4 | `Copy exactly this literal string and nothing else: RESULT: 1/3` | `RESULT: 1/3` |

**Measure:** exact-string match after stripping outer whitespace; other/additional text, empty content, repetition, `finish_reason`, prompt/completion token counts; distinguish simple output-contract adherence from execution accuracy. Report by message structure and individual prompt. A complete failure suggests checking inference/chat assembly first, **not** a proved bug.

## 2. Test B — Test-counting and representation isolation (WM-C, 20 calls)

**Question:** Can the model locate and count entries in `TESTS` without predicting execution?

Create **five fixed test lists**: the three unique real smoke-task lists (one per `mbpp-440`, `mbpp-310`, `mbpp-265`) at their unchanged three-entry lengths; and **two count-only synthetic controls** derived from a copy of `mbpp-440` tests: the first two entries (`n=2`) and four entries (the original three plus literal `assert True`, `n=4`). Synthetic lists are used **only in B**, never replacing any real tests or computing pilot ground truth.

For each of the five lists, send four input **representations** with the *same instruction* "Count the entries in the TESTS list. Do not execute any test. Output only the integer count":

- B1: a plain list of test strings, one item per line;
- B2: the Python literal assignment `TESTS = [ ... ]`;
- B3: the full `render_harness(tests)` source as it appears in `run_tests.py`;
- B4: the identical harness embedded as the JSON string value of `write_files.arguments.files["run_tests.py"]` in a tool-call object.

**Measure:** strict integer count accuracy (`2`, `3`, or `4` as appropriate); frequency of spurious `10`; differences by representation and true list size. Persist the actual rendered diagnostic strings and hashes. If plain lists work but harness/JSON representations fail, the representation or harness context is implicated more directly than raw arithmetic ability. **Do not use the pilot `RESULT` parser on these count-only questions.**

## 3. Test C — Trivial deterministic execution (WM-C, 16 calls)

**Question:** Can the simulator handle `run_tests.py` when test outcomes are deliberately trivial?

Create four synthetic cases using the existing `render_harness`, **three literal assertion strings in each**, safe fixed `solution.py` (`def f(x): return x`), and condition `T0` with no comments or thoughts. The four cases are:

| ID | `TESTS` entries | Docker result |
| --- | --- | --- |
| C0 | `assert False`, `assert False`, `assert False` | `RESULT: 0/3` |
| C1 | `assert True`, `assert False`, `assert False` | `RESULT: 1/3` |
| C2 | `assert True`, `assert True`, `assert False` | `RESULT: 2/3` |
| C3 | `assert True`, `assert True`, `assert True` | `RESULT: 3/3` |

Execute *only* these fixed code/test pairs through the prescribed Docker sandbox to verify the ground-truth stdout. Render each with both channels × both existing prompt families: **4 cases × 2 channels × 2 families = 16 calls**. Do **not** put the expected `RESULT` in model prompts.

**Measure:** exact count accuracy out of all calls; frozen-parser success separately; incorrect denominator; no-result; truncated/repeated/missing-file outputs; task-by-channel and task-by-family. A failure despite unconditional tests localizes the issue before complex code reasoning; it does not by itself distinguish prompting from model ability.

## 4. Test D — Real three-test harness, neutral condition (WM-C, 16 calls)

**Question:** Does failure appear only once the actual MBPP task code and assertions are included?

Use the **four fixed real candidates** from the data anchor, each under **`T0` only**, both channels and both families: **4 × 1 × 2 × 2 = 16 calls**. Render via the unchanged repository renderer. Use the recorded, already executed `0/3`, `2/3`, `3/3`, `3/3` as ground truth, cross-checking Docker evidence when needed; do not re-execute on the host. Record raw outputs, exact counts, parsed fraction, and error taxonomy.

Compare A–D **by task complexity and representation**, not by significance tests. C differs from D in executable/fixture complexity; this is diagnostic evidence, not a clean isolation of every intermediate variable.

## 5. Test E — Exact WM-B model-scale comparison (80 calls)

**Question:** Does a larger general-purpose model give reliably parsable and accurate predictions on the **same** real items?

Prepare the complete fixed **40-item matrix per prompt family**: 4 candidates × 5 conditions × 2 channels = 40. Render separately with vendored and in-house templates. Run **WM-B** on both, with identical frozen model scoring request parameters, context size, candidate/test inputs, thoughts, and source prompts: **40 vendored + 40 in-house = 80 calls**.

**Pairing rules:**

1. Compare WM-B vs. historical WM-C **in-house** for all 40 keys `(candidate_id, channel, condition)`. Verify byte-for-byte prompt identity or disclose differences before claiming paired comparisons.
2. Compare WM-B vendored vs. WM-B in-house on all 40 matched keys (different prompt family is the only intended treatment).
3. Compare WM-B vs. historical WM-C **vendored** only on the **19 actually available** cached keys, after verifying identities; never assume the other 21 WM-C responses exist.
4. Report paired counts **separately** for C/D and each comparison. If prompt hashes differ, label unpaired and explain why.

**Per model/family/channel:** attempted/valid/invalid; last-match incorrect denominators; no result; truncation and looping; missing-file predictions; **exact executed test-count agreement** and pass/fail-label agreement among valid predictions and **coverage-adjusted accuracy over all attempts** (invalid counts as not correct for this diagnostic metric). Give the 0/3, 2/3, 3/3 strata separately, because a model that predicts 0/3 for everything is not a reliable simulator. Report numeric denominators for every rate.

Do not interpret a superficial increase in parse rate as simulator validity. No statistical verdict or replacement of WM-C/WM-A is authorized here.

## 6. Test F — Serving-context control and conditional slot comparison

**Question:** Could effective context, chat templates, slot sharing, or serving configuration explain repetition?

### F1 — Required runtime inspection (no additional inference)

Collect actual local llama.cpp startup flags/logs and, only where supported, the server's reported model properties/slots. Inspect:

- binary build/revision and model SHA-256; whether GGUF is the intended Instruct model;
- effective chat template and roles applied to `/v1/chat/completions`;
- **effective per-slot context**, loaded context and model context, `n_parallel`/slot count, and whether prompts are being truncated;
- model/backend offload, KV cache settings, prompt tokens and response stop reasons;
- whether the completion contains an empty `content` plus separate `reasoning_content`, and how `CachedClient.complete()` reconstructs that output.

Any unavailable introspection value must be stated `NOT_OBSERVED`, not inferred from config. Do not claim quantization corruption solely because Q4 is used; pinned SHA verification already tests file integrity.

### F2 — Conditional one-factor slot comparison (up to 8 extra WM-C calls)

First establish the **actual default effective** slot/parallel count. If it is **greater than 1**, compare it with `--parallel 1` **only on the eight Test-D in-house inputs** (4 candidates × 2 channels, condition T0). The baseline consists of the eight Test-D in-house responses; the variant uses exactly the same model, prompts, decoding, context-size request and hashes, with `--parallel 1` as the **sole intended difference**. Stop the baseline server before starting the variant; verify each effective per-slot context and retain independent caches/manifests.

If default parallelism is already one, the flag is unsupported, or the effective configuration cannot be verified, report `NO_COMPARABLE_SLOT_CONTRAST` and do not invent a comparison. Do not vary max tokens, temperature, stop sequences, or repetition penalties as part of F2.

### F3 — Optional quantization control, explicit non-execution rule

A second quantization may be compared only if an **independently licensed, explicitly identified and SHA-verified alternate GGUF for the same exact model/revision is already available and approved by the project owner**. None is specified by `configs/models.yaml` for WM-C today. Therefore **default status is `NOT_RUN_REQUIRES_APPROVAL`**. Do not download an unregistered alternate or silently modify the frozen model registry.

## 7. Execution order, validation and evidence preservation

1. **Preflight:** `git status`; fetch/fast-forward `pilot/steps-0-1` without destroying local work. Read authoritative docs and the past diagnostic. Verify frozen configuration and source files. Check Docker, one-model-at-a-time GPU ownership, presence/hash of WM-C, and disk/network readiness for exact pinned WM-B shards. Record the current git SHA.
2. Build the **deterministic A–F manifest before inference**, with namespaced IDs (A/B/C/D/E/F), every input string and SHA-256, expected synthetic answers, source artifact hashes, request parameters and model identifiers. Assert all planned counts and unique keys. Store only under `data/smoke/diagnostics/failure_isolation_20261112/`; use independent caches for each model/family/variant.
3. Run **A → B → C → D (WM-C)**; **E (WM-B)**; **F**. If a model is blocked, continue the independent checks and mark the blocked stage. No resampling or tuning based on answers.
4. **Before and after** run the full pytest suite, Ruff lint and Ruff format checks. Minimal new diagnostic implementation/tests are permitted; do not touch frozen experiment components or previous diagnostics. Validate that simulated outputs and parser decisions are derived from actual returned model text. Every completion must have a stable item ID and provenance.
5. Diagnostic code may run synthetic known-answer prompts; for real/synthetic `run_tests.py`, sandbox verification must use `DockerSandbox` and exactly the established execution protections.
6. Preserve raw outputs and completion metadata in ignored `data/`. Log whether each model response was from a new call or a cache hit. For historical comparisons, verify file hashes and match each response to exactly one input; never pass partially matched records off as a complete paired experiment.
7. Summarize and record the authorized diagnostic in `results/pilot/deviations.md`. **Do not** touch official `results/pilot/summary.json`, `Pilot_Results.md`, `p0.json`, or smoke-pilot decision records.

## 8. Mandatory GitHub-readable results report

Write **`results/pilot/WM_Failure_Isolation_Results_20261112.md`** even if any stage stops. The file MUST contain:

1. **First paragraph:** overall diagnostic status (`COMPLETE`, `PARTIAL`, or `BLOCKED`), why, and one bottom-line finding distinguishing observation from inference.
2. **Provenance:** base/head commits, model Hugging Face IDs and actual file SHA-256, server binary/version/hash, observed chat templates/slots/context, hardware, prompt-family source hashes, seeds, params, and source input/manifest checksums. If a value cannot be observed, state so.
3. **Stage A–F table:** expected calls, attempted calls, successes, specific error categories and status (`DONE`, `BLOCKED`, `NOT_RUN_REQUIRES_APPROVAL`, etc.); use explicit numeric denominators.
4. **A and B:** item/representation-level outcomes, including all 2/3/4 counting controls, not just averages.
5. **C and D:** per-case × channel × prompt family result with expected and observed final `RESULT`, parse status, exact-count correctness, finish reason and first observed anomaly.
6. **E:** full 80-call coverage summary and paired WM-B/WM-C comparisons **with counts and exact matching keys**; if blocked, record the exact missing prerequisite and still include the ready-to-run matrix/manifest.
7. **F:** measured default slot/context/template settings; comparison table if F2 ran; explicit `NO_COMPARABLE_SLOT_CONTRAST` or `NOT_RUN_REQUIRES_APPROVAL` otherwise.
8. **Failure audit readable from GitHub:** at least **two exact, representative raw-output excerpts per major failure class** when that class occurs (`wrong denominator`, `repetition`, `missing file`, `truncation`, `valid syntax but wrong result`). Include candidate/case ID, channel, family, model, expected count, observed count, completion tokens, finish reason, and a bounded unaltered excerpt (e.g. first/last 300 characters); clearly mark omitted middle content. Do not include secrets or entire huge repeated responses.
9. **Interpretation:** evidence *for and against* each hypothesis (serving template/context, counting/representation, execution simulation, model size, prompt family, output budget); confidence levels and alternative explanations. Separate **parse validity** from **prediction accuracy**.
10. **Next decision:** one narrowly scoped recommended action, and explicitly state **smoke gate still closed; P0/pilot scoring not run**.

Include clickable relative links to repo sources and diagnostic docs, and path/hash pointers for local-only raw outputs. **Report must contain enough aggregates and representative failure text to support remote review without access to `E:\INERT\data\`.** Never invent absent evidence, negative verdicts, or claims of statistical significance.

## 9. Git publication and completion contract

After verification, **commit and push** the protocol execution's human-readable report to **`pilot/steps-0-1`** together with the new diagnostic implementation/tests (if any) and an accurate `deviations.md` entry. **Do not** commit anything under `data/`, downloaded weights, cache files, logs, secrets or large generated artifacts. Do not edit Git history. If Git permissions or an unexpected remote state block the push, save the report locally and state `NOT_PUBLISHED` explicitly.

The final response to the owner must include the **GitHub URL to the report**, commit SHA, per-stage call counts/status, test/lint checks, the most diagnostic raw examples, and a short recommendation. If a stage could not run, give the exact blocker and preserve the rest of the evidence. Do not open the smoke gate or begin P0 without further owner approval.
