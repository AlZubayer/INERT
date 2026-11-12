# Direct Pass-Count Diagnostic — 2026-11-12

## Finding

All 16 prospectively fixed local calls completed. Both models returned exactly one parser-valid `RESULT: k/n` line on every call, with the correct denominator. WM-B matched the Docker pass count on 8/8; WM-C matched on 6/8, missing C1 under both interfaces. Supplying the denominator changed no prediction. These simple assertions show that the direct interface can avoid the earlier format and denominator failures, but they do not establish reliability on MBPP or identify the terminal/tool interface as the sole cause of the earlier errors. The official smoke gate remains closed.

## Provenance and fixed inputs

The branch was `pilot/steps-0-1`; the verified starting commit was `800da3c921cbed82488b3b945c4891d63a2ca05e`. This diagnostic is isolated under ignored `data/smoke/diagnostics/direct_pass_count_20261112/`. Its complete manifest, fixed before inference, has SHA-256 `77f74e1283ff10236e71beb8e1c3c0d7f8ac929312cabee5b45a32c8b7c4b5d9`. The prior Stage-C manifest and Docker-truth files have SHA-256 `189f19108db6a2d766cb22cdf4931c52495b0839b54a6f864485d13f10581188` and `d4578f2058a7c1a25df00024e3e19fe9ffe8e983e5f87c7972508a0f18f75b5c`. The new runner checked each source, assertion list, harness hash, and expected Docker output against those fixed files before inference; no experimental code ran on the host.

| Model | Pinned source / GGUF revision | Verified Q4_K_M weight SHA-256 |
| --- | --- | --- |
| WM-C: `Qwen/Qwen2.5-1.5B-Instruct` | `989aa7980e4cf806f80c7fef2b1adb7bc71aa306` / `91cad51170dc346986eccefdc2dd33a9da36ead9` | `6a1a2eb6d15622bf3c96857206351ba97e1af16c30d7a74ee38970e434e9407e` |
| WM-B: `Qwen/Qwen2.5-7B-Instruct` | `a09a35458c702b33eeacc393d103063234e8bc28` / `bb5d59e06d9551d752d08b292a50eb208b07ab1f` | shard 1 `dfce12e3862a5283ccfb88221b48480e58745165de856439950d0f22590580db`; shard 2 `539cf93f78e887edea1c04e2d7d8cdaca9d01dae9c9025bcb8accbe29df3d72a` |

Both model licenses are recorded as Apache-2.0 in `configs/models.yaml`. The local `llama-server.exe` was build `b12110`, commit `cd959bae9`, executable SHA-256 `00d50686815af38249d0218c91558fbd0e9093ac8c074bac86196907f4305e31`. Sampling was temperature `0.0`, top-p `1.0`, maximum completion tokens `1024`, seed `0`, requested context `8192`; server settings and Q4_K_M quantization were unchanged. Servers ran sequentially, one model on the GPU at a time. All 16 response records have `cache_hit=false` and retain the original API body in separate model caches and response files.

## Method

Each prompt contained the same complete `solution.py` code (`def f(x):` followed by `return x`) and the same numbered assertions under both interfaces. C0 was three `assert False` assertions; C1 was `assert True`, `assert False`, `assert False`; C2 was `assert True`, `assert True`, `assert False`; C3 was three `assert True` assertions. Previous Docker-sandbox results were respectively `RESULT: 0/3`, `1/3`, `2/3`, and `3/3`.

Both interfaces used the same system message: “You predict the outcome of Python assertions by analyzing the supplied code. Do not execute any code or explain your reasoning. Return only the requested RESULT line.” Only the final user instruction differed:

> **DIRECT_COUNT:** Determine the number of passing tests and total tests from the provided code and assertions. Output exactly one line in the format RESULT: k/n, where k is the passing count and n is the total test count.

> **FIXED_DENOMINATOR:** There are exactly 3 tests. Determine how many of them pass. Output exactly one line in the format RESULT: k/3, where k is the passing count. Do not output any explanation.

The first interface did not explicitly state the denominator. Neither interface supplied the expected passing count. Strict format means the entire trimmed response matches one `RESULT: k/n` line. Parser validity uses the unchanged frozen pilot parser, which permits surrounding text but rejects an incorrect denominator or out-of-range count. An invalid response would count as incorrect in coverage-adjusted accuracy.

## Complete response matrix

Every quoted raw response below is the entire model output, not a cleaned excerpt. Token counts are prompt/completion. `yes` in the exact column means the predicted pass count matches the Docker result; all outputs have finish reason `stop`.

