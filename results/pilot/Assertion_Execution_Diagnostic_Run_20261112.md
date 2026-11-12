# Assertion-reading and execution-reasoning diagnostic — 2026-11-12

## Executive finding

**Complete: 48/48 local calls; the official smoke gate remains closed.** All eight Docker per-assertion vectors reproduced the frozen aggregate counts. The models show distinct format and reasoning failures; this diagnostic does not establish general ability from three tasks.

## Frozen selection and Docker oracle

Selection manifest SHA-256: `3aed60838f4c44dc5a8fa76b0bcf858ffb37f5d8de5c5ab8d267d0a50add37eb`. Source archive SHA-256: `e76c93a8483f370dc9d684d295264175739940355df79fbe37ceddceedd24378`. Frozen aggregate oracle SHA-256: `b180a21fe9640783f9429b2e1040a0a53b89ea7441a53610f9b9f84079d49cfe`. Per-assertion oracle SHA-256: `305c33612c6ab146c32c31d85ce27b1b776acc85c755d36f5915b3260955e3a8`. Docker image: `sha256:07d4824036af339fa1b6ef769cc99d9c10a141769538b52b3b597c84f7a7b535`. All eight source and ordered test hashes were verified before inference; eight code hashes were distinct.

| Candidate | Task | Code SHA-256 | Tests SHA-256 | Import | Docker vector | Aggregate |
|---|---|---|---|---|---|---|
| `acq-mbpp-125-g06` | `mbpp-125` | `6b3757571f7b5efe0ee048f69fd1b979b9bb53c70a1009e5c770ac7bc88908b9` | `98c21f4e2af7b1d9b4ea1906d7c1b12ebc2efab6f66bd63279e53a1ff0be75ca` | ok | F,F,F | RESULT: 0/3 |
| `acq-mbpp-125-g07` | `mbpp-125` | `8ea1c1c85d11823334a8da5d8faed35ab094a37922bd24ef1d3fb64b5572f48a` | `98c21f4e2af7b1d9b4ea1906d7c1b12ebc2efab6f66bd63279e53a1ff0be75ca` | ok | F,F,F | RESULT: 0/3 |
| `acq-mbpp-563-g00` | `mbpp-563` | `e8f3ead65e325cf638e1e9921517543211ad1e12439e6fc4e071492443102a2b` | `f1237c800a3914aa74d2e27965c499981729caabf967a8885d403b2a49687f7b` | ok | P,F,F | RESULT: 1/3 |
| `acq-mbpp-622-g00` | `mbpp-622` | `8acd39c9c90b679904b5467a2d158e76af0bc59cfba18b8ad6eccb082496b51a` | `01aae2a121fdba46ba2268c63d05bc53df39b68623d510b90fba26c5a0dccad4` | ok | P,F,F | RESULT: 1/3 |
| `acq-mbpp-563-g10` | `mbpp-563` | `a4b9e6d9d6ac5c0d969ec9d30308912c8284f14befd050834163738996a84736` | `f1237c800a3914aa74d2e27965c499981729caabf967a8885d403b2a49687f7b` | ok | F,P,P | RESULT: 2/3 |
| `acq-mbpp-563-g13` | `mbpp-563` | `5ba350bd3f2f0147da456e0b07599429f7c22174b8f2a957094aa62378a9f937` | `f1237c800a3914aa74d2e27965c499981729caabf967a8885d403b2a49687f7b` | ok | F,P,P | RESULT: 2/3 |
| `acq-mbpp-125-g00` | `mbpp-125` | `9ce029fe958c6706f24634b75ed97dd3c99c636bd729851af259da796357bccf` | `98c21f4e2af7b1d9b4ea1906d7c1b12ebc2efab6f66bd63279e53a1ff0be75ca` | ok | P,P,P | RESULT: 3/3 |
| `acq-mbpp-125-g01` | `mbpp-125` | `cfb6edee691b7fe854e3bc04b2a2abf4a0468e9a3371a662e73dc4f0cca40ca5` | `98c21f4e2af7b1d9b4ea1906d7c1b12ebc2efab6f66bd63279e53a1ff0be75ca` | ok | P,P,P | RESULT: 3/3 |

