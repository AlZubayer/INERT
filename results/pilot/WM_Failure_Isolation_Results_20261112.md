# World-model failure isolation: results (2026-11-12)

**COMPLETE for authorized A–F2; F3 was not run because it requires separate approval.** Observed: WM-B produced a parsable final result on 80/80 real-item calls, but matched the executed pass count on only 25/80. This separates a major WM-C output-format failure from the still-unreliable execution predictions; the causal balance among model ability, prompt framing, and representation remains an inference, not a pilot verdict.

## Provenance and controls

The fixed procedure is the [A–F protocol](WM_Failure_Isolation_Protocol.md), under the [frozen design](../../Pilot_Experimental_Design.md) and [repository instructions](../../AGENTS.md). The pre-execution branch HEAD was `b0097b75e0ab3c86fd224c330cb69a8090ebe694` on `pilot/steps-0-1`; the publication head is the commit containing this report. The implementation is [diagnostic_failure_isolation.py](../../src/inert/diagnostic_failure_isolation.py). Prior context: [in-house diagnostic](Inhouse_Prompt_Diagnostic_20261112.md) and [deviations](deviations.md).

All inference was local through llama.cpp `llama-server` build `b12110`, commit `cd959bae9`, version `0.9.0-dev` (Clang 20.1.8, Windows x86_64). Executable SHA-256: `00d50686815af38249d0218c91558fbd0e9093ac8c074bac86196907f4305e31`. Hardware: NVIDIA GeForce RTX 5060 Ti, 16,311 MiB VRAM, driver 617.14. A during-E snapshot recorded 6,695 MiB used and 95% GPU utilization in local-only `data/smoke/diagnostics/failure_isolation_20261112/runtime/gpu_during_e.txt`; this was not a peak measurement. The post-run hardware and Docker image observations are in local-only `data/smoke/diagnostics/failure_isolation_20261112/runtime/environment_snapshot.json`. Docker image ID `sha256:07d4824036af339fa1b6ef769cc99d9c10a141769538b52b3b597c84f7a7b535` was used only through `DockerSandbox` for the four fixed C truths.

| Role | HF source | Source revision | GGUF repository/revision | Actual verified file SHA-256 and size | Licence |
| --- | --- | --- | --- | --- | --- |
| wm_c | Qwen/Qwen2.5-1.5B-Instruct | 989aa7980e4cf806f80c7fef2b1adb7bc71aa306 | Qwen/Qwen2.5-1.5B-Instruct-GGUF @ 91cad51170dc346986eccefdc2dd33a9da36ead9 | `6a1a2eb6d15622bf3c96857206351ba97e1af16c30d7a74ee38970e434e9407e` (1117320736 B) | apache-2.0 |
| wm_b | Qwen/Qwen2.5-7B-Instruct | a09a35458c702b33eeacc393d103063234e8bc28 | Qwen/Qwen2.5-7B-Instruct-GGUF @ bb5d59e06d9551d752d08b292a50eb208b07ab1f | `dfce12e3862a5283ccfb88221b48480e58745165de856439950d0f22590580db` (3993201344 B)<br>`539cf93f78e887edea1c04e2d7d8cdaca9d01dae9c9025bcb8accbe29df3d72a` (689872288 B) | apache-2.0 |

All calls used temperature `0.0`, top-p `1.0`, max completion tokens `1024`, seed `0`, and requested context `8192` from [pilot.yaml](../../configs/pilot.yaml). The server command used the pinned first GGUF shard with `--host 127.0.0.1 --port 8080 --ctx-size 8192 --n-gpu-layers 99 --jinja --reasoning-format none`; F2 added `--parallel 1`. Servers ran one at a time. WM-B loaded exactly the two pinned Q4_K_M shards; no alternate model or quantization was used.

| Unchanged prompt source | SHA-256 |
| --- | --- |
| [prompts/inhouse/wm_terminal.txt](../../prompts/inhouse/wm_terminal.txt) | 7479882e009db9ea7575f9618f2587da664de1d3e6709acc3b32e4c98ba9e468 |
| [prompts/inhouse/wm_tool.txt](../../prompts/inhouse/wm_tool.txt) | 465551d71f3cd1e4ee52eaf217066cf7e3852d0c6efb53d55456a1e2cd4e490f |
| [prompts/vendored/wm_terminal.txt](../../prompts/vendored/wm_terminal.txt) | 27b9851255cbd4b18b0c57123134f7148ac41406557c3da2c8b93fb9d532a77b |
| [prompts/vendored/wm_tool.txt](../../prompts/vendored/wm_tool.txt) | 70b89768275627b63a74a3757e85761977b71cec9b013f76ba038c27a5e7a7d1 |

