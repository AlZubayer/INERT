# Vendored prompt-adaptation diagnostic (2026-11-13; audited 2026-11-14)

Status: diagnostic only. Not smoke scoring, not P0, not pilot scoring. The
official renderer (`src/inert/render.py`), prompts, text conditions, parser,
thresholds and seeds are unchanged. The smoke gate remains closed.

## Question

Are the WM-C parse failures and the poor execution predictions caused by a
defect in how the vendored prompts are assembled?

## What was checked without inference

- **Ground truth.** The 11 selected smoke candidates retain their recorded
  Docker results. In particular, `mbpp-440-g00` is recorded as `0/3`; its
  implementation returns word-index arithmetic where the assertions require
  character positions. The archived diagnostic did not execute candidates
  again.
- **Runtime.** Cache request identities record pinned model hashes, the server
  binary hash, context size 8,192, temperature 0, top-p 1, seed 0, and the
  1,024-token completion limit. Many Channel-C completions ended with
  `finish_reason=length`; that is output truncation, not absence of it.
- **Upstream Channel C assembly.** `eval/eval.py` sends the system prompt plus
  `prompts[turn_idx-1]` from the pinned AgentWorldBench dataset, preceded by
  prior user/assistant turns when available. The current renderer sends the
  same vendored terminal system prompt and a bare compact JSON keystroke-action
  array as its user message; the action ends in a newline. In the first 77
  complete terminal rows from the first 3 MB of
  `Qwen/AgentWorldBench` (revision `6b8d28437042434dcdd168434227ca0de408c5ba`,
  Apache-2.0), every evaluated turn has a turn header, fenced indent-2 JSON
  action, and one fixed instruction suffix. The 16 first turns have a
  `**Current State:**` block; later turns need not. The suffix SHA-256 is
  `ed04f1deea4b3a5159f2fe5295a9b60ddbc6e5c5f08ba476eeb270429cd9c1fd`; it
  asks for step-by-step reasoning followed by `<predicted_observation>` tags.
  The new diagnostic-only `prompts/vendored/wm_terminal_turn.txt` has source,
  revision, location, Apache-2.0 license, exact template hash, and declared
  state/action substitutions. Substituting the first pinned dataset row's
  state and action reconstructs its evaluated turn byte for byte. The upstream
  code was read as data and was not imported or executed. This audit corrected
  the new file's provenance header from `prompts[turn_idx]` to the actual
  `prompts[turn_idx-1]`; the model-facing template bytes did not change. The
  diagnostic renderer now normalizes Windows CRLF checkout line endings for
  this new data file, so a future checkout recreates the same frozen messages.
- **Upstream Channel D assembly.** Simia labels history turns `Assistant:` and
  `User/Tool response:` and writes `No reference conversation` when there is
  none. The current renderer uses `Agent:` / `Environment:` and an empty field.

## Variants

All variants use the same 11 smoke core-set candidates, the same condition
texts, the frozen sampling parameters and the frozen parser.

| Variant | Assembly |
| --- | --- |
| C0 | Current vendored Channel C (bare compact JSON action) |
| C1 | Upstream AgentWorldBench user turn |
| C2 | C1, with one `TESTS` entry per line in `run_tests.py` |
| D0 | Current vendored Channel D |
| D1 | Simia role labels and empty-reference placeholder |
| D2 | D1, with one `TESTS` entry per line in `run_tests.py` |

The archived manifest has 594 unique prompt cases: 11 candidates × 9
conditions × 6 variants. It was frozen before the recorded inference;
`cases_sha256` is
`531f729744d2835b14cf91076de7fc302b54af801b8e42da4576c3605bc53a4f`.
WM-C completed all 594 assignments. WM-B completed 264 assignments on the
four stated conditions. **The diagnostic therefore has 858 completed
model-call records, not 594.**

### Complete call accounting

`Valid` means the unchanged `RESULT: k/n` parser accepted the last match with
denominator 3. `Exact` means the parsed passing count matched Docker truth;
invalid calls count as incorrect for the assigned-call denominator. `Length`
counts `finish_reason=length`, including calls with a parser-valid result.