Every import succeeded. The detailed Docker runs distinguished assertion failure, other exception and timeout; all observed failed tests in this selection raised `AssertionError`. The original aggregate Docker output matched each frozen output exactly.

## Inference provenance

Input manifest SHA-256: `426b455f3b371d62fbaf483a900cc4489e626cff12b8bfec332dc1a61f4a0e9a`; 48 case-bound input hashes covering 24 distinct prompt messages, each assigned to both models and frozen before inference. Sampling: `{'temperature': 0.0, 'top_p': 1.0, 'max_tokens': 1024, 'seed': 0}`; context size: `8192`. Server: `data/tools/llama/bin/llama-server.exe`; SHA-256 `00d50686815af38249d0218c91558fbd0e9093ac8c074bac86196907f4305e31`; configured build `b12110` and commit `cd959bae9`; `--version` output `version: 0.9.0-dev (build 12110, commit cd959bae9)<br>built with Clang 20.1.8 for Windows x86_64`. One local model server was active at a time. Raw API responses and prompts are retained under ignored `data/smoke/diagnostics/assertion_execution_20261112/run_48/`. All 48 calls were new cache misses.

- **WM_B**: `Qwen/Qwen2.5-7B-Instruct` revision `a09a35458c702b33eeacc393d103063234e8bc28`; pinned GGUF revision `bb5d59e06d9551d752d08b292a50eb208b07ab1f`; license `apache-2.0`; resolved identity `c15612e12f1910d8008f894b772c7836a875cbf29911036c17c665ba519b2dfa`; `data/models/wm_b/qwen2.5-7b-instruct-q4_k_m-00001-of-00002.gguf` SHA-256 `dfce12e3862a5283ccfb88221b48480e58745165de856439950d0f22590580db`, `data/models/wm_b/qwen2.5-7b-instruct-q4_k_m-00002-of-00002.gguf` SHA-256 `539cf93f78e887edea1c04e2d7d8cdaca9d01dae9c9025bcb8accbe29df3d72a`.
- **WM_C**: `Qwen/Qwen2.5-1.5B-Instruct` revision `989aa7980e4cf806f80c7fef2b1adb7bc71aa306`; pinned GGUF revision `91cad51170dc346986eccefdc2dd33a9da36ead9`; license `apache-2.0`; resolved identity `6a1a2eb6d15622bf3c96857206351ba97e1af16c30d7a74ee38970e434e9407e`; `data/models/wm_c/qwen2.5-1.5b-instruct-q4_k_m.gguf` SHA-256 `6a1a2eb6d15622bf3c96857206351ba97e1af16c30d7a74ee38970e434e9407e`.

## Complete 48-call evidence

Stage A expects the exact ordered three-string assertion array. Stage B expects the exact `TEST_RESULTS: P,F,P` form, with values varying by candidate. Stage C uses the frozen pilot parser; strict display format is measured separately. `Correct` means exact extraction, exact vector, or exact count for stages A, B, or C respectively. An invalid B output has no scored vector.