Fixed source hashes: `configs/models.yaml` `cf6797cfd00b6d49bcb0af3961e488c6f7a4a7cf679672ca0576e8d2bbc700ab`; `configs/pilot.yaml` `e963d47167a5060eccd5f3f7e74af1646e9f5a2fd0dfcccceda16f1d9a7e80ef`; `data/smoke/tasks.jsonl` `5ed10378c6a4c908a5419cdfb7b80173a16bbde7a2ef658c48aef48cf595b6f3`; `data/smoke/candidates.jsonl` `319f50be284222ae9ea76aa0dcc4222aeac720fee603a242ee9047f0e6ab3700`; `data/smoke/thoughts.jsonl` `e729cf4a3337b5bafb68af80e70f4c2fe92691dedaf1604491d64d8400b7af04`; `data/smoke/items.jsonl` `6bbea63c586b0b63ba671f1181a5966dd624c2bb48f113cfa6128f004a9094f2`; prior selection `0820c33910d662ebb0d26c1bd0341e7ddf4e737da63bfbe6d15a09d6e3c52330`; prior in-house items `312b064fd8e341e931d93e7f001ccd98804359c83f032521dcf25af2b36c0870`. Full source-file hashes, all 148 exact input messages and message hashes are in `data/smoke/diagnostics/failure_isolation_20261112/manifest.json` (SHA-256 `189f19108db6a2d766cb22cdf4931c52495b0839b54a6f864485d13f10581188`). Responses, original API JSON, finish reasons, token counts, and cache-hit flags are under the same ignored `data/` folder; `analysis.json` SHA-256 is `10f42e3bf1a92a35d464cb91f97a2f014aa57aaf648934bbd12427707126b13c`.

An independent 148/148 response-to-SQLite audit is in local-only `data/smoke/diagnostics/failure_isolation_20261112/cache_audit.json` (SHA-256 `7ca50328f10b6c28f8675c2dab9f903485fab046e06f224ae0d086417d878af6`). Raw outputs, request hashes, and provider prompt-token counts matched their cached records.

The real-item anchor was unchanged: `mbpp-440-g00` 0/3, `mbpp-310-g00` 2/3, `mbpp-440-g04` 3/3, `mbpp-265-g01` 3/3. C's synthetic outcomes were independently confirmed inside Docker as 0/3, 1/3, 2/3, 3/3. No model output or expected concrete `RESULT` was inserted into C–E prompts.

## Stage completion

| Stage | Planned | Attempted | Success definition and observed | Main errors | Status |
| --- | --- | --- | --- | --- | --- |
| A | 8 calls | 8/8 | Exact answer 6/8 | A3 wrong or verbose: 2/8 | DONE |
| B | 20 calls | 20/20 | Strict correct integer 0/20; integer-only shape 4/20 | Two literal `10`s; 16/20 non-integer outputs | DONE |
| C | 16 calls + 4 Docker truths | 16/16 + 4/4 | Frozen-parser valid 13/16; exact executed count 7/16 | 1 wrong denominator, 2 no result, 3 length stops | DONE |
| D | 16 calls | 16/16 | Frozen-parser valid 6/16; exact executed count 2/16 | 6 wrong denominators, 4 no result, 5 length stops | DONE |
| E | 80 calls | 80/80 | Frozen-parser valid 80/80; exact executed count 25/80 | 55/80 parsed but wrong counts | DONE |
| F1 | 1 offline inspection | 1/1 | Default 4 slots, 8,192 tokens/slot observed | No logged context truncation | DONE |
| F2 | 8 conditional calls | 8/8 | Parser valid 1/8 vs baseline 2/8; exact 0/8 vs 1/8 | No parsing improvement | DONE |
| F3 | Requires separate approval | 0 | None | No registered alternate quantization | NOT_RUN_REQUIRES_APPROVAL |

For C–F, `frozen-parser valid` means the last `RESULT: k/n` match had the expected denominator and `0 ≤ k ≤ n`; `exact executed count` also requires `k` to equal Docker truth. Invalid output counts as incorrect for coverage-adjusted accuracy. Failure categories can overlap.

## A: trivial runtime/chat sanity

