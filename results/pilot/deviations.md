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
