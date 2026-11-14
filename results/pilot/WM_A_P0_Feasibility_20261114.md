# WM-A P0 feasibility: BLOCKED_INCOMPLETE_EVIDENCE

**Audit date:** 2026-11-14 (Asia/Dhaka). **Branch:** `pilot/steps-0-1`;
starting commit `2a2355abbdc77683593b6f69c3a944d18fbe9361`.
The registered 100-call P0 trial did **not** finish. There is no valid P0
feasibility decision, no `results/pilot/p0.json`, and no authorization to
start scientific scoring.

## Model and environment

| Item | Verified observation |
| --- | --- |
| WM-A | `Qwen/Qwen-AgentWorld-35B-A3B`, source revision `60d2b0434a53d2e62a7c00a489586815d94ebffb`, Apache-2.0 |
| GGUF | Q4_K_M, 21,166,758,784 bytes, SHA-256 `98de3cd55f5bd89a15708e084ccbb838ff00dec6c35e9daa15eb3f3fad596bdd` (full local file hash checked before inference) |
| Local server | llama.cpp build `b12110`, commit `cd959bae9`, binary SHA-256 `00d50686815af38249d0218c91558fbd0e9093ac8c074bac86196907f4305e31`; bound to `127.0.0.1:8080` |
| Serving | 8,192-token context, `--jinja --reasoning-format none`, largest attempted offload setting of **41 GPU layers**, loaded in both sessions without OOM |
| Hardware | NVIDIA GeForce RTX 5060 Ti, 16,311 MiB VRAM; 16,216,674,304 bytes physical RAM; 18,349 MiB allocated pagefile at preflight |
| Preflight storage | 44,102,905,856 bytes free on E: and 17,599,848,448 bytes free on C: |

The first server load took **26.24 s** (PID 31240); the resumed load took
**28.23 s** (PID 39088). The first session ended during a local session
handoff after 18 completed requests. Its lock was copied and removed only
after PID 31240 was absent and port 8080 was free. The resumed session used
the same 41-layer Q4 setting and replayed those 18 cached responses with
their original live timings. It stopped after the 62nd response because
`nvidia-smi` returned no valid single-GPU memory reading. The second server
shut down and removed its lock. Both server logs and structured load records
remain under `data/`.

The registered Q3_K_M weights remain unavailable and **were not tested**.
Q3 fallback is not presently required because Q4 loaded successfully.

## Frozen input provenance

The existing manifest `data/p0/selection_manifest.json` was verified against
the pilot source files and model-facing message hashes. Its SHA-256 identity
is `81431897467fe7a62821c44967c888bfd1b9bec9ae8520538470fe35051827e0`.
It contains **12 distinct ready tasks**, **100 unique existing assignments**,
50 per channel, and all nine frozen conditions (T0 11, NEU_A 11, NEU_B 11,
NAT 11, TRUE 11, MIS_OUTCOME 12, MIS_VERIFY 11, MIS_PROPERTY 11,
MIS_AUTHORITY 11). No source task, candidate, item, condition, or prompt was
regenerated. The preflight check found no raw Docker ground-truth result in
the model messages. Sampling remained temperature 0.0, top-p 1.0, seed 0,
and 1,024 maximum completion tokens.

## Partial execution and measured evidence

**62/100** planned 1,024-token responses were cached. There are **61**
matching persisted live HTTP and GPU-memory observations. One completed
response has no live GPU-memory observation, so a complete, valid trial cannot
be reconstructed. The first interrupted session produced 18 cached calls;
the resumed run reused those 18 and made 44 further live requests. No
completed response was deleted, cleared, or repeated. The incomplete
measurement record is
`data/p0/measurements/b9d09428692151008470b2de80be43b9cf5092093dee2d9ad70199.json`.

The following figures are **descriptive for the 61 measured calls only**;
they are not a P0 result or input to the registered decision table:

| Metric | Partial observation |
| --- | ---: |
| Median HTTP inference latency | 101.43 s |
| 90th-percentile HTTP latency | 106.12 s |
| Aggregate completion throughput | 10.15 tokens/s |
| Sum of recorded HTTP inference durations | 6,150.21 s |
| Peak sampled live GPU memory | 15,926 MiB |

