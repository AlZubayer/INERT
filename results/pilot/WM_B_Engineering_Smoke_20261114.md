# WM-B engineering smoke: ENGINEERING_SMOKE_PASS after accepted recovery

**ENGINEERING STATUS: ENGINEERING_SMOKE_PASS for the authorized 198-call WM-B core matrix.** All assignments completed, the frozen parse gate passed, and scores reconcile with raw local responses. Channel D's smoke-level T0 balanced accuracy is below the registered validity floor; that finding does not turn this engineering check into an official pilot verdict. This is an engineering-only substitution authorized by the project owner. The original WM-C smoke gate remains closed. P0 and pilot scoring remain unstarted.

## Prepared evidence

- Starting branch and commit: `pilot/steps-0-1`, `ce09ef20a56f3053ac51620011865a5bf1fd5486`.
- Isolated directory: `data/smoke/diagnostics/wm_b_engineering_smoke_20261114/`. The original 3 tasks, 29 candidates, 29 Docker execution records, 11 thoughts, 310 rendered items, and 211 Channel-C inertness records were schema-checked, cross-checked, and copied byte for byte. There are 11 core candidates and 198 core WM-B assignments (99 per channel, 11 per condition). The 112 optional KT-C items were frozen but were not authorized for scoring before the KT-A stage gate.
- The frozen manifest contains exact messages and message hashes for all 310 existing items, with executed truth in a separate evaluation file. Manifest SHA-256: `68e97583b023e9acec815c0e14c9db97343afec6b0375c5f94b7eadbe71a552d`. Source hashes and a 587-file historical inventory are recorded there. Ten representative core prompts were inspected across both channels, T0, neutral, natural, true, and misleading conditions. The official renderer reconstructed the saved messages exactly; no literal executed `RESULT: number/number` appeared in these prompts.
- WM-B is the configured `Qwen/Qwen2.5-7B-Instruct` Q4_K_M model. Both local GGUF shards matched the pinned SHA-256 hashes `dfce12e3862a5283ccfb88221b48480e58745165de856439950d0f22590580db` and `539cf93f78e887edea1c04e2d7d8cdaca9d01dae9c9025bcb8accbe29df3d72a`. The local llama-server binary matched the earlier diagnostic hash `00d50686815af38249d0218c91558fbd0e9093ac8c074bac86196907f4305e31`; configured build and commit are `b12110` / `cd959bae9`. The manifest records the exact server arguments and frozen temperature 0, top-p 1, seed 0, 1,024 completion-token and 8,192 context settings.

## Original BLOCKED event and integrity finding

The first full `pytest -q` run after the historical inventory modified one existing file: `data/smoke/diagnostics/assertion_execution_20261112/run_48/cache/sandbox.sqlite`. Its SHA-256 changed from `7722ab53d01b60f2af5f56597d913ea932e194abcabf37e652ce1ee54022c246` to `0a02c5112a63710576970d47596fea6b914cfd205a15912d2369b7318ce96697`. The test `test_instrumented_oracle_matches_harness_exception_semantics_in_docker` used `RunPaths` for the frozen diagnostic and invoked `DockerSandbox.run(..., use_cache=False)`. That function still performs an `INSERT OR REPLACE` into its SQLite cache. The cache passes SQLite `integrity_check`; it currently has 18 records, including the two test requests. There is no saved pre-test byte copy from which to restore the original file, and the runner does not silently rebaseline its inventory. All other 586 inventoried files retained their original hashes. The test now uses a temporary cache, and a second full test run made no further historical changes.

Because the instruction required all historical files to remain byte-for-byte unchanged, the pre-inference gate was stopped. At that point, the prepared manifest could not pass `verify` until the discrepancy was resolved explicitly. No model server had been started, and no engineering score or cache file existed.

## Approved recovery (prospective baseline)

The project owner subsequently approved `HISTORICAL_PRESERVATION_EXCEPTION_ACCEPTED` for the one changed SQLite file. This does **not** make the original preservation check pass. The original 587-file inventory remains at `data/smoke/diagnostics/wm_b_engineering_smoke_20261114/historical_inventory.json`; the prospective inventory is a separate file in the same directory and differs only for that cache. The approved current hash is `0a02c5112a63710576970d47596fea6b914cfd205a15912d2369b7318ce96697`, prospectively only.

The current database is 86,016 bytes. SQLite `integrity_check` returned `ok`; the `executions` table contains 18 records. No WAL or SHM file existed. An exact byte copy and a SQLite backup snapshot, with independent hashes, are preserved under `data/smoke/diagnostics/wm_b_engineering_smoke_20261114/preservation_incident/`. No pre-test byte copy was found in the repository. The archived eight-candidate per-assertion oracle JSON still contains the earlier experiment's detailed and aggregate Docker outputs; all its distinct output strings are present in the current cache. The two additional cache outputs are the Docker regression-test cases. The changed cache therefore does not appear to hold unique, lost evidence required to validate that earlier report.

`DockerSandbox.run(..., use_cache=False)` now bypasses all cache creation, reads, and writes while retaining its Docker execution path. Docker tests use temporary paths, and pytest no longer opens historical diagnostic SQLite caches. Cache protocol tests retain temporary SQLite coverage; archived response-accounting tests still validate the exported response records. The complete suite passed with **244 tests**, and the prospective inventory verified **zero additional historical-file modifications** after that suite. The frozen WM-B manifest verified before inference. This recovery section records the accepted exception; the original `BLOCKED` event above remains part of the record.