| ID | Structure | Expected exact | Raw response | Exact | Prompt/completion tokens | Finish |
| --- | --- | --- | --- | --- | --- | --- |
| A1 | system_user | READY | 'READY' | yes | 25/2 | stop |
| A1 | user_only | READY | 'READY' | yes | 34/2 | stop |
| A2 | system_user | 2 | '2' | yes | 33/2 | stop |
| A2 | user_only | 2 | '2' | yes | 42/2 | stop |
| A3 | system_user | 3 | '4' | no | 38/2 | stop |
| A3 | user_only | 3 | 'There are 3 entries in the list [7, 8, 9].' | no | 47/18 | stop |
| A4 | system_user | RESULT: 1/3 | 'RESULT: 1/3' | yes | 35/7 | stop |
| A4 | user_only | RESULT: 1/3 | 'RESULT: 1/3' | yes | 44/7 | stop |

System+user: 3/4 exact. User-only: 3/4 exact. A3 failed both structures: one wrong count (`4`), one verbose answer that mentioned three. No empty or repeated responses occurred in A.

## B: TESTS counting by representation

| List ID | Representation | True n | Observed response preview | Integer-only | Strict correct | Finish |
| --- | --- | --- | --- | --- | --- | --- |
| mbpp-440 | B1 | 3 | 'To count the entries in the `TESTS` list without executing any test, you can use the `len(' [rest omitted] | no | no | stop |
| mbpp-440 | B2 | 3 | 'The TESTS list contains 3 entries.' | no | no | stop |
| mbpp-440 | B3 | 3 | 'To count the number of entries in the `TESTS` list without executing any tests, you can mo' [rest omitted] | no | no | stop |
| mbpp-440 | B4 | 3 | '10' | yes | no | stop |
| mbpp-310 | B1 | 3 | 'To count the entries in the `TESTS` list without executing any tests, you can use the `len' [rest omitted] | no | no | stop |
| mbpp-310 | B2 | 3 | 'The TESTS list contains 3 entries.' | no | no | stop |
| mbpp-310 | B3 | 3 | 'To count the number of entries in the `TESTS` list without executing any tests, you can mo' [rest omitted] | no | no | stop |
| mbpp-310 | B4 | 3 | 'The TESTS list contains 3 entries.' | no | no | stop |
| mbpp-265 | B1 | 3 | 'To count the number of entries in the TESTS list without executing any test, we can use th' [rest omitted] | no | no | stop |
| mbpp-265 | B2 | 3 | 'The TESTS list contains 6 entries.' | no | no | stop |
| mbpp-265 | B3 | 3 | 'To count the number of entries in the `TESTS` list without executing any tests, you can mo' [rest omitted] | no | no | stop |
| mbpp-265 | B4 | 3 | '14' | yes | no | stop |
| mbpp-440-n2 | B1 | 2 | 'To count the entries in the `TESTS` list without executing any test, you can use the `len(' [rest omitted] | no | no | stop |
| mbpp-440-n2 | B2 | 2 | 'The TESTS list contains 2 entries.' | no | no | stop |
| mbpp-440-n2 | B3 | 2 | 'To count the number of entries in the `TESTS` list without executing any tests, you can mo' [rest omitted] | no | no | stop |
| mbpp-440-n2 | B4 | 2 | 'The TESTS list contains 2 entries.' | no | no | stop |
| mbpp-440-n4 | B1 | 4 | '1' | yes | no | stop |
| mbpp-440-n4 | B2 | 4 | 'The TESTS list contains 4 entries.' | no | no | stop |
| mbpp-440-n4 | B3 | 4 | 'The TESTS list contains 4 entries.' | no | no | stop |
| mbpp-440-n4 | B4 | 4 | '10' | yes | no | stop |

B1=plain list, B2=Python `TESTS = [...]`, B3=full harness, B4=JSON `write_files` string. Every list was evaluated in all four representations; true sizes were 2, 3, or 4. Strict integer accuracy was 0/20 for every representation: 0/5 in B1, B2, B3, and B4. Four responses were integer-only, all wrong (`10`, `14`, `1`, `10`); `10` appeared as a standalone wrong answer on two B4 calls. B2 often mentioned the correct count in a sentence, which does not satisfy the fixed count-only contract. The real `mbpp-265` B2 sentence said six entries for three tests. All B calls finished normally; this control used no pilot `RESULT` parser.

## C and D: execution cases

### C: unconditional Docker-verified tests

