# Assertion-reading and execution-reasoning diagnostic — 2026-11-12

## Executive finding

**BLOCKED_SELECTION.** The fixed eight-candidate matrix could not be formed from the existing local MBPP pool. The protocol requires two previously untested candidates in each of the 0/3, 1/3, 2/3, and 3/3 Docker pass-count strata. The entire 29-candidate pool has **zero 1/3 candidates**, even before earlier model exposures are excluded. The fresh pool therefore cannot supply the required two 1/3 candidates. No candidate was selected, no per-assertion oracle was run, and **0/48 model calls** were made. No extraction, individual-outcome, or aggregate-prediction accuracy can be reported. The original smoke gate remains closed.

## Repository and selection provenance

The clean `pilot/steps-0-1` branch was fetched and fast-forward checked at starting commit `c1a26304302eb1c8045d0cfe7fb3c421ce7d163e`. This is a diagnostic-only selection audit. The reproducible audit is stored at `data/smoke/diagnostics/assertion_execution_20261112/selection_audit.json` (git-ignored), SHA-256 `6def12845d6b69f9179efd649d34d0ac79ac2934df50cd26ed3219f6c4ad2845`. It contains the source file hashes, every candidate ID and code hash, original recorded Docker count, source task, exposure evidence, scanned archive paths, and shortage calculation. No prior score, cache, manifest, or report was modified.

The deterministic rule was to sort candidate IDs ascending **within each Docker-truth stratum** after excluding any candidate found in prior scored items, diagnostic responses, or model-response caches. Selection was all-or-nothing: eight unique IDs and eight distinct code hashes, two per stratum, were required before freezing an input matrix. Since one stratum was empty in the complete source pool, the audit records `selected_candidate_ids: []` and no 48-input manifest exists. Candidate difficulty or anticipated model behavior played no role.

The source pool was the existing `data/smoke/candidates.jsonl` for three tasks (`mbpp-265`, `mbpp-310`, and `mbpp-440`). All 29 records had three original tests, a recorded aggregate `n_passed`, and a matching `RESULT: k/3` harness output. Candidate IDs and stripped-code hashes were unique. This audit read existing recorded Docker evidence; it did not execute candidate code on the host or generate new candidates.

## Complete local-pool inventory and exclusions

| Docker result | All pool IDs | All | Previously inferred IDs | Known fresh | Required | Shortage |
| --- | --- | ---: | --- | ---: | ---: | ---: |
| 0/3 | `mbpp-265-g00`, `mbpp-265-g03`, `mbpp-310-g15`, `mbpp-440-g00`, `mbpp-440-g01`, `mbpp-440-g02`, `mbpp-440-g03`, `mbpp-440-g05`, `mbpp-440-g07`, `mbpp-440-g08`, `mbpp-440-g10`, `mbpp-440-g11`, `mbpp-440-g12` | 13 | `mbpp-440-g00`, `mbpp-440-g01` | 11 | 2 | 0 |
| 1/3 | **none** | **0** | none | **0** | **2** | **2** |
| 2/3 | `mbpp-310-g00`, `mbpp-310-g01`, `mbpp-310-g02`, `mbpp-310-g04`, `mbpp-310-g06`, `mbpp-310-g12`, `mbpp-310-g13` | 7 | `mbpp-310-g00` | 6 | 2 | 0 |
| 3/3 | `mbpp-265-g01`, `mbpp-265-g02`, `mbpp-265-g08`, `mbpp-310-reference`, `mbpp-440-g04`, `mbpp-440-g06`, `mbpp-440-g09`, `mbpp-440-g14`, `mbpp-440-g15` | 9 | `mbpp-265-g01`, `mbpp-440-g04` | 7 | 2 | 0 |
| **Total** | 29 unique candidate IDs and code hashes | **29** | **5** | **24** | **8** | **2 in 1/3** |

