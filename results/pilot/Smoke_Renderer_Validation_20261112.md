# Smoke renderer validation, 2026-11-12

Status: **FAILED the existing parse gate**. The isolated three-task smoke run
was stopped during WM-C `kt_ab` scoring. P0, full pilot data generation, and
pilot scoring were not started.

## Repository and validation

- Branch: `pilot/steps-0-1`; fast-forwarded to
  `3b2239a03b9623c96c4b2ad6774a9798bb899265` without discarding the
  existing untracked report.
- `.venv\Scripts\python.exe -m pytest -q`: **184 passed**.
- `.venv\Scripts\ruff.exe check src tests`: **passed**.
- `.venv\Scripts\ruff.exe format --check src tests`: **passed** (41 files;
  Ruff reported a non-fatal cache-write warning).
- The new commit removed one blank line in a test. Across the fetched renderer
  repair commits, frozen configuration, parser, statistics, and decision files
  did not change.

## Prompt and artifact checks

Representative prompts for all nine conditions were inspected in both
channels. Channel C carries the unchanged shell action in a JSON action array,
with `duration` from the existing configuration and a final newline after
`python run_tests.py`. Channel D retains the same `write_files` and
`run_command` calls, tests, code, and thoughts; the simulator output instruction
is separated and states that `n = len(TESTS)`. `T0` has no stray thought or
comment. No actual expected test result was added to either prompt.

The previous active items, scores, WM-C SQLite database, WAL, and SHM were
archived in `data/smoke/audit/prompt_format_before_rerun_20261111T204010Z/`.
The earlier historical archive was preserved. `inert --smoke build-items`
created 310 new items. Comparison with the archived item file confirmed all
310 non-message fields unchanged; only rendered messages differ (211 Channel C,
99 Channel D). Inertness checks passed during item construction.

## Interrupted WM-C scoring

The scorer persisted its first 10 scores before interruption. SQLite contains
19 completed local WM-C calls, matched unambiguously to `kt_ab` items and
checked against the persisted records. All counts below use those 19 completed
calls; the 9 cache-only calls are identified in the evidence file.

| Channel | Completed | Parsed | Failed | Failure rate |
| --- | ---: | ---: | ---: | ---: |
| C | 10 | 4 | 6 | 60.0% |
| D | 9 | 7 | 2 | 22.2% |
| Overall | 19 | 11 | 8 | 42.1% |

Full raw outputs, task and candidate IDs, conditions, expected and predicted
denominators, completion tokens, finish reasons, timestamps, and score/cache
provenance for **every failure** are in
`data/smoke/audit/prompt_format_rerun_20261112_failures.json`.

- Five Channel-C failures ended with `finish_reason=length` at 1,024 tokens
  without a valid `RESULT`; four of these repeated `python run_tests.py` over
  130 times. One included a missing-file hallucination.
- The sixth Channel-C failure also reached 1,024 tokens. It contained a valid
  `RESULT: 3/3` but later emitted `RESULT: 1/1`; the frozen last-match parser
  correctly rejected its final denominator for a three-test task.
- The two Channel-D failures returned `RESULT: 0/10` with `finish_reason=stop`
  for a task with three tests. Denominator errors therefore remain.

The first persisted batch already had 5 failures among 10 records, exceeding
the frozen 10% parse-failure gate. Scoring was stopped; no further prompt
adjustment, `kt_c` scoring, smoke analysis, or smoke report generation ran.
The INERT server process exited, and its stale lock was removed after checking
the recorded PID.

The previous interrupted rerun's 16/18 Channel-C and 8/12 Channel-D parsed
counts are historical incomplete-run observations. They are not a reliable
improvement baseline for these 19 completed calls.

Recommended next action: inspect the archived raw failures and decide whether
to authorize another prompt-format repair or use the design's in-house prompt
fallback. Any new adaptation requires a documented deviation and a fresh
smoke run; the existing parse gate and parser must remain unchanged.