The one-time startup durations are reported separately above and were not
included in call latency. A trustworthy total trial elapsed time is
unavailable because the trial was interrupted and then stopped. No cache
lookup duration or idle GPU reading was substituted for a live measurement.

## Output validity and stopping evidence

| Channel | Cached calls | Parse successes | Parse failures | Truncated before `RESULT` | Wrong denominators |
| --- | ---: | ---: | ---: | ---: | ---: |
| C | 31 | 1 | 30 (96.77%) | 30 | 0 |
| D | 31 | 8 | 23 (74.19%) | 23 | 0 |
| **Total** | **62** | **9** | **53 (85.48%)** | **53 (85.48%)** | **0** |

Finish reasons were `length` for 61 outputs and `stop` for one. The
independent audit verified the exact cache request hashes, raw HTTP bodies,
completion records, manifest membership, parsing, and all 61 persisted live
observations. The 62nd completed call was:

- Item: `mbpp-633:mbpp-633-g10:D:NAT:kt_ab:vendored`.
- Request key: `675281ba380346155c537838d325bf18de2e58f24b8b38dea854a5389e41478d`.
- Raw-output SHA-256: `0efa5258550aa36b1b405032959e77bca7b6a6f9597be41d58a6388d00419db0`.
- HTTP latency: 106.37 s; completion: 1,024 tokens; finish reason: `length`;
  parse: fail, no `RESULT` line. The raw output ends mid-reasoning: “Wait,
  the formula in the code is:”.
- Cache response SHA-256: `c54ee1caaeb81fc04b4f24d3c26e05ed30ba48c8cd1bb87c98ddaface2e9ad3b`.
- **No matching live GPU-memory observation** was persisted. The monitor
  reported `P0 received no valid single-GPU memory reading from nvidia-smi.`
  The invalid command output was not captured, so its underlying cause is
  unknown. A subsequent manual `nvidia-smi` query succeeded.

The observed truncation fraction already exceeds 5%, but the registered
condition applies to a **completed 100-call first pass**. That pass stopped
at 62 calls. The authorized 2,048-token escalation did not occur, and the
10% final parse gate was not applied. These interim parse rates do not
constitute `P0_PARSE_FAILURE_STOP`; this is a measurement-integrity stop.
The separate first-200-call pilot scoring checkpoint was not run.

## Decision and preservation

**Status: `BLOCKED_INCOMPLETE_EVIDENCE`.** There is no legitimate `full`,
`reduced`, or `drop_wm_a` decision. Q4 hardware loading succeeded, but P0
timing and parsing compliance remain unestablished for the complete sample.
No KT-A, KT-B, or KT-C validity verdict is assigned. The owner-authorized
P0-only stage exception does not reopen the failed original WM-C smoke gate.

The post-run historical inventory passed: **8,882** current protected files
match the pre-run SHA-256 baseline
`56b8326c864a573dd2684143bf5ef4bd992773bf280fa7fd925ee93a51e9513e`;
the **8,852** protected historical files match their approved prospective
baselines, including both prior cache-preservation exceptions. The initial
post-run inventory check identified two newly generated `statistics.pyc`
files, not changed historical artifacts. The check passed after excluding
only those two exact interpreter-bytecode paths; the failed check and scope
correction are recorded in `deviations.md`. Raw P0 cache, measurements,
server logs, and audit files remain under ignored `data/`; no historical
model response, prompt, dataset, or smoke record was overwritten. All P0
inference used the local server. No pilot scoring or generated-code execution
was performed.

Validation: **266 tests passed**; Ruff lint passed; Ruff format checked 67
files; `git diff --check` passed. No `llama-server.exe` process or server lock
remained after the stop. The original WM-C smoke gate remains closed.

**Next action:** The project owner should approve an explicit recovery
protocol for the cached 62nd response with missing live VRAM evidence before
any further P0 inference. Preserve the original response; do not silently
replay it, impute its memory reading, or issue a feasibility verdict.
