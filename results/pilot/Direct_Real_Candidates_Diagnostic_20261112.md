# Direct pass-count diagnostic on real MBPP candidates — 2026-11-12

## Executive finding

**COMPLETE: 16/16 fixed local model calls and 4/4 independent Docker checks.** The direct interface made responses concise: 16/16 were strict one-line `RESULT` outputs and 15/16 passed the frozen parser. It did not make pass-count prediction reliable on these real programs. WM-C was exact on 3/8 calls and WM-B on 4/8. Both models missed the informative `mbpp-310-g00` 2/3 candidate under both direct interfaces. These are observations on four selected candidates; the role of the interface versus reasoning ability remains uncertain. This diagnostic does not amend the registered experiment, and the original smoke gate remains closed.

## Methods and provenance

The verified starting commit was `8e4d8f73c3696abf176c326104b4201efa841310` on `pilot/steps-0-1`. Artifacts are isolated under ignored `data/smoke/diagnostics/direct_real_candidates_20261112/`: the fixed 16-case manifest, exact messages and input SHA-256 hashes, four new Docker responses, 16 original API bodies and completion records, separate WM-C/WM-B SQLite caches, and `analysis.json`. The manifest was saved **before** inference; SHA-256 `3ffba5941fdb81138e1d202df2860c3f569e28f4868ecd80cf1bfce35f1579d8`. Docker verification file SHA-256: `db0b534449e4c3cbb1d5a12a36c5c34f328f6ef01affb3b95875866ac2f8a310`. The runner checked every candidate, test list, historical Stage-D/E T0 input, and prior direct-interface template before creating the new manifest. All 16 model responses were new cache misses.

The prompts reused the exact system instruction and final DIRECT_COUNT/FIXED_DENOMINATOR instructions from the [synthetic direct diagnostic](Direct_Pass_Count_Diagnostic_20261112.md), by substituting only `solution.py` and its numbered assertions into those frozen message templates. Both interfaces received identical executable code and tests for each candidate; only the final instruction differed. DIRECT_COUNT asked the model to determine `k` and `n`; FIXED_DENOMINATOR supplied `n=3` but did not supply `k`. There were no examples, agent Thoughts, misleading text, condition changes, or execution results in the prompts. Every item was neutral `T0`.

| Candidate | Docker truth | `code_stripped` SHA-256 | Original test-list SHA-256 | Harness SHA-256 |
| --- | --- | --- | --- | --- |
| `mbpp-440-g00` | `0/3` | `ee012ee6fcc51ddeaae1ffba4c85b3e8cea46418d9868177526e102b24035cda` | `3db7b11e18a5151a0debf7a549b7c048197f1cb851a4b852c46f713ea68eeeda` | `fd1d78c9f3e30e83b8d4c2bc9b1e77dffc934d79deb20569947826a742970592` |
| `mbpp-310-g00` | `2/3` | `2d696f5aa8e3d32568d858c37e11c2ce5d98f480f0356c6fdecefc4f23044fc6` | `c356b4f11d45ef061b83c1c613ae0367c2181719fd25229d13b37a972b95e6df` | `dac4b886e9ec7b2fb3fc1a693a83e4ffdd01952399fc76f21f04794276d52055` |
| `mbpp-440-g04` | `3/3` | `1951085c60d9382e1475ae3fa960454659992ee55383d9c0e4901a045af402ae` | `3db7b11e18a5151a0debf7a549b7c048197f1cb851a4b852c46f713ea68eeeda` | `fd1d78c9f3e30e83b8d4c2bc9b1e77dffc934d79deb20569947826a742970592` |
| `mbpp-265-g01` | `3/3` | `bf1ed438abcdc7391ea8d5e80abe55cf8b1aafef926c108ba8f5fc2c17644546` | `54f9ae1483cc01bd823d479b30a264ff100f77152d1dbcf6e04b648661e185a0` | `f46b61326dcd7410213faac4da250255790e82b5054d82ae6e05594d7e3eccd0` |