| Case | Channel | Family | Docker expected | Observed last RESULT | Parser | Only RESULT | Count exact | Finish | First anomaly/class |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| C0 | C | vendored | RESULT: 0/3 | RESULT: 0/3 | ok | no | yes | stop | — |
| C0 | C | inhouse | RESULT: 0/3 | RESULT: 0/3 | ok | no | yes | stop | missing_file_hallucination |
| C0 | D | vendored | RESULT: 0/3 | RESULT: 0/3 | ok | yes | yes | stop | — |
| C0 | D | inhouse | RESULT: 0/3 | RESULT: 0/3 | ok | no | yes | stop | — |
| C1 | C | vendored | RESULT: 1/3 | RESULT: 3/3 | ok | no | no | stop | valid syntax, wrong count |
| C1 | C | inhouse | RESULT: 1/3 | none | fail | no | no | length | no_result, truncated, repetitive, missing_file_hallucination |
| C1 | D | vendored | RESULT: 1/3 | RESULT: 0/3 | ok | yes | no | stop | valid syntax, wrong count |
| C1 | D | inhouse | RESULT: 1/3 | RESULT: 0/3 | ok | no | no | stop | valid syntax, wrong count |
| C2 | C | vendored | RESULT: 2/3 | RESULT: 0/3 | ok | no | no | length | valid syntax, wrong count; truncated, repetitive |
| C2 | C | inhouse | RESULT: 2/3 | none | fail | no | no | length | no_result, truncated, repetitive, missing_file_hallucination |
| C2 | D | vendored | RESULT: 2/3 | RESULT: 2/2 | fail | yes | no | stop | incorrect_denominator |
| C2 | D | inhouse | RESULT: 2/3 | RESULT: 3/3 | ok | no | no | stop | valid syntax, wrong count |
| C3 | C | vendored | RESULT: 3/3 | RESULT: 3/3 | ok | no | yes | stop | — |
| C3 | C | inhouse | RESULT: 3/3 | RESULT: 0/3 | ok | no | no | stop | valid syntax, wrong count; missing_file_hallucination |
| C3 | D | vendored | RESULT: 3/3 | RESULT: 3/3 | ok | yes | yes | stop | — |
| C3 | D | inhouse | RESULT: 3/3 | RESULT: 3/3 | ok | no | yes | stop | — |

C totals: 13/16 parser valid, 7/16 exact count, 4/16 strict one-line `RESULT` only. Docker truth and raw responses are in the isolated artifact folder.

### D: real MBPP, T0 only

| Case | Channel | Family | Docker expected | Observed last RESULT | Parser | Only RESULT | Count exact | Finish | First anomaly/class |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| mbpp-440-g00 | C | vendored | RESULT: 0/3 | none | fail | no | no | length | no_result, truncated, repetitive |
| mbpp-440-g00 | C | inhouse | RESULT: 0/3 | none | fail | no | no | length | no_result, truncated, repetitive, missing_file_hallucination |
| mbpp-440-g00 | D | vendored | RESULT: 0/3 | RESULT: 3/3 | ok | yes | no | stop | valid syntax, wrong count |
| mbpp-440-g00 | D | inhouse | RESULT: 0/3 | none | fail | no | no | stop | no_result |
| mbpp-310-g00 | C | vendored | RESULT: 2/3 | RESULT: 0/3 | ok | no | no | length | valid syntax, wrong count; truncated, repetitive |
| mbpp-310-g00 | C | inhouse | RESULT: 2/3 | RESULT: 0/10 | fail | no | no | stop | incorrect_denominator, repetitive |
| mbpp-310-g00 | D | vendored | RESULT: 2/3 | RESULT: 0/10 | fail | yes | no | stop | incorrect_denominator |
| mbpp-310-g00 | D | inhouse | RESULT: 2/3 | RESULT: 3/3 | ok | yes | no | stop | valid syntax, wrong count |
| mbpp-440-g04 | C | vendored | RESULT: 3/3 | RESULT: 0/3 | ok | no | no | length | valid syntax, wrong count; truncated, repetitive |
| mbpp-440-g04 | C | inhouse | RESULT: 3/3 | RESULT: 0/10 | fail | no | no | stop | incorrect_denominator, repetitive |
| mbpp-440-g04 | D | vendored | RESULT: 3/3 | RESULT: 3/3 | ok | yes | yes | stop | — |
| mbpp-440-g04 | D | inhouse | RESULT: 3/3 | RESULT: 3/3 | ok | no | yes | stop | — |
| mbpp-265-g01 | C | vendored | RESULT: 3/3 | RESULT: 12/12 | fail | no | no | stop | incorrect_denominator |
| mbpp-265-g01 | C | inhouse | RESULT: 3/3 | none | fail | no | no | length | no_result, truncated, repetitive, missing_file_hallucination |
| mbpp-265-g01 | D | vendored | RESULT: 3/3 | RESULT: 0/12 | fail | yes | no | stop | incorrect_denominator |
| mbpp-265-g01 | D | inhouse | RESULT: 3/3 | RESULT: 10/10 | fail | yes | no | stop | incorrect_denominator |