## Original blocked accounting

| Measure | Value |
| --- | ---: |
| Planned core calls | 198 |
| Completed | 0 |
| New / cached | 0 / 0 |
| Incomplete core calls | 198 |
| Parse failure, Channel C | unavailable (0 calls) |
| Parse failure, Channel D | unavailable (0 calls) |
| Exact-count accuracy | unavailable |
| T0 balanced accuracy | unavailable for both channels |

No parse, validity, or KT-A gate was evaluated. The previous diagnostic's WM-B C0/D0 subset had 0/44 parse failures in each channel, but it used only four conditions and cannot substitute for this unrun matrix. The earlier WM-C failures remain unaffected.

## Validation at the original blocked stop

The final local validation completed **243 passing tests**; Ruff lint, Ruff format, and `git diff --check` passed. The official renderer, parser, condition templates, config, thresholds, seeds, and decision rules were not edited. No model server remains running. The engineering runner and tests are local and uncommitted; no files under `data/` were staged.

The owner subsequently approved the prospective baseline documented above. No WM-B calls had occurred at this original stop.

## Resumed 198-call core run

The resumed run used the unchanged official vendored renderer and Section 9.5 parser. The cache key binds each exact message to the local WM-B model identity, server flags, temperature 0, top-p 1, seed 0, and 1,024-token completion limit. The server used 8,192 context and 99 GPU layers on `127.0.0.1`. The separate scoring cache, typed scores, raw API responses, log, and independent audit are under `data/smoke/diagnostics/wm_b_engineering_smoke_20261114/`. No optional KT-C call was started.

| Measure | Channel C | Channel D | Combined |
| --- | ---: | ---: | ---: |
| Planned and completed core assignments | 99/99 | 99/99 | 198/198 |
| New requests | 97 | 97 | 194 |
| Exact duplicate cache hits within this run | 2 | 2 | 4 |
| Parser-valid `RESULT: k/3` | 99/99 | 99/99 | 198/198 |
| Parse failures | 0/99 (0%) | 0/99 (0%) | 0/198 (0%) |
| Exact executed pass count | 29/99 (29.3%) | 39/99 (39.4%) | 68/198 (34.3%) |
| Binary pass/fail accuracy | 37/99 (37.4%) | 41/99 (41.4%) | 78/198 (39.4%) |
| T0 balanced accuracy | 0.5833 | 0.5000 | separate by channel |
| T0 false-pass predictions on failing candidates | 5/6 | 6/6 | — |

Each of the nine registered conditions has 11 completed, parser-valid assignments in each channel. Across all 198 assignments, there were **zero** wrong denominators, missing `RESULT` lines, or `finish_reason=length` completions. There are no remaining parse-failure raw examples. The four cache hits are repeated exact prompt requests inside this isolated run; historical smoke and diagnostic caches were not used. The independent audit matched all 198 scores to the frozen manifest, cache request hashes, raw API bodies, model identity, and parser output. The 194 SQLite cache rows pass `integrity_check`.

The existing 10% overall core-block parse-failure gate did not fire. The first-200-call checkpoint is inapplicable to a 198-call block. The all-cells-INVALID stop rule did not fire: Channel C's exploratory three-task T0 balanced accuracy is 0.5833, inside the Section 11.2 validity interval, while Channel D's 0.5000 is below its 0.55 floor and is **INVALID** for that smoke sample. These are dependent observations from only 11 candidates across three tasks; they do not decide full-pilot validity or KT-A, KT-B, or KT-C outcomes. Low exact-count accuracy is an execution-prediction finding, distinct from complete format compliance.

The earlier prompt-adaptation diagnostic observed 0/44 parse failures for WM-B C0 and D0 on four conditions. This full nine-condition core run also has 0 parse failures. The cases and prompt family overlap; the comparison is descriptive and is not an independent improvement estimate. WM-C was not rerun.

## Final integrity and limits

The approved one-file preservation exception remains explicitly open as a historical fact. After accepting its prospective hash, the 587-file inventory showed **zero additional changes** after the regression suite, WM-B inference, and independent audit. The original before-test inventory, current byte copy, SQLite snapshot, and incident metadata remain in the ignored isolated directory. All source task, candidate, execution, thought, item, and inertness hashes match the frozen manifest. The official smoke configuration still names WM-C; `src/inert/render.py`, prompt files, condition templates, parser, thresholds, seeds, and decision rules are unchanged.

The run establishes local WM-B loading, both channel renderings, nine-condition coverage, caching, strict parsing, score persistence, and reproducible engineering accounting. It does not establish that WM-C's smoke gate passed, that WM-A can load, or that the official pilot is valid. Three tasks and within-task candidate dependence sharply limit accuracy and balanced-accuracy interpretation. No P0, WM-A, WM-C, KT-C, or pilot scoring followed this run.

**Next action:** review the WM-C smoke failure and WM-B's weak execution prediction together, then specify any next scientific step explicitly. Do not treat this engineering pass as authorization for P0 or pilot scoring.