Test-list hashes are SHA-256 of UTF-8 JSON arrays of the original three assertion strings. The Docker checks used `DockerSandbox` with networking disabled, the unchanged harness, and no host execution of candidate code. The four Docker outputs matched the prior recorded outputs byte for byte.

| Role | Pinned model, Q4_K_M | Verified weight SHA-256 |
| --- | --- | --- |
| WM-C | `Qwen/Qwen2.5-1.5B-Instruct`; source revision `989aa7980e4cf806f80c7fef2b1adb7bc71aa306`; GGUF revision `91cad51170dc346986eccefdc2dd33a9da36ead9` | `6a1a2eb6d15622bf3c96857206351ba97e1af16c30d7a74ee38970e434e9407e` |
| WM-B | `Qwen/Qwen2.5-7B-Instruct`; source revision `a09a35458c702b33eeacc393d103063234e8bc28`; GGUF revision `bb5d59e06d9551d752d08b292a50eb208b07ab1f` | shard 1 `dfce12e3862a5283ccfb88221b48480e58745165de856439950d0f22590580db`; shard 2 `539cf93f78e887edea1c04e2d7d8cdaca9d01dae9c9025bcb8accbe29df3d72a` |

Both licenses are recorded as Apache-2.0 in `configs/models.yaml`. Local llama.cpp server build `b12110`, commit `cd959bae9`, executable SHA-256 `00d50686815af38249d0218c91558fbd0e9093ac8c074bac86196907f4305e31`. The verified request settings were temperature `0.0`, top-p `1.0`, maximum completion tokens `1024`, seed `0`, requested context `8192`. Model servers ran sequentially. Source provenance hashes in the manifest include the smoke tasks and candidates files and both previous diagnostic records. No hosted inference was used.

## Complete 16-call result matrix

The raw output column is each **entire** model response. `P/C` is prompt/completion tokens. Strict means exactly one `RESULT: k/n` line; parser validity uses unchanged design §9.5. Exact and label correctness count invalid outputs as incorrect.

| Model | Candidate | Interface | Docker | Exact raw output | Parsed | Strict | Parser | Exact | Label | P/C | Finish |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| WM-C | `440-g00` | DIRECT_COUNT | `0/3` | `RESULT: 3/3` | `3/3` | yes | ok | no | no | 228/7 | stop |
| WM-C | `440-g00` | FIXED_DENOMINATOR | `0/3` | `RESULT: 3/3` | `3/3` | yes | ok | no | no | 225/7 | stop |
| WM-B | `440-g00` | DIRECT_COUNT | `0/3` | `RESULT: 3/3` | `3/3` | yes | ok | no | no | 228/7 | stop |
| WM-B | `440-g00` | FIXED_DENOMINATOR | `0/3` | `RESULT: 3/3` | `3/3` | yes | ok | no | no | 225/7 | stop |
| WM-C | `310-g00` | DIRECT_COUNT | `2/3` | `RESULT: 3/3` | `3/3` | yes | ok | no | no | 197/7 | stop |
| WM-C | `310-g00` | FIXED_DENOMINATOR | `2/3` | `RESULT: 3/3` | `3/3` | yes | ok | no | no | 194/7 | stop |
| WM-B | `310-g00` | DIRECT_COUNT | `2/3` | `RESULT: 0/3` | `0/3` | yes | ok | no | yes | 197/7 | stop |
| WM-B | `310-g00` | FIXED_DENOMINATOR | `2/3` | `RESULT: 0/3` | `0/3` | yes | ok | no | yes | 194/7 | stop |
| WM-C | `440-g04` | DIRECT_COUNT | `3/3` | `RESULT: 3/3` | `3/3` | yes | ok | yes | yes | 217/7 | stop |
| WM-C | `440-g04` | FIXED_DENOMINATOR | `3/3` | `RESULT: 3/3` | `3/3` | yes | ok | yes | yes | 214/7 | stop |
| WM-B | `440-g04` | DIRECT_COUNT | `3/3` | `RESULT: 3/3` | `3/3` | yes | ok | yes | yes | 217/7 | stop |
| WM-B | `440-g04` | FIXED_DENOMINATOR | `3/3` | `RESULT: 3/3` | `3/3` | yes | ok | yes | yes | 214/7 | stop |
| WM-C | `265-g01` | DIRECT_COUNT | `3/3` | `RESULT: 3/6` | `3/6` (rejected) | yes | fail | no | no | 329/7 | stop |
| WM-C | `265-g01` | FIXED_DENOMINATOR | `3/3` | `RESULT: 3/3` | `3/3` | yes | ok | yes | yes | 326/7 | stop |
| WM-B | `265-g01` | DIRECT_COUNT | `3/3` | `RESULT: 3/3` | `3/3` | yes | ok | yes | yes | 329/7 | stop |
| WM-B | `265-g01` | FIXED_DENOMINATOR | `3/3` | `RESULT: 3/3` | `3/3` | yes | ok | yes | yes | 326/7 | stop |