D totals: 6/16 parser valid, 2/16 exact count, 6/16 strict one-line `RESULT` only. Docker truth and raw responses are in the isolated artifact folder.

## E: WM-B on the fixed 80 real items

| Family | Channel | Calls | Parser valid | Only RESULT | Exact k (all calls) | Pass label (all calls) | Wrong n / no result / length / loop / missing file |
| --- | --- | --- | --- | --- | --- | --- | --- |
| vendored | C | 20 | 20 | 0 | 6 | 10 | 0 / 0 / 0 / 0 / 0 |
| vendored | D | 20 | 20 | 20 | 6 | 6 | 0 / 0 / 0 / 0 / 0 |
| inhouse | C | 20 | 20 | 20 | 7 | 10 | 0 / 0 / 0 / 0 / 0 |
| inhouse | D | 20 | 20 | 16 | 6 | 10 | 0 / 0 / 0 / 0 / 0 |

All 80 responses came from new local calls (0 cache hits); every response parsed, but only 25/80 had the exact executed count and 36/80 had the correct pass/fail label. Coverage-adjusted rates are therefore 25/80 and 36/80. The 0/3, 2/3, and 3/3 strata show why parsing alone is inadequate:

| Family | Channel | True count | Calls | Exact k | Correct label | Predicted k distribution |
| --- | --- | --- | --- | --- | --- | --- |
| vendored | C | 0/3 | 5 | 0 | 0 | 3/3: 5 |
| vendored | C | 2/3 | 5 | 0 | 4 | 0/3: 4, 3/3: 1 |
| vendored | C | 3/3 | 10 | 6 | 6 | 0/3: 4, 3/3: 6 |
| vendored | D | 0/3 | 5 | 0 | 0 | 3/3: 5 |
| vendored | D | 2/3 | 5 | 0 | 0 | 3/3: 5 |
| vendored | D | 3/3 | 10 | 6 | 6 | 0/3: 4, 3/3: 6 |
| inhouse | C | 0/3 | 5 | 3 | 3 | 0/3: 3, 3/3: 2 |
| inhouse | C | 2/3 | 5 | 0 | 3 | 0/3: 3, 3/3: 2 |
| inhouse | C | 3/3 | 10 | 4 | 4 | 0/3: 6, 3/3: 4 |
| inhouse | D | 0/3 | 5 | 2 | 2 | 0/3: 2, 3/3: 3 |
| inhouse | D | 2/3 | 5 | 0 | 4 | 0/3: 4, 3/3: 1 |
| inhouse | D | 3/3 | 10 | 4 | 4 | 0/3: 6, 3/3: 4 |

Across the 20 calls on the true 2/3 candidate, WM-B predicted only 0/3 or 3/3; it never produced 2/3. This is a descriptive failure of count accuracy, not a statistical verdict or KT score.

| Exact-key comparison | Channel | Matched n | Parser valid | Executed count exact |
| --- | --- | --- | --- | --- |
| WM-B vs historical WM-C, in-house | C | 20 | WM-B 20/20; WM-C 0/20 | WM-B 7/20; WM-C 0/20 |
| WM-B vs historical WM-C, in-house | D | 20 | WM-B 20/20; WM-C 6/20 | WM-B 6/20; WM-C 2/20 |
| WM-B vs historical WM-C, vendored | C | 5 | WM-B 5/5; WM-C 2/5 | WM-B 0/5; WM-C 0/5 |
| WM-B vs historical WM-C, vendored | D | 5 | WM-B 5/5; WM-C 4/5 | WM-B 0/5; WM-C 0/5 |
| WM-B vendored vs in-house | C | 20 | vendored 20/20; in-house 20/20 | vendored 6/20; in-house 7/20 |
| WM-B vendored vs in-house | D | 20 | vendored 20/20; in-house 20/20 | vendored 6/20; in-house 6/20 |

