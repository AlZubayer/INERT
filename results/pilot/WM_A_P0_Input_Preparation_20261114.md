# WM-A P0 input preparation: P0_INPUTS_PREPARED

**Final status (2026-11-14, Asia/Dhaka): `P0_INPUTS_PREPARED`.** The owner
accepted the second historical-cache preservation exception prospectively and
authorized completion of the pilot input stages. The original failed baseline
remains failed and is retained below. No WM-A inference, P0, WM-B/WM-C pilot
scoring, or kill-test scoring was performed. The original WM-C smoke gate
remains closed.

## Approved recovery and completed preparation

The pre-existing `data/cache/sandbox.sqlite` had an original expected SHA-256
of `956bbf780edafcc5d31b05461de14403113d92d8ea000703c9f6ea2e6aee7149`
and changed to
`5febe62370e779409019f7bef98d4afc63f37f21848dfb59101390f8a15650d2`
during the earlier official task filter. Under owner approval
`HISTORICAL_PRESERVATION_EXCEPTION_ACCEPTED_2`, only this file received a
separate prospective baseline. Its 492 execution rows pass SQLite integrity
checking, and all 13 archived import-dependent reference checks remain
present with matching inputs and outputs. The exact changed byte copy,
consistent SQLite backup, original inventory, and prospective inventory are
under `data/p0/preparation_audit_20261114/`. All 8,852 protected historical
files matched the prospective inventory before validation and after each
remaining preparation stage. The original expected hash was not reconstructed
or silently replaced.

The remaining stages used the explicit sandbox-cache override
`data/p0/preparation_audit_20261114/sandbox_cache/sandbox.sqlite`. Tests
covered `execute`, `core-set`, `build-items`, and task filtering; the actual
preparation confirmed the original sandbox cache remained at its prospective
hash. The isolated cache has 2,290 execution rows and passes SQLite
`integrity_check`. Its cache-key identity, Docker harness, network isolation,
and resource limits were unchanged.

The 50 sampled tasks and 10 original reserves matched the pinned sanitized
MBPP revision `4bb6404fdc6cacfda99d4ac4205087b89d32030c`, configured file
hashes, and seed `20261111`. All 60 selected task records matched their local
source rows and passing Docker reference evidence. Core-set construction
activated nine reserves in their registered order, including one replacement
of a prior reserve; **50 tasks are now core ready and one reserve remains**.
The exact drop chain is in `data/task_drops.json` and the final ignored audit
at `data/p0/preparation_audit_20261114/final_input_audit.json`.

Proposer generation completed **944 attempts**: 573 accepted, 369 duplicate,
and two syntax errors. `data/candidates.jsonl` contains 612 candidate records
including reference solutions and accepted mutants; 549 belong to the current
50 tasks. Docker produced 637 execution records: 636 `ok` and one
`unusable_harness_output`. The final core set contains **182 candidates**,
with at least one passing and one failing candidate for each task. There are
182 thought records, 139 nonempty. Item rendering produced **5,316 items**:
3,678 Channel C and 1,638 Channel D; 3,276 KT-A/KT-B and 1,020 in each KT-C
rung. All 3,678 recorded Channel-C inertness checks passed, and the final
item IDs are unique. These are input-construction counts, not model scores.

The first 12 ready tasks supplied **100 frozen P0 assignments**, with 50
items per channel, eight items per task plus one extra for each of the first
four tasks, and all nine registered conditions represented. The manifest
contains exact item IDs, model-facing messages and hashes, source-file hashes,
and the WM-A Q4 identity; ground-truth pass counts remain in separate
candidate records. The manifest SHA-256 is
`81431897467fe7a62821c44967c888bfd1b9bec9ae8520538470fe35051827e0`.
The local WM-A Q4 GGUF matched its pinned SHA-256
`98de3cd55f5bd89a15708e084ccbb838ff00dec6c35e9daa15eb3f3fad596bdd`.
No `results/pilot/p0.json`, WM-A response cache, or pilot score file was
created by this preparation.