Candidate labels in this table abbreviate the `mbpp-` prefix only; the exact IDs are above and in the manifest. `3/6 (rejected)` identifies the last observed `RESULT`, not an accepted parsed prediction: the frozen parser returned `parse_status=fail`, `k_pred=3`, `n_pred=6`, and no `R_sim`.

## Aggregate results and paired interface effects

| Model / interface | Calls | Strict | Parser valid | Correct denominator | Exact count | Correct pass/fail label | Wrong denominator | No result / repetition / truncation |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| WM-C / DIRECT_COUNT | 4 | 4/4 (100%) | 3/4 (75%) | 3/4 (75%) | 1/4 (25%) | 1/4 (25%) | 1/4 (25%) | 0/4 each |
| WM-C / FIXED_DENOMINATOR | 4 | 4/4 (100%) | 4/4 (100%) | 4/4 (100%) | 2/4 (50%) | 2/4 (50%) | 0/4 (0%) | 0/4 each |
| WM-B / DIRECT_COUNT | 4 | 4/4 (100%) | 4/4 (100%) | 4/4 (100%) | 2/4 (50%) | 3/4 (75%) | 0/4 (0%) | 0/4 each |
| WM-B / FIXED_DENOMINATOR | 4 | 4/4 (100%) | 4/4 (100%) | 4/4 (100%) | 2/4 (50%) | 3/4 (75%) | 0/4 (0%) | 0/4 each |

Across both interfaces WM-C was strict 8/8, parser-valid 7/8, exact 3/8, label-correct 3/8; WM-B was strict and parser-valid 8/8, exact 4/8, label-correct 6/8. Combined exact accuracy was 7/16 (43.75%), with invalid counted as incorrect. Among the 15 parser-valid responses, 7 were exact; this conditional rate is less informative than 7/16 coverage-adjusted accuracy. Predicted `k` among accepted responses: WM-C `0`: 0, `1`: 0, `2`: 0, `3`: 7; WM-B `0`: 2, `1`: 0, `2`: 0, `3`: 6. The invalid WM-C response had observed `k=3, n=6` and is excluded from that valid-prediction distribution.

For each model/candidate pair, DIRECT_COUNT and FIXED_DENOMINATOR gave the **same passing-count numeral**. The only denominator and validity change was WM-C on `mbpp-265-g01`: `3/6` became `3/3`, making that one prediction exact. All other seven paired outcomes were identical within model. Thus explicitly supplying `3` improved WM-C parsing and exact accuracy by one of four cases, but did not improve its ability to infer any passing count. The models disagreed with each other on `mbpp-310-g00`: WM-C chose `3/3`, WM-B `0/3`, and both were wrong.

## Candidate-level findings