| Model | Candidate | Stage | Complete raw output | Parsed output | Docker expected | Valid | Correct | Tokens prompt/completion | Finish |
|---|---|---|---|---|---|---|---|---|---|
| WM_B | `acq-mbpp-125-g06` | A | <code>["assert find_length(\"11000010001\") == 6", "assert find_length(\"10111\") == 1", "assert find_length(\"11011101100101\") == 2"]</code> | ["assert find_length(\"11000010001\") == 6", "assert find_length(\"10111\") == 1", "assert find_length(\"11011101100101\") == 2"] | ["assert find_length(\"11000010001\") == 6", "assert find_length(\"10111\") == 1", "assert find_length(\"11011101100101\") == 2"] | True | True | 256/61 | stop |
| WM_B | `acq-mbpp-125-g07` | A | <code>["assert find_length(\"11000010001\") == 6", "assert find_length(\"10111\") == 1", "assert find_length(\"11011101100101\") == 2"]</code> | ["assert find_length(\"11000010001\") == 6", "assert find_length(\"10111\") == 1", "assert find_length(\"11011101100101\") == 2"] | ["assert find_length(\"11000010001\") == 6", "assert find_length(\"10111\") == 1", "assert find_length(\"11011101100101\") == 2"] | True | True | 222/61 | stop |
| WM_B | `acq-mbpp-563-g00` | A | <code>["assert extract_values('"Python", "PHP", "Java"')==['Python', 'PHP', 'Java']", "assert extract_values('"python","program","language"')==['python','program','language']", "assert extract_values('"red","blue","green","yellow"')==['red','blue','green','yellow']"]</code> | — | ["assert extract_values('\"Python\", \"PHP\", \"Java\"')==['Python', 'PHP', 'Java']", "assert extract_values('\"python\",\"program\",\"language\"')==['python','program','language']", "assert extract_values('\"red\",\"blue\",\"green\",\"yellow\"')==['red','blue','green','yellow']"] | False | False | 195/67 | stop |
| WM_B | `acq-mbpp-622-g00` | A | <code>["assert get_median([1, 12, 15, 26, 38], [2, 13, 17, 30, 45], 5) == 16.0", "assert get_median([2, 4, 8, 9], [7, 13, 17, 30, 45], 4) == 8.5", "assert get_median([3, 6, 14, 23, 36, 42], [2, 18, 27, 39, 49, 55], 6) == 25.0"]</code> | ["assert get_median([1, 12, 15, 26, 38], [2, 13, 17, 30, 45], 5) == 16.0", "assert get_median([2, 4, 8, 9], [7, 13, 17, 30, 45], 4) == 8.5", "assert get_median([3, 6, 14, 23, 36, 42], [2, 18, 27, 39, 49, 55], 6) == 25.0"] | ["assert get_median([1, 12, 15, 26, 38], [2, 13, 17, 30, 45], 5) == 16.0", "assert get_median([2, 4, 8, 9], [7, 13, 19, 28], 4) == 8.5", "assert get_median([3, 6, 14, 23, 36, 42], [2, 18, 27, 39, 49, 55], 6) == 25.0"] | True | False | 433/156 | stop |
| WM_B | `acq-mbpp-563-g10` | A | <code>["assert extract_values('"Python", "PHP", "Java"')==['Python', 'PHP', 'Java']", "assert extract_values('"python","program","language"')==['python','program','language']", "assert extract_values('"red","blue","green","yellow"')==['red','blue','green','yellow']"]</code> | — | ["assert extract_values('\"Python\", \"PHP\", \"Java\"')==['Python', 'PHP', 'Java']", "assert extract_values('\"python\",\"program\",\"language\"')==['python','program','language']", "assert extract_values('\"red\",\"blue\",\"green\",\"yellow\"')==['red','blue','green','yellow']"] | False | False | 173/67 | stop |
| WM_B | `acq-mbpp-563-g13` | A | <code>["assert extract_values('"Python", "PHP", "Java"')==['Python', 'PHP', 'Java']", "assert extract_values('"python","program","language"')==['python','program','language']", "assert extract_values('"red","blue","green","yellow"')==['red','blue','green','yellow']"]</code> | — | ["assert extract_values('\"Python\", \"PHP\", \"Java\"')==['Python', 'PHP', 'Java']", "assert extract_values('\"python\",\"program\",\"language\"')==['python','program','language']", "assert extract_values('\"red\",\"blue\",\"green\",\"yellow\"')==['red','blue','green','yellow']"] | False | False | 182/67 | stop |
| WM_B | `acq-mbpp-125-g00` | A | <code>["assert find_length(\"11000010001\") == 6", "assert find_length(\"10111\") == 1", "assert find_length(\"11011101100101\") == 2"]</code> | ["assert find_length(\"11000010001\") == 6", "assert find_length(\"10111\") == 1", "assert find_length(\"11011101100101\") == 2"] | ["assert find_length(\"11000010001\") == 6", "assert find_length(\"10111\") == 1", "assert find_length(\"11011101100101\") == 2"] | True | True | 227/61 | stop |
| WM_B | `acq-mbpp-125-g01` | A | <code>["assert find_length(\"11000010001\") == 6", "assert find_length(\"10111\") == 1", "assert find_length(\"11011101100101\") == 2"]</code> | ["assert find_length(\"11000010001\") == 6", "assert find_length(\"10111\") == 1", "assert find_length(\"11011101100101\") == 2"] | ["assert find_length(\"11000010001\") == 6", "assert find_length(\"10111\") == 1", "assert find_length(\"11011101100101\") == 2"] | True | True | 216/61 | stop |
| WM_C | `acq-mbpp-125-g06` | A | <code>```json<br>[<br>    "assert find_length('11000010001') == 6",<br>    "assert find_length('10111') == 1",<br>    "assert find_length('11011101100101') == 2"<br>]<br>```</code> | — | ["assert find_length(\"11000010001\") == 6", "assert find_length(\"10111\") == 1", "assert find_length(\"11011101100101\") == 2"] | False | False | 256/70 | stop |
| WM_C | `acq-mbpp-125-g07` | A | <code>```json<br>[<br>    "assert find_length(\"11000010001\") == 6",<br>    "assert find_length(\"10111\") == 1",<br>    "assert find_length(\"11011101100101\") == 2"<br>]<br>```</code> | — | ["assert find_length(\"11000010001\") == 6", "assert find_length(\"10111\") == 1", "assert find_length(\"11011101100101\") == 2"] | False | False | 222/70 | stop |
| WM_C | `acq-mbpp-563-g00` | A | <code>```json<br>[<br>    "assert extract_values('"Python", "PHP", "Java"')==['Python', 'PHP', 'Java']",<br>    "assert extract_values('"python","program","language"')==['python','program','language']",<br>    "assert extract_values('"red","blue","green","yellow"')==['red','blue','green','yellow']"<br>]<br>```</code> | — | ["assert extract_values('\"Python\", \"PHP\", \"Java\"')==['Python', 'PHP', 'Java']", "assert extract_values('\"python\",\"program\",\"language\"')==['python','program','language']", "assert extract_values('\"red\",\"blue\",\"green\",\"yellow\"')==['red','blue','green','yellow']"] | False | False | 195/81 | stop |
| WM_C | `acq-mbpp-622-g00` | A | <code>```json<br>[<br>    "assert get_median([1, 12, 15, 26, 38], [2, 13, 17, 30, 45], 5) == 16.0",<br>    "assert get_median([2, 4, 8, 9], [7, 13, 19, 28], 4) == 8.5",<br>    "assert get_median([3, 6, 14, 23, 36, 42], [2, 18, 27, 39, 49, 55], 6) == 25.0"<br>]<br>```</code> | — | ["assert get_median([1, 12, 15, 26, 38], [2, 13, 17, 30, 45], 5) == 16.0", "assert get_median([2, 4, 8, 9], [7, 13, 19, 28], 4) == 8.5", "assert get_median([3, 6, 14, 23, 36, 42], [2, 18, 27, 39, 49, 55], 6) == 25.0"] | False | False | 433/161 | stop |
| WM_C | `acq-mbpp-563-g10` | A | <code>```json<br>[<br>    "assert extract_values('"Python", "PHP", "Java"')==['Python', 'PHP', 'Java']",<br>    "assert extract_values('"python","program","language"')==['python','program','language']",<br>    "assert extract_values('"red","blue","green","yellow"')==['red','blue','green','yellow']"<br>]<br>```</code> | — | ["assert extract_values('\"Python\", \"PHP\", \"Java\"')==['Python', 'PHP', 'Java']", "assert extract_values('\"python\",\"program\",\"language\"')==['python','program','language']", "assert extract_values('\"red\",\"blue\",\"green\",\"yellow\"')==['red','blue','green','yellow']"] | False | False | 173/78 | stop |
| WM_C | `acq-mbpp-563-g13` | A | <code>```json<br>[["\"Python\", \"PHP\", \"Java\""], ["\"python\", \"program\", \"language\""], ["\"red\", \"blue\", \"green\", \"yellow\""]]<br>```</code> | — | ["assert extract_values('\"Python\", \"PHP\", \"Java\"')==['Python', 'PHP', 'Java']", "assert extract_values('\"python\",\"program\",\"language\"')==['python','program','language']", "assert extract_values('\"red\",\"blue\",\"green\",\"yellow\"')==['red','blue','green','yellow']"] | False | False | 182/42 | stop |
| WM_C | `acq-mbpp-125-g00` | A | <code>```json<br>[<br>    "assert find_length('11000010001') == 6",<br>    "assert find_length('10111') == 1",<br>    "assert find_length('11011101100101') == 2"<br>]<br>```</code> | — | ["assert find_length(\"11000010001\") == 6", "assert find_length(\"10111\") == 1", "assert find_length(\"11011101100101\") == 2"] | False | False | 227/70 | stop |
| WM_C | `acq-mbpp-125-g01` | A | <code>```json<br>[<br>    "assert find_length('11000010001') == 6",<br>    "assert find_length('10111') == 1",<br>    "assert find_length('11011101100101') == 2"<br>]<br>```</code> | — | ["assert find_length(\"11000010001\") == 6", "assert find_length(\"10111\") == 1", "assert find_length(\"11011101100101\") == 2"] | False | False | 216/70 | stop |
| WM_B | `acq-mbpp-125-g06` | B | <code>F,F,F</code> | — | F,F,F | False | False | 276/4 | stop |
| WM_B | `acq-mbpp-125-g07` | B | <code>P,P,P</code> | — | F,F,F | False | False | 242/4 | stop |
| WM_B | `acq-mbpp-563-g00` | B | <code>TEST_RESULTS:PPP</code> | — | P,F,F | False | False | 215/5 | stop |
| WM_B | `acq-mbpp-622-g00` | B | <code>P,P,P</code> | — | P,F,F | False | False | 453/4 | stop |
| WM_B | `acq-mbpp-563-g10` | B | <code>TEST_RESULTS:PPP</code> | — | F,P,P | False | False | 193/5 | stop |
| WM_B | `acq-mbpp-563-g13` | B | <code>TEST_RESULTS:PPP</code> | — | F,P,P | False | False | 202/5 | stop |
| WM_B | `acq-mbpp-125-g00` | B | <code>TEST_RESULTS:PPP</code> | — | P,P,P | False | False | 247/5 | stop |
| WM_B | `acq-mbpp-125-g01` | B | <code>P,P,P</code> | — | P,P,P | False | False | 236/4 | stop |
| WM_C | `acq-mbpp-125-g06` | B | <code>TEST_RESULTS: P,P,F</code> | P,P,F | F,F,F | True | False | 276/7 | stop |
| WM_C | `acq-mbpp-125-g07` | B | <code>TEST_RESULTS: P,P,F</code> | P,P,F | F,F,F | True | False | 242/7 | stop |
| WM_C | `acq-mbpp-563-g00` | B | <code>TEST_RESULTS: P,F,P</code> | P,F,P | P,F,F | True | False | 215/7 | stop |
| WM_C | `acq-mbpp-622-g00` | B | <code>TEST_RESULTS: P,P,F</code> | P,P,F | P,F,F | True | False | 453/7 | stop |
| WM_C | `acq-mbpp-563-g10` | B | <code>TEST_RESULTS: P,P,F</code> | P,P,F | F,P,P | True | False | 193/7 | stop |
| WM_C | `acq-mbpp-563-g13` | B | <code>TEST_RESULTS: P,P,F</code> | P,P,F | F,P,P | True | False | 202/7 | stop |
| WM_C | `acq-mbpp-125-g00` | B | <code>TEST_RESULTS: P,P,F</code> | P,P,F | P,P,P | True | False | 247/7 | stop |
| WM_C | `acq-mbpp-125-g01` | B | <code>TEST_RESULTS: P,P,F</code> | P,P,F | P,P,P | True | False | 236/7 | stop |
| WM_B | `acq-mbpp-125-g06` | C | <code>RESULT: 2/3</code> | 2/3 | 0/3 | True | False | 269/7 | stop |
| WM_B | `acq-mbpp-125-g07` | C | <code>RESULT: 3/3</code> | 3/3 | 0/3 | True | False | 235/7 | stop |
| WM_B | `acq-mbpp-563-g00` | C | <code>RESULT: 3/3</code> | 3/3 | 1/3 | True | False | 208/7 | stop |
| WM_B | `acq-mbpp-622-g00` | C | <code>RESULT: 3/3</code> | 3/3 | 1/3 | True | False | 446/7 | stop |
| WM_B | `acq-mbpp-563-g10` | C | <code>RESULT: 3/3</code> | 3/3 | 2/3 | True | False | 186/7 | stop |
| WM_B | `acq-mbpp-563-g13` | C | <code>RESULT: 3/3</code> | 3/3 | 2/3 | True | False | 195/7 | stop |
| WM_B | `acq-mbpp-125-g00` | C | <code>RESULT: 3/3</code> | 3/3 | 3/3 | True | True | 240/7 | stop |
| WM_B | `acq-mbpp-125-g01` | C | <code>RESULT: 3/3</code> | 3/3 | 3/3 | True | True | 229/7 | stop |
| WM_C | `acq-mbpp-125-g06` | C | <code>RESULT: 3/3</code> | 3/3 | 0/3 | True | False | 269/7 | stop |
| WM_C | `acq-mbpp-125-g07` | C | <code>RESULT: 3/3</code> | 3/3 | 0/3 | True | False | 235/7 | stop |
| WM_C | `acq-mbpp-563-g00` | C | <code>RESULT: 3/3</code> | 3/3 | 1/3 | True | False | 208/7 | stop |
| WM_C | `acq-mbpp-622-g00` | C | <code>RESULT: 3/3</code> | 3/3 | 1/3 | True | False | 446/7 | stop |
| WM_C | `acq-mbpp-563-g10` | C | <code>RESULT: 3/3</code> | 3/3 | 2/3 | True | False | 186/7 | stop |
| WM_C | `acq-mbpp-563-g13` | C | <code>RESULT: 3/3</code> | 3/3 | 2/3 | True | False | 195/7 | stop |
| WM_C | `acq-mbpp-125-g00` | C | <code>RESULT: 3/3</code> | 3/3 | 3/3 | True | True | 240/7 | stop |
| WM_C | `acq-mbpp-125-g01` | C | <code>RESULT: 3/3</code> | 3/3 | 3/3 | True | True | 229/7 | stop |