| Model | Channel | Variant | Planned | Completed | New | Cache hits | Valid | Invalid | Exact | Length | Wrong denominator |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| WM-C | C | C0 | 99 | 99 | 97 | 2 | 41 | 58 | 15 | 82 | 37 |
| WM-C | C | C1 | 99 | 99 | 97 | 2 | 0 | 99 | 0 | 99 | 0 |
| WM-C | C | C2 | 99 | 99 | 97 | 2 | 0 | 99 | 0 | 99 | 0 |
| WM-C | D | D0 | 99 | 99 | 97 | 2 | 35 | 64 | 17 | 0 | 64 |
| WM-C | D | D1 | 99 | 99 | 97 | 2 | 57 | 42 | 24 | 0 | 42 |
| WM-C | D | D2 | 99 | 99 | 97 | 2 | 49 | 50 | 21 | 0 | 50 |
| WM-B | C | C0 | 44 | 44 | 44 | 0 | 44 | 0 | 15 | 0 | 0 |
| WM-B | C | C1 | 44 | 44 | 44 | 0 | 36 | 8 | 13 | 34 | 0 |
| WM-B | C | C2 | 44 | 44 | 44 | 0 | 31 | 13 | 12 | 36 | 0 |
| WM-B | D | D0 | 44 | 44 | 44 | 0 | 44 | 0 | 15 | 0 | 0 |
| WM-B | D | D1 | 44 | 44 | 44 | 0 | 44 | 0 | 15 | 0 | 0 |
| WM-B | D | D2 | 44 | 44 | 44 | 0 | 44 | 0 | 15 | 0 | 0 |
| **Total** | | | **858** | **858** | **846** | **12** | **425** | **433** | **162** | **350** | **193** |

The eight groups originally cited by the owner total 572 records. C2 and D2
contribute the other **286** (198 WM-C, 88 WM-B). The apparent 22-call gap
(`594 − 572`) mixes the WM-C-only manifest count with a two-model subset;
there is no 22-call group in the archive. The 594 case IDs are unique. Across
both response files, 858 model/case IDs are unique; 12 WM-C assignments reuse
exact T0/NAT prompt hashes for two candidates whose natural text is empty.
They are recorded as cache hits, so the SQLite caches contain 582 WM-C and
264 WM-B distinct completed requests. Every response matches its archived
cache key, request settings, completion, and raw API body. There are no
unmatched, incomplete, or failed HTTP requests in the archived completed-call
set; the evidence cannot prove whether any unpersisted attempt occurred.

The archived WM-C request identity is
`6a1a2eb6d15622bf3c96857206351ba97e1af16c30d7a74ee38970e434e9407e`;
WM-B's two-shard identity is
`c15612e12f1910d8008f894b772c7836a875cbf29911036c17c665ba519b2dfa`.
Both cache identities record server SHA-256
`00d50686815af38249d0218c91558fbd0e9093ac8c074bac86196907f4305e31`
and `--jinja`, `--reasoning-format none`, 8,192 context and 99 GPU layers.
The current local GGUF files and server binary were independently rehashed
against those pinned identities during the audit, without starting inference.
The two model roles used distinct ignored cache files beneath the diagnostic
directory. Original smoke, pilot and historical caches were not read for
these new calls or altered by this audit. The archived prompt messages contain
no literal executed `RESULT: 0/3`, `1/3`, `2/3` or `3/3` line and no
`n_passed`, `true_pass`, `R_exec` or `harness_output` field. The registered
condition texts still make outcome claims by design.

## Results

### WM-C (all 9 conditions, 99 calls per variant)

| Variant | Parse failures | Truncated at 1,024 | Wrong denominator | T0 balanced accuracy |
| --- | ---: | ---: | ---: | ---: |
| C0 | 58/99 (58.6%) | 82 | 37 | 0.50 (6 valid) |
| C1 | 99/99 (100%) | 99 | 0 | none valid |
| C2 | 99/99 (100%) | 99 | 0 | none valid |
| D0 | 64/99 (64.6%) | 0 | 64 | 0.50 (5 valid) |
| D1 | 42/99 (42.4%) | 0 | 42 | 0.50 (8 valid) |
| D2 | 50/99 (50.5%) | 0 | 50 | 0.50 (7 valid) |