- `mbpp-440-g00` (Docker `0/3`): both models predicted `3/3` twice. The candidate checks whether a word **ends** in `ly`; the supplied words carry trailing punctuation. The observed error is a wrong passing count with a correct denominator and wrong pass/fail label.
- `mbpp-310-g00` (Docker `2/3`): WM-C predicted `3/3` twice and WM-B `0/3` twice. The candidate returns `tuple(str)`, which retains the space in `"python 3.0"`; the first expected tuple omits it, while the other two assertions pass. Neither model produced `2/3` under either interface. The WM-B `0/3` response had the correct **pass/fail label** while missing the fractional reward by two tests. This was the designated partial-pass check.
- `mbpp-440-g04` (Docker `3/3`): both models predicted `3/3` in both interfaces, exact.
- `mbpp-265-g01` (Docker `3/3`): WM-B was exact twice. WM-C returned `3/6` in DIRECT_COUNT and `3/3` when told there were exactly three tests. The `6` may reflect confusion with the six-element input list in the third assertion, but the raw answer does not establish the model's reasoning.

## Historical T0 terminal/tool comparison

The [failure-isolation report](WM_Failure_Isolation_Results_20261112.md) and its fixed manifest supplied **32 exactly matched T0 records**: four candidates × two channels (C terminal, D tool) × two prompt families (vendored, in-house) × two models. The new prompts used the same `code_stripped` and original tests, but changed the model-input and response interface, so the comparison is descriptive. The cells below give the **last observed `RESULT`** from each historical raw response; `none` means no result. `✓` means exact Docker count, `×` means wrong count or invalid denominator, and `—` means no parsed count. Exact historical case IDs have the form `D-<candidate>-T0-<channel>-<family>` for WM-C and `E-<candidate>-T0-<channel>-<family>` for WM-B; these IDs and their prompt hashes are saved in the new analysis.

### Historical WM-C, Stage D (`T0`)

| Candidate (Docker) | C vendored | C in-house | D vendored | D in-house | New direct WM-C |
| --- | --- | --- | --- | --- | --- |
| `440-g00` (`0/3`) | none — | none — | `3/3` × | none — | `3/3`, `3/3` × |
| `310-g00` (`2/3`) | `0/3` × | `0/10` × | `0/10` × | `3/3` × | `3/3`, `3/3` × |
| `440-g04` (`3/3`) | `0/3` × | `0/10` × | `3/3` ✓ | `3/3` ✓ | `3/3`, `3/3` ✓ |
| `265-g01` (`3/3`) | `12/12` × | none — | `0/12` × | `10/10` × | `3/6` ×, `3/3` ✓ |

Historical WM-C T0: 6/16 parser-valid, 2/16 exact. New direct: 7/8 parser-valid, 3/8 exact. The direct prompts removed historical missing-result/repetition patterns on these cases, but did not solve two of the four candidate behaviors.

### Historical WM-B, Stage E (`T0`)

| Candidate (Docker) | C vendored | C in-house | D vendored | D in-house | New direct WM-B |
| --- | --- | --- | --- | --- | --- |
| `440-g00` (`0/3`) | `3/3` × | `0/3` ✓ | `3/3` × | `0/3` ✓ | `3/3`, `3/3` × |
| `310-g00` (`2/3`) | `0/3` × | `0/3` × | `3/3` × | `0/3` × | `0/3`, `0/3` × |
| `440-g04` (`3/3`) | `3/3` ✓ | `0/3` × | `3/3` ✓ | `0/3` × | `3/3`, `3/3` ✓ |
| `265-g01` (`3/3`) | `3/3` ✓ | `3/3` ✓ | `3/3` ✓ | `3/3` ✓ | `3/3`, `3/3` ✓ |

Historical WM-B T0: 16/16 parser-valid, 8/16 exact. New direct: 8/8 parser-valid, 4/8 exact. Exact-rate improvement is therefore **not observed** for WM-B on this selected set. In the previous full five-condition Stage-E block, WM-B parsed 20/20 responses on `mbpp-310-g00` but none predicted exact `2/3`; its T0 subset here was 0/4 exact, and the new direct subset was 0/2 exact. The five-condition aggregate is not treated as a matched direct comparison.