## Accuracy and failure mechanisms

All denominators below are assigned candidates or assertions unless explicitly described as parsed-only. Invalid responses count as incorrect for coverage-adjusted accuracy; they do not enter the per-test confusion matrix.

| Measure | WM-B | WM-C |
|---|---:|---:|
| Stage A valid bare JSON | 5/8 | 0/8 |
| Stage A valid three-string array | 5/8 | 0/8 |
| Stage A exact ordered extraction | 4/8 | 0/8 |
| Stage B valid format | 0/8 | 8/8 |
| Stage B correct assertions, assigned | 0/24 | 12/24 |
| Stage B exact vectors, assigned | 0/8 | 0/8 |
| Stage C parser valid | 8/8 | 8/8 |
| Stage C strict display format | 8/8 | 8/8 |
| Stage C denominator correct | 8/8 | 8/8 |
| Stage C exact counts | 2/8 | 2/8 |
| Stage C pass/fail labels | 3/8 | 2/8 |
| Stage C fractional counts | 1/8 | 0/8 |

**WM_B detail.** Among correctly extracted candidates, Stage B scored 0/12 individual assertions and 0/4 exact vectors. Among valid B responses it scored 0/0 assertions. Parsed all-PASS vectors: 0/8; all-FAIL: 0/8. Per-test confusion (truth→prediction): {'P->P': 0, 'P->F': 0, 'F->P': 0, 'F->F': 0}. Completion reasons: {'stop': 24}.