Under C1 and C2, all 198 WM-C responses reached the 1,024-token limit, none
contained a `<predicted_observation>` opening tag, and none had a parser-valid
`RESULT: k/3` match. All 198 **do** contain `RESULT:` text, typically copied
from the harness template; 97/99 C1 and 95/99 C2 outputs contain a fabricated
`### Turn 2`. This is observed echoing and continuation, not proof of a
particular internal mechanism. Every parser-valid Channel-D prediction is
`3/3`. WM-C exceeded the frozen 10% parse-failure threshold in all six
tested variants.

### WM-B (conditions T0, NEU_A, NEU_B, MIS_OUTCOME; 44 calls per variant)

| Variant | Parse failures | Truncated at 1,024 | Exact count correct | Predicted k (valid) | T0 balanced accuracy |
| --- | ---: | ---: | ---: | --- | ---: |
| C0 | 0/44 | 0 | 15 | 0: 9, 3: 35 | 0.58 |
| C1 | 8/44 (18.2%) | 34 | 13 | 0: 2, 1: 1, 2: 1, 3: 32 | 0.50 |
| C2 | 13/44 (29.5%) | 36 | 12 | 0: 4, 3: 27 | 0.50 |
| D0 | 0/44 | 0 | 15 | 0: 5, 3: 39 | 0.50 |
| D1 | 0/44 | 0 | 15 | 0: 5, 3: 39 | 0.50 |
| D2 | 0/44 | 0 | 15 | 0: 5, 3: 39 | 0.50 |

In sampled C1/C2 raw outputs, WM-B expands the files and gives a general
correctness claim without correctly tracing the failing assertions. For
`mbpp-440-g00:T0:C1` it calls all three tests passing and includes
`RESULT: 3/3`, while Docker truth is `0/3`. That response ends with
`finish_reason=length` at 1,024 tokens; the frozen parser still accepts its
earlier `RESULT: 3/3` match. Across C1 and C2, 34/44 and 36/44 completions
respectively hit the token limit; 8/44 and 13/44 failed to parse. Thus
truncation and parse failure overlap but are not identical. Exact counts on
assigned calls changed from C0's 15/44 to C1's 13/44 and C2's 12/44;
among parser-valid calls those figures are 13/36 and 12/31.

All 44 paired WM-B D0, D1 and D2 raw outputs are byte-identical. For WM-C,
D1 improved parser validity from 35/99 to 57/99 and exact counts from 17/99
to 24/99; D2 yielded 49/99 valid and 21/99 exact. D1 changes role labels,
the empty-reference placeholder, and formatting together. D2 also changes
the harness layout. The data do not isolate the effect of labels alone, and
all WM-C Channel-D variants still fail the parse gate.

In this selected sample, WM-B's Channel-D predictions correlate with the
outcome-claim text on passing candidates. All three Channel-D variants have
the same observed counts:

| Condition | Predicted pass, failing candidates | Predicted fail, passing candidates |
| --- | ---: | ---: |
| T0 | 6/6 | 0/5 |
| NEU_A | 6/6 | 0/5 |
| NEU_B | 6/6 | 0/5 |
| MIS_OUTCOME | 6/6 | 5/5 |

C0 shows a related pattern (failing candidates predicted to pass: 5/6, 4/6,
5/6, 6/6; passing candidates predicted to fail: 0/5, 0/5, 0/5, 5/5).
This is descriptive, not a preregistered KT-A result. The 5/5 passing-case
flips belong to the design's exploratory mirror analysis. The KT-A primary
endpoint uses false-pass predictions on failing candidates and compares
`MIS_OUTCOME` with neutral-text controls; this diagnostic does not estimate
that endpoint with its registered task-level uncertainty.

### Harness layout and prompt isolation