P0 timing code now uses each live HTTP request-to-completed-response interval
for the frozen 20/50-second feasibility bands. Server startup is measured
separately. Persisted per-request latency, token count, and live GPU peak are
bound to the model, server, settings, and manifest identity. Mixed cached/live
or interrupted trials may reuse only matching live evidence; missing,
conflicting, or incomplete provenance stops without a decision. Tests use
mocks and temporary files only. **No WM-A timing or VRAM measurement has run.**

The first `build-items` process stopped after 948 PASS check records because
Windows denied one atomic replacement of `data/inertness.jsonl`. The stage
log identifies a file-write `PermissionError`, not an inertness failure. The
registered stage was retried once using its passed-check checkpoint and
completed all 5,316 items without changing scientific logic or parser rules.

Final validation passed: **265 tests**, Ruff lint, Ruff format (`67 files
already formatted`), and `git diff --check`. The final protected-inventory
check matched all 8,852 files under the prospective baseline. Frozen config,
text templates, parser code, and condition definitions had no Git diff.

The next action is a separately authorized P0 run only after the existing
WM-C smoke gate is resolved. This preparation does not imply P0 feasibility
or validity of any WM-channel cell.

## Prior blocked checkpoint (historical evidence)

**Branch and starting commit:** `pilot/steps-0-1` at `eab98bdd55b89402d4ffb5c2bdbf852c42ea817b`. **Audit date:** 2026-11-14 (Asia/Dhaka). The owner authorized official pilot input preparation and two P0 implementation clarifications. The official task stage completed, but preparation stopped before proposer inference because a pre-existing historical SQLite cache changed. This is a new preservation incident; the earlier smoke diagnostic exception does not authorize it. P0, WM-A inference, pilot scoring, and all kill tests remain unstarted. The original WM-C smoke gate remains closed.

## Task preparation

The configured `google-research-datasets/mbpp` `sanitized` data at pinned revision `4bb6404fdc6cacfda99d4ac4205087b89d32030c` was used with seed `20261111`. The stage checked 427 source rows; 425 met the registered filters and Docker reference check, and two were excluded for external-state use. It wrote the registered **50 sampled tasks** to `data/tasks.jsonl` and **10 reserves** to `data/reserves.jsonl`; there were no replacements or core-set drops yet. The sampled and reserve IDs reproduce the frozen `random.Random(20261111)` selection from eligible rows, with no overlap. The first 12 sampled IDs are `mbpp-440`, `mbpp-265`, `mbpp-310`, `mbpp-133`, `mbpp-447`, `mbpp-291`, `mbpp-794`, `mbpp-633`, `mbpp-593`, `mbpp-103`, `mbpp-162`, and `mbpp-766`. They are **sampled, not yet ready** under section 6.3.

The local dataset parquet hashes matched `configs/models.yaml`; task records passed schema validation and had non-empty reference code and tests. Exact IDs, per-task source hashes, dataset hashes, and file hashes are in `data/p0/preparation_audit_20261114/task_audit.json`. The task file SHA-256 is `bfd4492ad3832f85d03237908a062824a3a82925e208caa9dd3229bc539a9719`; the reserve file SHA-256 is `c445997f7150e3fa2131cdfcae3fe15dc75e026b3d44941bd27f494b6c6ca63d`. The independent audit did not reparse every original MBPP row against each written reference program; that deeper source comparison remains for resumed preparation.

## Candidate generation and Docker truth

The code proposer stage was **not started**. Planned official generation is 50 tasks × 16 attempts = 800 attempts; completed attempts, valid generated candidates, syntax failures, duplicates, and proposer cache hits are all **0**. There is no official `data/candidates.jsonl` or `data/generation_attempts.jsonl`.

The task filter used the registered network-disabled Docker sandbox to check reference solutions. Candidate execution, ground-truth pass counts, sandbox-error accounting for candidates, core-set construction, thought generation, item rendering, and static/dynamic inertness checks were **not started**. There are **0 official candidate execution records**, **0 core-set candidates**, **0 thoughts**, and **0 rendered pilot items**. No candidate code ran on the host.

## P0 selection