**WM_C detail.** Among correctly extracted candidates, Stage B scored 0/0 individual assertions and 0/0 exact vectors. Among valid B responses it scored 12/24 assertions. Parsed all-PASS vectors: 0/8; all-FAIL: 0/8. Per-test confusion (truth→prediction): {'P->P': 8, 'P->F': 4, 'F->P': 8, 'F->F': 4}. Completion reasons: {'stop': 24}.

WM-B's four exact A outputs were all `mbpp-125`. One other A response was valid JSON but copied an incorrect second `mbpp-622` assertion; the three `mbpp-563` responses had unescaped quotation marks and were invalid JSON. No valid A array was reordered or duplicated. WM-C wrapped every A answer in a Markdown code fence, making all eight invalid as bare JSON; several also changed or failed to copy assertion text. These format failures prevent an unconditional claim that WM-C cannot identify assertions.

All eight WM-B B responses stopped normally but omitted required syntax: seven visibly expressed all-PASS and one all-FAIL, yet none matched `TEST_RESULTS: P,F,P` structure. These visible strings are qualitative evidence only. WM-C gave eight valid B vectors, 12/24 correct individual outcomes and no exact vector. All 16 C responses were strict `RESULT: k/3`, with no denominator mismatch or truncation; both models got only the two 3/3 candidates' counts right.