C1/C2 and D1/D2 use the same candidate code, original three test strings,
thought text and frozen model settings within each pair. Only the `TESTS`
assignment is changed from the compact Python list representation to one
string per line; the existing harness body and Docker semantics are unchanged.
The actual archived prompt pairs were checked against both renderings. For
WM-C, C1 and C2 both had 99/99 parse failures; D1 and D2 had 42/99 and
50/99. For WM-B, C1 and C2 had 8/44 and 13/44 parse failures and 13/44 and
12/44 exact counts. WM-B's D1/D2 outputs were identical; WM-C's were not.
Those observations do not justify changing the official harness layout.

## Conclusions

1. The tested upstream-style Channel-C turn did **not** improve measured
   parsing or exact counts under the frozen 1,024-token budget. This does not
   prove that additional reasoning cannot help under another, separately
   authorized design. The upstream suffix requests reasoning and
   `<predicted_observation>` tags while the frozen parser requires a
   `RESULT: k/3` line, so the test also changes the requested output
   interface. No official renderer change follows from this ablation.
2. The archived model calls used the intended candidate code, tests,
   parser and sampling settings. The observed failures are compatible with
   output-format, truncation and prediction errors; the experiment does not
   uniquely identify a causal mechanism.
3. WM-C exceeded the 10% parse-failure threshold under every prompt
   configuration tested here (42.4–100%). Engineering smoke validation has
   not passed; the original WM-C-only smoke gate remains closed.
4. WM-B parsed all C0 and D0 calls. Its T0 balanced accuracies of 0.58 (C0)
   and 0.50 (D0) come from just 11 candidates across three tasks. Section
   11.2's `INVALID` rule applies to the full pilot WM-channel core set,
   separately from the 10% parsing gate. This preliminary sample determines
   neither full-pilot cell validity nor a KT-A verdict.
5. Under T0, WM-B predicts pass for 5/6 failing candidates in C0 and 6/6
   in D0; the false-pass rate is already high in this small selected sample.
   No population-level model claim or registered effect verdict follows.

## Limits

- Three tasks and 11 candidates; outcomes within a task are highly dependent.
- WM-B was run on four of nine conditions.
- WM-A has not been run in this diagnostic.
- C1 and C2 were scored with the frozen 1,024-token limit; a higher limit was
  not tested.
- The six diagnostic prompt assemblies test bundled adaptations, not every
  individual component independently. No causal attribution to Channel-D
  role labels alone is warranted. C1/C2 also add an output instruction that
  does not directly match the frozen parser; their parse failures cannot be
  attributed solely to the presence of a turn header or fenced action.

## Next engineering step

Review the existing WM-C parse failures and the preliminary WM-B baseline
validity issue together as an owner decision. Any further prompt adaptation
or model substitution would require a separately specified and authorized
study; do not resume smoke, P0 or pilot scoring from this report.

## Audit validation

On 2026-11-14, the independent audit completed `pytest -q` with **239
passing tests**. Ruff lint and Ruff format checks passed for `src` and
`tests`; `git diff --check` passed. No test launched a model server or
repeated the diagnostic. The earlier 235-test count preceded four additional
audit regression tests. The audit verified the archived 858 records, cache
request hashes, raw API bodies, prompt-template provenance, and source/test
equivalence without changing any frozen pilot file.

## Artefacts

- Code: `src/inert/diagnostic_prompt_adaptation.py`
- Data (git-ignored): `data/smoke/diagnostics/prompt_adaptation_20261113/`
  (`manifest.json`, `cases.json`, `responses/`, `analysis_wm_b.json`,
  `analysis_wm_c.json`, separate caches and logs)
- Source provenance: [pinned Qwen-AgentWorld evaluator](https://github.com/QwenLM/Qwen-AgentWorld/blob/cd0aa83dc7a9c733695eb9c4652e0a68b6e6ecde/eval/eval.py), [pinned AgentWorldBench dataset](https://huggingface.co/datasets/Qwen/AgentWorldBench/tree/6b8d28437042434dcdd168434227ca0de408c5ba), and [pinned Simia simulator](https://github.com/microsoft/Simia-Agent-Training/blob/ea77d9d13362cc56cd1e0f33dc4cea4508aea28f/Simia-RL/subtrees/ragen/ragen/env/simulated_General/env.py).