The owner-approved algorithm is implemented in `src/inert/p0_selection.py`: take the first 12 ready tasks in the frozen pilot order; sort each task's core candidates by `(gen_index, cand_id)`; take eight slots per task plus a ninth for the first four; assign channels, candidates, and conditions by the approved index formulas. It enforces 100 unique existing `kt_ab` item IDs, 50 items per channel, and coverage of all nine conditions. The `prepare-p0` CLI command creates an ignored manifest with source hashes, task/item IDs, exact model-facing messages and hashes, model identity, inference settings, and a canonical manifest SHA-256. P0 execution requires that frozen manifest to match the current source files byte for byte. The code changes do not change KT-A/B/C populations or endpoints.

Because no task has completed core-set preparation, the current P0 selection is **0/12 ready tasks** and **0/100 items**. `data/p0/selection_manifest.json` does not exist; its SHA-256 and condition distribution are **unavailable**. No `results/pilot/p0.json` exists.

## Measurement safety

The P0 implementation now keys VRAM evidence to the model SHA-256, quantization, GPU layers, context, server binary and arguments, inference settings, and frozen P0 manifest hash. A completed live trial writes an atomic, hashed measurement record with source `nvidia-smi`, peak MiB, sample count, and completed live-request count. A cache-only replay can reuse only a complete matching live record. Missing, corrupted, mismatched, or incomplete evidence stops before a P0 decision; idle GPU samples alone are never accepted. The registered feasibility bands, 1,024-to-2,048 truncation rule, parser, and parse-failure stop remain unchanged. These behaviors passed mock and temporary-file regression tests; **no live WM-A measurement exists**. A mixed cached/live replay currently records the peak of its live portion; whether that suffices for the intended full-trial peak remains to be reviewed before P0. The design's phrase “time them end to end” still needs the owner's answer on whether initial server startup belongs in the decision latency.

## Historical preservation incident

The pre-stage SHA-256 inventory at `data/p0/preparation_audit_20261114/historical_inventory_before.json` includes 9,009 files, of which 8,852 are immutable historical files and 157 are pytest temporary-workspace files. Before the task stage, the 8,852 historical files all matched. After `inert tasks`, **one historical file changed**: `data/cache/sandbox.sqlite` went from SHA-256 `956bbf780edafcc5d31b05461de14403113d92d8ea000703c9f6ea2e6aee7149` to `5febe62370e779409019f7bef98d4afc63f37f21848dfb59101390f8a15650d2`. The other 8,851 matched. Changes under `data/pytest-tmp/` are listed separately as temporary validation files; the original inventory was not rebaselined.

The task stage wrote through the configured pilot sandbox cache during Docker reference checks. The changed database passes `PRAGMA integrity_check` and contains 492 execution records. An exact current byte copy, a SQLite-consistent backup, and incident metadata are stored under `data/p0/preparation_audit_20261114/preservation_incident/`. No copy matching the original hash was found, so the original bytes cannot presently be restored. The 50-task sample, 10 reserves, filter evidence, and all prior smoke and diagnostic evidence remain in place. This incident is recorded in `results/pilot/deviations.md` and is **not** covered by the earlier accepted cache exception.

## Validation and remaining barriers

The final full suite passed **259 tests** in 64.14 seconds; P0 selection and measurement tests passed with mocks and temporary paths. Ruff lint and format checks passed (`67 files already formatted`), and `git diff --check` passed. The post-test inventory still shows the same single immutable-file discrepancy, `data/cache/sandbox.sqlite`, and no additional historical change. The publication gate remains failed because historical preservation failed. No proposer, WM-A, WM-B, or WM-C server was started in this preparation. The absence of pilot proposer and WM-A cache files and of `data/server.lock` was checked after the stop. The official WM-C smoke gate remains closed.

**Status at this earlier checkpoint: `BLOCKED`.** The project was **not ready** for a separately authorized P0 run. The next owner decision at that time was whether to accept this new cache-preservation exception prospectively, retaining the original failed hash record, and authorize an isolated cache path for all remaining pilot Docker preparation. That approval and the completed recovery are documented above. No data under `data/` is proposed for Git.