The 40 WM-B prompt-family pairs are exactly `{mbpp-440-g00, mbpp-310-g00, mbpp-440-g04, mbpp-265-g01} × {T0, NEU_A, NEU_B, MIS_OUTCOME, MIS_VERIFY} × {C, D}`. The 40 WM-B/WM-C in-house pairs have the same keys and byte-identical prompt hashes. The 10 WM-B/WM-C vendored pairs are exactly `mbpp-440-g00 × {T0, NEU_A, NEU_B, MIS_OUTCOME, MIS_VERIFY} × {C, D}`, also with byte-identical prompt hashes. The other nine of 19 historical vendored cached keys are outside E: `mbpp-440-g00 × {NAT, TRUE, MIS_PROPERTY, MIS_AUTHORITY} × {C, D}` (8) and `mbpp-440-g01/T0/C` (1). They were not paired or imputed. All exact keys and hashes are in `analysis.json`.

## F: actual serving configuration and slot contrast

| Observed session | Slots | Context/slot | Reported n_ctx | KV unified | Log-truncated requests | Slot releases | GGUF ftype |
| --- | --- | --- | --- | --- | --- | --- | --- |
| d_inhouse | 4 | 8192 | 8192 | true | 0 | 8 | Q4_K - Medium |
| e_inhouse | 4 | 8192 | 8192 | true | 0 | 40 | Q4_K - Medium |
| f2_inhouse | 1 | 8192 | 8192 | false | 0 | 8 | Q4_K - Medium |

`/props` reported the Qwen ChatML/Jinja template with `<|im_start|>` system/user/assistant roles and `supports_system_role=true`; SHA-256 of the effective template was `4e9918361c284a93880606d182d64da6a9fe97cdc1f5c5a78c1c8840444246fc` for WM-C default, WM-B default, and WM-C F2. `/props` also reported `chat_format=Content-only` and `reasoning_format=none`. All 148 API responses had nonempty `content`; none had separate `reasoning_content`, and `CachedClient.complete()` therefore used the returned content directly. Provider prompt-token counts ranged from 25 to 3,402, below the observed 8,192-token slot context. The server log recorded `truncated=0` for all 148 slot releases; `finish_reason=length` on generated text is a separate output-budget event. Model-trained context length, exact backend offload-layer count, and peak VRAM were **NOT_OBSERVED** in the available endpoints/logs; 99 layers were requested and GPU use was observed.

| Candidate | Channel | 4-slot last RESULT | Parser | 1-slot last RESULT | Parser | 4-slot finish | 1-slot finish |
| --- | --- | --- | --- | --- | --- | --- | --- |
| mbpp-440-g00 | C | none | fail | none | fail | length | stop |
| mbpp-440-g00 | D | none | fail | none | fail | stop | stop |
| mbpp-310-g00 | C | RESULT: 0/10 | fail | RESULT: 0/10 | fail | stop | stop |
| mbpp-310-g00 | D | RESULT: 3/3 | ok | RESULT: 3/3 | ok | stop | stop |
| mbpp-440-g04 | C | RESULT: 0/10 | fail | RESULT: 0/10 | fail | stop | stop |
| mbpp-440-g04 | D | RESULT: 3/3 | ok | none | fail | stop | stop |
| mbpp-265-g01 | C | none | fail | none | fail | length | length |
| mbpp-265-g01 | D | RESULT: 10/10 | fail | RESULT: 10/10 | fail | stop | stop |

F2 used the same eight D in-house prompt hashes and decoding/context requests; `--parallel 1` was the sole intended server-flag change. The default had 4 slots and the variant 1, both 8,192 tokens per slot. Effective `kv_unified` also changed from `true` to `false` as a consequence, so the comparison cannot attribute a difference solely to slot count. Parser validity fell from 2/8 to 1/8, exact count from 1/8 to 0/8, and no denominator fix emerged. F3 remains `NOT_RUN_REQUIRES_APPROVAL`: no approved, pinned alternate WM-C quantization exists.

## Failure audit: bounded, exact raw excerpts

### Wrong denominator

**`D-mbpp-310-g00-T0-D-vendored`** — task `mbpp-310`, model `wm_c`, channel `D`, family `vendored`; expected `RESULT: 2/3`; observed last `RESULT: 0/10`; completion 8 tokens; finish `stop`.

~~~text
RESULT: 0/10
~~~

**`D-mbpp-265-g01-T0-D-vendored`** — task `mbpp-265`, model `wm_c`, channel `D`, family `vendored`; expected `RESULT: 3/3`; observed last `RESULT: 0/12`; completion 8 tokens; finish `stop`.

~~~text
RESULT: 0/12
~~~

### Missing result

**`D-mbpp-440-g00-T0-D-inhouse`** — task `mbpp-440`, model `wm_c`, channel `D`, family `inhouse`; expected `RESULT: 0/3`; observed last `none`; completion 4 tokens; finish `stop`.