### Raw error evidence

All new raw failures are visible verbatim in the 16-row table. In particular, the two WM-B responses to `mbpp-310-g00` were each exactly `RESULT: 0/3`, whereas Docker returned `RESULT: 2/3`; the two WM-C responses were each exactly `RESULT: 3/3`. For the failed `mbpp-440-g00`, both models returned exactly `RESULT: 3/3` in both interfaces, versus Docker `RESULT: 0/3`. The WM-C wrong denominator was exactly `RESULT: 3/6` on `mbpp-265-g01` (DIRECT_COUNT); `finish_reason=stop`, seven completion tokens. None of the 16 new responses contained a missing-file claim, commentary, repetition, or a length stop.

For historical context, exact bounded excerpts from the prior raw T0 records show interface-specific failures (middle content omitted only where stated):

| Historical case | Raw excerpt | Observation |
| --- | --- | --- |
| `D-mbpp-265-g01-T0-D-vendored` (WM-C) | `RESULT: 0/12` | Wrong denominator; three real tests. |
| `D-mbpp-310-g00-T0-C-vendored` (WM-C) | `RESULT: 0/3\nRESULT: 0/3\nRESULT: 0/3\nroot@hostname:/path# python run_tests.py\nRESULT: 0/3\nRESULT: 0/3\nRESULT:` | Tail of a 1,024-token repeated terminal completion; last valid count wrong. |
| `D-mbpp-440-g00-T0-C-vendored` (WM-C) | `python run_tests.py\npython run_tests.py\npython run_tests.py\npython run_tests.py\npython run_tests.py\n` | Tail of a 1,024-token completion with no `RESULT`; missing execution output. |
| `E-mbpp-310-g00-T0-C-vendored` (WM-B) | `root@ad092d3df69c:/app# python run_tests.py\nRESULT: 0/3\nroot@ad092d3df69c:/app#` | Tail of a normal terminal completion with a wrong count. |
| `E-mbpp-310-g00-T0-D-vendored` (WM-B) | `RESULT: 3/3` | Wrong count in the tool channel, normal stop. |

The historical excerpts identify the model, candidate, T0, channel, and family through the case IDs. `\n` in the table represents an actual newline. Longer historical raw responses, including other missing-file and truncation examples, are quoted in the failure-isolation report; the new direct run had **zero** such outputs.

## Interpretation and limits

**Simulator interface difficulty:** The new answers were all short one-line results, versus historical WM-C T0 outputs with missing results, wrong denominators, and repetitive terminal transcripts. That is evidence that the earlier interface imposed substantial output-format demands. The competing explanation is that the direct prompts themselves were simpler and more explicit; because several components changed together, this is not a controlled causal estimate of the terminal/tool interface alone.

**Execution-reasoning limits:** Both models missed the 2/3 candidate twice despite a clear direct pass-count request and correct denominator. Both also called the 0/3 candidate a full pass. These errors cannot be explained by formatting alone. WM-B's 8/8 success on trivial synthetic assertions did not generalize to this selected real set. The direct prompts omit the full harness, and the models are asked to infer its behavior from code and assertions; this remains a possible source of difficulty, not proof of an architecture-level limit.

**Both mechanisms:** The observed pattern supports a combined account: direct prompting removed many output-shape failures, while semantic pass-count errors remained. Evidence against a strong claim is the tiny, deliberately selected four-candidate set, repeated deterministic calls on each candidate under closely related instructions, and changed prompt families and channels between runs. No significance test, generalization claim, pilot validity verdict, or preregistered interface amendment follows from these diagnostics.

## Recommended next action

Keep the original smoke gate closed. The next decision should be an owner review of whether to preregister a single **real-candidate execution-reasoning control** that separates reading the assertions from predicting candidate behavior, using a fresh fixed candidate set and Docker ground truth. No primary prompt replacement, smoke rerun, P0, or pilot scoring should start from this diagnostic alone.