The audit inspected three existing items files (including historical smoke item archives), four diagnostic input manifests, **four score files** (active, in-house diagnostic, and two historical smoke archives), and 17 model-response SQLite caches. It cross-referenced score item IDs and response case IDs to source items, then matched cached request messages to their exact prompt hashes or embedded source code. The five observed candidate IDs were `mbpp-265-g01`, `mbpp-310-g00`, `mbpp-440-g00`, `mbpp-440-g01`, and `mbpp-440-g04`. The first, second, third, and fifth had been repeatedly studied in prior diagnostics; `mbpp-440-g01` also appeared in older smoke-response caches and is **not** treated as unseen. Cache rows from synthetic controls without real candidate code were not counted as exposures.

The first two audit snapshots were preserved as `selection_audit_initial.json` and `selection_audit_before_archived_scores.json`. The initial pass could not map nine requests from an early Channel-D cache because candidate code was JSON-escaped inside a tool-call message. The matcher was corrected to inspect that representation; all 24 requests in that cache then mapped. The second pass was expanded to inspect both historical archived score files explicitly. Neither refinement changed the five-candidate exposed set or the zero 1/3 pool count. Both happened before any selection, Docker oracle, or model inference.

## Stage status and unavailable measurements

| Stage | Planned | Completed | Status and reason |
| --- | ---: | ---: | --- |
| Fresh balanced selection | 8 candidates, two per result stratum | 0 selected | **BLOCKED**: no 1/3 candidates in the 29-record pool. |
| Per-assertion Docker oracle | 8 vectors × 3 assertions | 0 | Not started because no fixed eight-candidate set exists. |
| A: assertion extraction | 16 calls | 0 | Not started. |
| B: individual pass/fail predictions | 16 calls | 0 | Not started. |
| C: independent aggregate predictions | 16 calls | 0 | Not started. |
| Cross-stage and WM-C/WM-B analysis | 8 candidates × 2 models | 0 | Unavailable; no model outputs exist. |

No 48-call result matrix, model raw outputs, format rates, extraction accuracy, per-assertion accuracy, exact-vector accuracy, aggregate accuracy, pass-count distributions, or cross-call consistency results can be computed. No model weights were loaded for this blocked selection. The existing registered model identifiers and inference settings were not altered.

## Historical context and interpretation

The [failure-isolation diagnostic](WM_Failure_Isolation_Results_20261112.md), [synthetic direct-count diagnostic](Direct_Pass_Count_Diagnostic_20261112.md), and [four-real-candidate direct diagnostic](Direct_Real_Candidates_Diagnostic_20261112.md) remain historical context. The proposed new study required **fresh** candidates so that assertion extraction, individual execution predictions, and aggregate counts could be compared without repeatedly probing the same four examples. The missing 1/3 stratum prevents that intended comparison. This report does not infer anything new about either model's assertion reading or execution reasoning.

The shortage is a property of the current three-task, 29-candidate local pool, not a model result or a statistical verdict. It cannot be repaired by choosing a different ordering, using previously exposed candidates, changing a test, imputing a 1/3 result, or silently weakening the required balance. The original smoke parse-failure gate remains closed; P0 and official pilot scoring remain unstarted.

## Validation and next decision

The selection audit has regression checks for deterministic output, prior-exposure detection, unique candidate IDs/code hashes, the four truth strata, the required two-per-stratum balance, and separate ignored artifact paths. Validation completed before publication: `.venv\Scripts\python.exe -m pytest -q` **219 passed**; `.venv\Scripts\ruff.exe check src tests` **passed**; `.venv\Scripts\ruff.exe format --check src tests` **51 files already formatted**; `git diff --check` **passed**.

**Recommended next action:** The project owner should decide whether to authorize a new, separately fixed candidate-acquisition protocol that can supply two genuine 1/3 cases while preserving fresh-candidate status. Until that decision is made, this diagnostic stays blocked and no model calls should be started.