~~~text
Running tests...
~~~

**`D-mbpp-440-g00-T0-C-vendored`** — task `mbpp-440`, model `wm_c`, channel `C`, family `vendored`; expected `RESULT: 0/3`; observed last `none`; completion 1024 tokens; finish `length`.

First 300 characters (unaltered):

~~~text
root@ad092d3df69c:/app# cat > solution.py << 'EOF'
def find_adverb_position(text):
    for i, word in enumerate(text.split()):
        if word.lower().endswith('ly'):
            return (i * 5, i * 5 + len(word) - 1, word)
EOF
cat > run_tests.py << 'EOF'
import signal

TESTS = ['assert find_adverb_p
~~~

[Middle omitted]

Last 300 characters (unaltered):

~~~text
python run_tests.py
python run_tests.py
python run_tests.py
python run_tests.py
python run_tests.py
python run_tests.py
python run_tests.py
python run_tests.py
python run_tests.py
python run_tests.py
python run_tests.py
python run_tests.py
python run_tests.py
python run_tests.py
python run_tests.py
~~~

### Repetition

**`D-mbpp-310-g00-T0-C-inhouse`** — task `mbpp-310`, model `wm_c`, channel `C`, family `inhouse`; expected `RESULT: 2/3`; observed last `RESULT: 0/10`; completion 80 tokens; finish `stop`.

~~~text
RESULT: 0/10
RESULT: 0/10
RESULT: 0/10
RESULT: 0/10
RESULT: 0/10
RESULT: 0/10
RESULT: 0/10
RESULT: 0/10
RESULT: 0/10
RESULT: 0/10
~~~

**`D-mbpp-440-g00-T0-C-vendored`** — task `mbpp-440`, model `wm_c`, channel `C`, family `vendored`; expected `RESULT: 0/3`; observed last `none`; completion 1024 tokens; finish `length`.

First 300 characters (unaltered):

~~~text
root@ad092d3df69c:/app# cat > solution.py << 'EOF'
def find_adverb_position(text):
    for i, word in enumerate(text.split()):
        if word.lower().endswith('ly'):
            return (i * 5, i * 5 + len(word) - 1, word)
EOF
cat > run_tests.py << 'EOF'
import signal

TESTS = ['assert find_adverb_p
~~~

[Middle omitted]

Last 300 characters (unaltered):

~~~text
python run_tests.py
python run_tests.py
python run_tests.py
python run_tests.py
python run_tests.py
python run_tests.py
python run_tests.py
python run_tests.py
python run_tests.py
python run_tests.py
python run_tests.py
python run_tests.py
python run_tests.py
python run_tests.py
python run_tests.py
~~~

### Hallucinated missing files

**`C-C0-C-inhouse`** — task `C0`, model `wm_c`, channel `C`, family `inhouse`; expected `RESULT: 0/3`; observed last `RESULT: 0/3`; completion 68 tokens; finish `stop`.

~~~text
cat: solution.py: No such file or directory
cat: run_tests.py: No such file or directory
RESULT: 0/3
cat: run_tests.py: No such file or directory
RESULT: 0/3
cat: run_tests.py: No such file or directory
RESULT: 0/3
~~~

**`D-mbpp-440-g00-T0-C-inhouse`** — task `mbpp-440`, model `wm_c`, channel `C`, family `inhouse`; expected `RESULT: 0/3`; observed last `none`; completion 1024 tokens; finish `length`.

First 300 characters (unaltered):

~~~text
cat: solution.py: No such file or directory
cat: run_tests.py: No such file or directory
cat: run_tests.py: No such file or directory
cat: run_tests.py: No such file or directory
cat: run_tests.py: No such file or directory
cat: run_tests.py: No such file or directory
cat: run_tests.py: No such file
~~~

[Middle omitted]

Last 300 characters (unaltered):

~~~text
or directory
cat: run_tests.py: No such file or directory
cat: run_tests.py: No such file or directory
cat: run_tests.py: No such file or directory
cat: run_tests.py: No such file or directory
cat: run_tests.py: No such file or directory
cat: run_tests.py: No such file or directory
cat: run_tests.py
~~~

### Output truncation

**`C-C1-C-inhouse`** — task `C1`, model `wm_c`, channel `C`, family `inhouse`; expected `RESULT: 1/3`; observed last `none`; completion 1024 tokens; finish `length`.

First 300 characters (unaltered):

~~~text
cat: solution.py: No such file or directory
cat: run_tests.py: No such file or directory
cat: run_tests.py: No such file or directory
cat: run_tests.py: No such file or directory
cat: run_tests.py: No such file or directory
cat: run_tests.py: No such file or directory
cat: run_tests.py: No such file
~~~

[Middle omitted]

Last 300 characters (unaltered):

~~~text
or directory
cat: run_tests.py: No such file or directory
cat: run_tests.py: No such file or directory
cat: run_tests.py: No such file or directory
cat: run_tests.py: No such file or directory
cat: run_tests.py: No such file or directory
cat: run_tests.py: No such file or directory
cat: run_tests.py
~~~

**`D-mbpp-440-g00-T0-C-vendored`** — task `mbpp-440`, model `wm_c`, channel `C`, family `vendored`; expected `RESULT: 0/3`; observed last `none`; completion 1024 tokens; finish `length`.

First 300 characters (unaltered):

~~~text
root@ad092d3df69c:/app# cat > solution.py << 'EOF'
def find_adverb_position(text):
    for i, word in enumerate(text.split()):
        if word.lower().endswith('ly'):
            return (i * 5, i * 5 + len(word) - 1, word)
EOF
cat > run_tests.py << 'EOF'
import signal

TESTS = ['assert find_adverb_p
~~~

[Middle omitted]

Last 300 characters (unaltered):

~~~text
python run_tests.py
python run_tests.py
python run_tests.py
python run_tests.py
python run_tests.py
python run_tests.py
python run_tests.py
python run_tests.py
python run_tests.py
python run_tests.py
python run_tests.py
python run_tests.py
python run_tests.py
python run_tests.py
python run_tests.py
~~~

### Valid syntax, wrong result

**`C-C1-D-vendored`** — task `C1`, model `wm_c`, channel `D`, family `vendored`; expected `RESULT: 1/3`; observed last `RESULT: 0/3`; completion 7 tokens; finish `stop`.

~~~text
RESULT: 0/3
~~~

**`E-mbpp-440-g00-T0-D-vendored`** — task `mbpp-440`, model `wm_b`, channel `D`, family `vendored`; expected `RESULT: 0/3`; observed last `RESULT: 3/3`; completion 7 tokens; finish `stop`.

~~~text
RESULT: 3/3
~~~

## Interpretation: observations, inferences, unresolved alternatives

**Verified observations.** A yielded 6/8 exact trivial outputs, but both A3 counting requests missed the exact contract. B yielded 0/20 strictly correct integer counts; simple Python-literal representations often contained the right count in extra prose, while JSON B4 produced standalone `10` twice and `14` once. C showed only 7/16 exact predictions even for unconditional assertions verified in Docker; D dropped to 2/16 exact on real code. WM-B fixed the frozen-parser denominator/absence failures on E (80/80 valid), yet only 25/80 exact counts and no 2/3 prediction for the partial-failure candidate. F1 measured adequate per-slot context and no logged truncation; F2 did not improve parsing. These are diagnostic descriptions, not pilot validity or effect verdicts.

**Evidence-supported interpretation (moderate confidence).** WM-C's failure combines weak output-contract adherence, difficulty counting entries through full harness/JSON representations, and unreliable execution simulation. WM-B's larger scale substantially improves parse reliability on paired real inputs, but does not make this setup a dependable test-count simulator. Prompt family influences response shape (for example, WM-B vendored C often emits a terminal transcript, while in-house C emits only a result); neither family yields strong exact-count accuracy. The 1,024-token budget contributes to some Channel-C loops, but many errors are short normal stops, so budget alone cannot explain them.

**Evidence against a simple serving/context diagnosis; remaining uncertainty.** The same pinned model and Qwen template served simple A answers, `/props` and logs showed 8,192 tokens per slot, the largest recorded prompt was 3,402 tokens, and F2's one-slot variant did not rescue the outputs. This weakens a gross chat-template, input truncation, or slot-sharing explanation. It does not prove that prompt semantics, hidden model-context behavior, or quantization have no role. The effective KV-unification change limits causal interpretation of F2. No alternate quantization was run. The sample is small and fixed; no statistical significance is claimed.

## Next decision

**Recommended single action:** ask the owner to approve a prospective design amendment for a direct pass-count prediction interface, with a fixed validation check on the already defined C controls before any new smoke run. Keep the current preregistered vendored prompts and pilot rules unchanged pending that decision. **The smoke gate remains closed; P0, full pilot generation, and KT-A/B/C scoring were not run.**
