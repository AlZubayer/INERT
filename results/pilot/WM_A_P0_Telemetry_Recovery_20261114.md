# WM-A P0 call-62 telemetry recovery: REPLAY_EVIDENCE_COLLECTED

**Date:** 2026-11-14 (Asia/Dhaka). **Branch:** `pilot/steps-0-1`.
This is one owner-authorized **independent replay** of a single P0 request.
It did not measure the original call retroactively, complete P0, or produce
`results/pilot/p0.json`.

## Original incident and immutable target

The interrupted Q4_K_M P0 first pass has 62/100 cached responses and 61
matching live GPU-memory observations. Call 62 alone lacks a persisted VRAM
reading because the original `nvidia-smi` poll returned no valid value.
Its original request and evidence are:

| Field | Original value |
| --- | --- |
| Item | `mbpp-633:mbpp-633-g10:D:NAT:kt_ab:vendored` |
| Request key | `675281ba380346155c537838d325bf18de2e58f24b8b38dea854a5389e41478d` |
| Raw-output SHA-256 | `0efa5258550aa36b1b405032959e77bca7b6a6f9597be41d58a6388d00419db0` |
| Cached API-response SHA-256 | `c54ee1caaeb81fc04b4f24d3c26e05ed30ba48c8cd1bb87c98ddaface2e9ad3b` |
| HTTP latency | 106.37190800003009 s |
| Output validity | 1,024 tokens; `length`; parse `fail`, no valid `RESULT` |

The original 61-observation record is
`data/p0/measurements/b9d09428692151008470b2de80be43b9cf5092093dee2d9ad70199d4db987099.json`
with file SHA-256
`b7d7bb3744a12136b315d12cfdf13a6a5ce84f352107fab6a8f3ddb953587a46`.
The prior feasibility report abbreviated this filename; `deviations.md`
records the exact path without changing that report or the file. The
original `data/cache/wm_a.sqlite` file SHA-256 is
`e5ee8fcaffc33c6f47eeb53d23edb56a686db9a167aee45a04d3d2934b8245dd`.
SQLite `integrity_check` returned `ok`, with 62 unique original requests.

## Engineering repair and isolation

The recovery code audits every `nvidia-smi` attempt with UTC and monotonic
times, exact command arguments, return code, raw stdout and stderr, duration,
parse result, MiB value, and acceptance. It requires one positive integer
from the single GPU. A process-wide lock serializes concurrent polling.
Each poll makes one initial attempt and at most two additional attempts,
separated by a fixed 0.1-second delay. Three invalid attempts stop without
inventing a memory value. The same bounded polling path is wired into any
later *separately authorized* P0 run, with its own ignored audit stream.

The new `p0-telemetry-replay` CLI command uses the established local
`ModelServer` and `CachedClient` with a separate SQLite cache. It creates a
durable one-replay guard before any inference request. An actual second
invocation returned through that guard without starting a server or making
another live request. Regression tests cover valid and invalid telemetry,
nonzero exits, timeouts, all-retry failure, multi-GPU and malformed output,
concurrent polling, audit completeness, original-record preservation,
isolation, and guard idempotency. **281 tests passed** before inference and
again after it; Ruff lint and format passed (71 files), as did
`git diff --check`.

## Isolated replay evidence

The frozen P0 manifest identity remained
`81431897467fe7a62821c44967c888bfd1b9bec9ae8520538470fe35051827e0`.
The replay recomputed the exact original request key before starting the
server. Its settings were Qwen AgentWorld 35B A3B Q4_K_M, model SHA-256
`98de3cd55f5bd89a15708e084ccbb838ff00dec6c35e9daa15eb3f3fad596bdd`,
llama.cpp build `b12110`/commit `cd959bae9`, server binary SHA-256
`00d50686815af38249d0218c91558fbd0e9093ac8c074bac86196907f4305e31`,
41 GPU layers, 8,192 context tokens, original Jinja/native reasoning
behavior, temperature 0.0, top-p 1.0, seed 0, and 1,024 completion tokens.
The model-facing messages matched the original manifest and cached request
exactly. The server bound only to `127.0.0.1:8080`, loaded in **25.22 s**
(PID 29480), and shut down with its owned lock removed.

All replay artifacts are under the ignored directory
`data/p0/telemetry_recovery_20261114/`: `replay.sqlite`,
`replay_request_manifest.json`, `raw_api_response.json`, `completion.json`,
`telemetry_attempts.jsonl`, `supplemental_measurement.json`,
`server_audit.json`, `output_comparison.json`, `independent_audit.json`,
`original_before.json`, `original_after.json`, `audit_summary.json`, and the
one-replay guard. The isolated cache passes SQLite `integrity_check` and
contains **exactly one** request, with the original key.

| Replay metric | Observation |
| --- | ---: |
| New live completion requests | 1 |
| HTTP latency | 96.56296379998093 s |
| Completion tokens / finish reason / parse | 1,024 / `length` / `fail` |
| Peak VRAM during replay | 15,774 MiB |
| Accepted telemetry polls | 653 total: 1 idle preflight, 652 during live inference |
| Rejected polls / successful live retries | 0 / 0 |

All 652 live samples have recorded monotonic times within the live request
window. The supplemental measurement record has its own provenance label and
integrity hash. No invalid telemetry occurred during this replay, so the
bounded retry behavior was validated by mocks rather than exercised live.

## Comparison and limits

The replay raw output is **byte-identical** to the original; both SHA-256
values are
`0efa5258550aa36b1b405032959e77bca7b6a6f9597be41d58a6388d00419db0`.
Both outputs fail the frozen parser, finish at `length`, and contain 1,024
completion tokens. The full replay API body has SHA-256
`bb0453a20923513b875d439ca55630939562366f7d39f73d9a2cbeb3fdc4e59b`;
it differs from the original API body in `id`, `created`, and `timings` only.
Replay HTTP latency is 9.81 s shorter than the original 106.37 s. Its
15,774 MiB sampled peak is 152 MiB below the **15,926 MiB peak across the
prior 61 measured P0 calls**; that prior peak is not a call-62 value.

The identical raw output supports repeatability under the registered
configuration. The **original call-62 VRAM observation remains unavailable**.
The replay VRAM and latency are independent supplemental observations and
were not inserted into the original cache or P0 measurement record.

## Experimental integrity and recommendation

The pre- and post-replay snapshots of the original cache, WAL/SHM, P0
measurement, and frozen manifest are identical. The original cache still
holds 62 calls; the original measurement still holds 61 observations.
The post-replay historical inventory passed: 8,882 protected current files
and 8,852 protected historical files matched the approved baselines. No
prompt, text condition, parser, seed, model revision, threshold, or decision
rule changed. No P0 call 63-100, 2,048-token escalation, pilot scoring, or
generated-code execution occurred. The original WM-C smoke gate remains
closed. No P0 feasibility verdict was issued.

The partial first pass remains unfavorable: the 61 measured calls had a
101.43 s median and 106.12 s P90 HTTP latency, and 53/62 cached outputs
were truncated before `RESULT` and failed parsing. Those 53 truncations
already guarantee a first-pass rate above the 5% escalation threshold if
the same 100-call pass were completed. These figures are **not** a completed
P0 result, do not establish the final 10% parse verdict, and cannot support
a registered `full`, `reduced`, or `drop_wm_a` decision.

**Recommendation:** Stop further WM-A P0 GPU spending unless the owner
separately decides that the unfavorable partial latency and parsing evidence
justifies a completed trial. The replay does not authorize adopting its VRAM
as the original reading or resuming inference.