| Model | Case | Interface | Docker expected | Raw model output | Parsed result | Strict | Parser | Exact | Tokens | Finish |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| WM-C | C0 | DIRECT_COUNT | `RESULT: 0/3` | `RESULT: 0/3` | `RESULT: 0/3` | yes | ok | yes | 120/7 | stop |
| WM-C | C0 | FIXED_DENOMINATOR | `RESULT: 0/3` | `RESULT: 0/3` | `RESULT: 0/3` | yes | ok | yes | 117/7 | stop |
| WM-C | C1 | DIRECT_COUNT | `RESULT: 1/3` | `RESULT: 0/3` | `RESULT: 0/3` | yes | ok | **no** | 120/7 | stop |
| WM-C | C1 | FIXED_DENOMINATOR | `RESULT: 1/3` | `RESULT: 0/3` | `RESULT: 0/3` | yes | ok | **no** | 117/7 | stop |
| WM-C | C2 | DIRECT_COUNT | `RESULT: 2/3` | `RESULT: 2/3` | `RESULT: 2/3` | yes | ok | yes | 120/7 | stop |
| WM-C | C2 | FIXED_DENOMINATOR | `RESULT: 2/3` | `RESULT: 2/3` | `RESULT: 2/3` | yes | ok | yes | 117/7 | stop |
| WM-C | C3 | DIRECT_COUNT | `RESULT: 3/3` | `RESULT: 3/3` | `RESULT: 3/3` | yes | ok | yes | 120/7 | stop |
| WM-C | C3 | FIXED_DENOMINATOR | `RESULT: 3/3` | `RESULT: 3/3` | `RESULT: 3/3` | yes | ok | yes | 117/7 | stop |
| WM-B | C0 | DIRECT_COUNT | `RESULT: 0/3` | `RESULT: 0/3` | `RESULT: 0/3` | yes | ok | yes | 120/7 | stop |
| WM-B | C0 | FIXED_DENOMINATOR | `RESULT: 0/3` | `RESULT: 0/3` | `RESULT: 0/3` | yes | ok | yes | 117/7 | stop |
| WM-B | C1 | DIRECT_COUNT | `RESULT: 1/3` | `RESULT: 1/3` | `RESULT: 1/3` | yes | ok | yes | 120/7 | stop |
| WM-B | C1 | FIXED_DENOMINATOR | `RESULT: 1/3` | `RESULT: 1/3` | `RESULT: 1/3` | yes | ok | yes | 117/7 | stop |
| WM-B | C2 | DIRECT_COUNT | `RESULT: 2/3` | `RESULT: 2/3` | `RESULT: 2/3` | yes | ok | yes | 120/7 | stop |
| WM-B | C2 | FIXED_DENOMINATOR | `RESULT: 2/3` | `RESULT: 2/3` | `RESULT: 2/3` | yes | ok | yes | 117/7 | stop |
| WM-B | C3 | DIRECT_COUNT | `RESULT: 3/3` | `RESULT: 3/3` | `RESULT: 3/3` | yes | ok | yes | 120/7 | stop |
| WM-B | C3 | FIXED_DENOMINATOR | `RESULT: 3/3` | `RESULT: 3/3` | `RESULT: 3/3` | yes | ok | yes | 117/7 | stop |

## Aggregates and paired effects

| Group | Calls | Strict | Parser valid | Denominator correct | Exact count | Pass/fail label | Wrong denominator | Commentary/repetition |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| WM-C | 8 | 8/8 | 8/8 | 8/8 | 6/8 | 8/8 | 0/8 | 0/8 |
| WM-B | 8 | 8/8 | 8/8 | 8/8 | 8/8 | 8/8 | 0/8 | 0/8 |
| DIRECT_COUNT | 8 | 8/8 | 8/8 | 8/8 | 7/8 | 8/8 | 0/8 | 0/8 |
| FIXED_DENOMINATOR | 8 | 8/8 | 8/8 | 8/8 | 7/8 | 8/8 | 0/8 | 0/8 |
| All | 16 | 16/16 | 16/16 | 16/16 | 14/16 | 16/16 | 0/16 | 0/16 |

These exact-count and label rates include every assigned call as the denominator. The predicted-count distribution was WM-C: `0` four times, `1` zero, `2` twice, `3` twice; WM-B: each of `0`, `1`, `2`, and `3` twice. Each paired interface outcome was identical for the same model and control: no parsing gain, no denominator gain, and no passing-count gain from explicitly supplying `3`. WM-B predicted both partial-pass controls C1 and C2 correctly under both interfaces. WM-C predicted C2 correctly and C1 incorrectly under both. The sole errors had a correct denominator and wrong pass count; there were no nonparseable, truncated, empty, repeated, or commentary outputs.

## Relation to the previous Stage-C diagnostic

The [previous Stage-C results](WM_Failure_Isolation_Results_20261112.md) used the identical fixed source and assertions but different terminal/tool-simulation prompts, two prompt families, and Channels C and D. WM-C then had 13/16 parser-valid outputs, 4/16 strict one-line outputs, and 7/16 exact counts. On C1 all four previous outputs were wrong or unparseable; on C2 all four were wrong or unparseable. The new direct WM-C calls were 8/8 parser-valid and strict, 6/8 exact, including 2/2 correct C2 predictions and 0/2 correct C1 predictions. These denominators and input interfaces differ; the comparison is descriptive and is not a causal estimate of a single interface component. WM-B had no previous synthetic Stage-C calls, so its 8/8 direct result has no matched historical synthetic baseline. Earlier WM-B real-item Stage E calls were parser-valid 80/80 but exact only 25/80, with no correct 2/3 predictions on the partial candidate; those are different, harder tasks.

## Error evidence and interpretation

The complete two WM-C errors were `RESULT: 0/3` on C1, while the preserved Docker output was `RESULT: 1/3`. Both had seven completion tokens and normal `stop` finishes. This rules out truncation and denominator mismatch for these two errors. Because C1 contains one `assert True` and two `assert False`, the wrong `0` is consistent with a failure to count passing assertions or with treating any failure as a zero-pass suite. The response alone cannot distinguish those mechanisms. Correct C2 answers show that neither model was restricted to only `0/3` and `3/3` under the direct interface. The simple unconditional assertions are much easier than real MBPP candidates; success here cannot validate full execution reasoning or open the frozen smoke gate.

## Recommended next action

Keep the smoke gate closed and seek owner approval for one preregistered, Docker-verified direct-interface diagnostic on a small set of nontrivial real candidates, with the same fixed model settings and separate evidence. That would test whether the direct interface's formatting gains persist when pass counts require interpreting actual candidate behavior, before any proposal to amend the primary interface or resume pilot stages.