Conditional accuracy with a 0/0 denominator is undefined, not a measured zero percent. The WM-B per-test confusion matrix is empty because no B response met the fixed format.

## Cross-stage comparison

Types can overlap. Type 1: extraction incorrect. Type 2: extraction correct but B vector wrong. Type 3: B vector correct but C count wrong. Type 4: B vector wrong but C count right. Type 5: both right. Type 6: B implied count disagrees with C. Invalid B outputs do not yield a scored implied count; invalid A can coexist with a valid B vector.

| Model | Candidate | Task | Docker vector/count | A exact | B vector/implied count | C count | Types |
|---|---|---|---|---|---|---|---|
| WM_B | `acq-mbpp-125-g06` | `mbpp-125` | F,F,F / 0 | True | invalid / — | 2 | — |
| WM_B | `acq-mbpp-125-g07` | `mbpp-125` | F,F,F / 0 | True | invalid / — | 3 | — |
| WM_B | `acq-mbpp-563-g00` | `mbpp-563` | P,F,F / 1 | False | invalid / — | 3 | 1 |
| WM_B | `acq-mbpp-622-g00` | `mbpp-622` | P,F,F / 1 | False | invalid / — | 3 | 1 |
| WM_B | `acq-mbpp-563-g10` | `mbpp-563` | F,P,P / 2 | False | invalid / — | 3 | 1 |
| WM_B | `acq-mbpp-563-g13` | `mbpp-563` | F,P,P / 2 | False | invalid / — | 3 | 1 |
| WM_B | `acq-mbpp-125-g00` | `mbpp-125` | P,P,P / 3 | True | invalid / — | 3 | — |
| WM_B | `acq-mbpp-125-g01` | `mbpp-125` | P,P,P / 3 | True | invalid / — | 3 | — |
| WM_C | `acq-mbpp-125-g06` | `mbpp-125` | F,F,F / 0 | False | P,P,F / 2 | 3 | 1, 6 |
| WM_C | `acq-mbpp-125-g07` | `mbpp-125` | F,F,F / 0 | False | P,P,F / 2 | 3 | 1, 6 |
| WM_C | `acq-mbpp-563-g00` | `mbpp-563` | P,F,F / 1 | False | P,F,P / 2 | 3 | 1, 6 |
| WM_C | `acq-mbpp-622-g00` | `mbpp-622` | P,F,F / 1 | False | P,P,F / 2 | 3 | 1, 6 |
| WM_C | `acq-mbpp-563-g10` | `mbpp-563` | F,P,P / 2 | False | P,P,F / 2 | 3 | 1, 6 |
| WM_C | `acq-mbpp-563-g13` | `mbpp-563` | F,P,P / 2 | False | P,P,F / 2 | 3 | 1, 6 |
| WM_C | `acq-mbpp-125-g00` | `mbpp-125` | P,P,P / 3 | False | P,P,F / 2 | 3 | 1, 4, 6 |
| WM_C | `acq-mbpp-125-g01` | `mbpp-125` | P,P,P / 3 | False | P,P,F / 2 | 3 | 1, 4, 6 |

WM_B type counts (overlapping): {'type_1': 4, 'type_2': 0, 'type_3': 0, 'type_4': 0, 'type_5': 0, 'type_6': 0}.

WM_C type counts (overlapping): {'type_1': 8, 'type_2': 0, 'type_3': 0, 'type_4': 2, 'type_5': 0, 'type_6': 8}.

## Partial-pass audit and task dependence

The four partial-pass candidates are `mbpp-563-g00` (P,F,F), `mbpp-622-g00` (P,F,F), `mbpp-563-g10` (F,P,P), and `mbpp-563-g13` (F,P,P). WM-B produced no strictly valid B vector on these four; its raw B outputs were `TEST_RESULTS:PPP` for all three `mbpp-563` candidates and `P,P,P` for `mbpp-622-g00`. All four WM-B C calls predicted `RESULT: 3/3`. WM-C B returned `P,F,P` for `mbpp-563-g00` and `P,P,F` for the other three; none matched Docker. The B implied count of 2 agrees with the actual count for the two 2/3 candidates only by positional coincidence. All four WM-C C calls predicted `RESULT: 3/3`.

Task-grouped candidate outcomes: `mbpp-125` has four candidates (two 0/3, two 3/3); `mbpp-563` has three (one 1/3, two 2/3); `mbpp-622` has one (1/3). Within `mbpp-125` the tests are identical while candidate code varies from 0/3 to 3/3. Within `mbpp-563` the tests are identical while code varies from 1/3 to 2/3. This outcome-balanced selection confounds some outcome strata with task identity. The 48 calls are repeated measurements on eight implementations from only three tasks, not 48 independent reasoning trials.

| Model | Task | Candidates | A exact | B valid | B correct tests | B exact vectors | C exact counts |
|---|---|---:|---:|---:|---:|---:|---:|
| WM_B | `mbpp-125` | 4 | 4/4 | 0/4 | 0/12 | 0/4 | 2/4 |
| WM_B | `mbpp-563` | 3 | 0/3 | 0/3 | 0/9 | 0/3 | 0/3 |
| WM_B | `mbpp-622` | 1 | 0/1 | 0/1 | 0/3 | 0/1 | 0/1 |
| WM_C | `mbpp-125` | 4 | 0/4 | 4/4 | 6/12 | 0/4 | 2/4 |
| WM_C | `mbpp-563` | 3 | 0/3 | 3/3 | 4/9 | 0/3 | 0/3 |
| WM_C | `mbpp-622` | 1 | 0/1 | 1/1 | 2/3 | 0/1 | 0/1 |

## Concrete failure examples

- For `acq-mbpp-563-g00`, WM-C predicted `TEST_RESULTS: P,F,P`; Docker observed P,F,F. Its independent C output was `RESULT: 3/3`, versus actual 1/3. The generated source also contains a top-level assertion, but the Stage A outputs did not validly substitute it into the original test list.
- For `acq-mbpp-125-g06`, WM-B copied all three assertions exactly in Stage A, then returned `F,F,F` without the required Stage B prefix. Its C output was `RESULT: 2/3`; Docker observed F,F,F and 0/3.
- For `acq-mbpp-622-g00`, WM-B's Stage A JSON changed the second assertion's list from `[7, 13, 19, 28]` to `[7, 13, 17, 30, 45]`. Its B output was the invalid `P,P,P` and C output `RESULT: 3/3`, versus Docker P,F,F and 1/3.

## Mechanism assessment and limitations

Stage A format validity and exact-copy accuracy measure input extraction. They do not prove semantic understanding. Stage B measures per-assertion reasoning only when the fixed output is parseable; malformed but visually suggestive responses remain invalid. Stage C used the existing frozen parser. B and C are independent calls, so Type 3 and Type 6 indicate cross-call inconsistency, not proven arithmetic failure. The small, selected, task-dependent sample supports diagnosis only and does not revise any official pilot verdict or open the smoke gate.


## Validation

- `.venv\Scripts\python.exe -m pytest -q`: exit 0; 234 passed in 28.14s.
- `.venv\Scripts\ruff.exe check src tests`: exit 0; All checks passed!.
- `.venv\Scripts\ruff.exe format --check src tests`: exit 0; 58 files already formatted.
- `git diff --check`: exit 0; no output.
- `git diff --cached --check`: exit 0; no output.

**Next recommendation:** Review the Stage B format failures and the 1/3–2/3 execution predictions as a single owner decision on whether to authorize a separately preregistered diagnostic; keep official scoring paused.
