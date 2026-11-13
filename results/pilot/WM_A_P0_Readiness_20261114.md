# WM-A P0 readiness: READY_FOR_P0_INPUT_PREPARATION

**Audit date:** 2026-11-14 (Asia/Dhaka). **Branch:** `pilot/steps-0-1`; starting commit `2d6c051495f57a621eca27a104ed1211b6a65594`. This is an offline preparation audit. P0, model inference, new candidate generation, and pilot scoring were not run. The original WM-C smoke gate remains closed; the 198/198 WM-B engineering smoke is unchanged and does not replace it.

## Model readiness

| Check | Observation |
| --- | --- |
| Model | `Qwen/Qwen-AgentWorld-35B-A3B`, source revision `60d2b0434a53d2e62a7c00a489586815d94ebffb`, Apache-2.0 per the pinned [source licence](https://huggingface.co/Qwen/Qwen-AgentWorld-35B-A3B/blob/60d2b0434a53d2e62a7c00a489586815d94ebffb/LICENSE) |
| GGUF | `DevQuasar/Qwen.Qwen-AgentWorld-35B-A3B-GGUF`, revision `d5ab6b74dad26a7dcb1fd9b5692d266573d057f2`, file `Qwen.Qwen-AgentWorld-35B-A3B.Q4_K_M.gguf` from the [pinned repository](https://huggingface.co/DevQuasar/Qwen.Qwen-AgentWorld-35B-A3B-GGUF/tree/d5ab6b74dad26a7dcb1fd9b5692d266573d057f2) |
| Local path | `data/models/wm_a/Qwen.Qwen-AgentWorld-35B-A3B.Q4_K_M.gguf` |
| Exact size | 21,166,758,784 bytes, matching pinned LFS metadata |
| Full-file SHA-256 | `98de3cd55f5bd89a15708e084ccbb838ff00dec6c35e9daa15eb3f3fad596bdd`, matching `configs/models.yaml` and pinned LFS metadata |
| Verification | **PASS**: pinned revision, HTTP range responses, resumed partial bytes, final size, and full-file digest checked. The `.part` file was promoted only after verification. Evidence: `data/smoke/diagnostics/wm_a_p0_readiness_20261114/download_status.json`. |
| Storage and memory | E: had 44,179,869,696 free bytes after download. The GPU reported 16,311 MiB total and 14,243 MiB free at audit time. Q4 exceeds GPU capacity, so partial CPU offload is required. The host has 16,216,674,304 bytes of physical RAM; actual load feasibility and throughput remain unknown until the authorized P0 run. |
| Fallback | Q3_K_M is **not downloaded**. Its identifier and expected SHA are registered, but no local fallback weight is available. |

The installed llama.cpp build and WM-A architecture support were verified in `results/pilot/env.json`. That check does not establish that this particular Q4 file loads at 8,192 context tokens. `configs/models.yaml` retains its original `local_verified: false` provenance field because this task's requested Git staging scope excluded config edits; the exact local verification is recorded above and in ignored audit evidence. `resolve_model` rechecks the full SHA before any server start.

## P0 input readiness and sequence

The pilot profile has **0 ready task records** in `data/tasks.jsonl` and **0 prepared item records** in `data/items.jsonl`, versus the registered **12 tasks** and **100 calls**. The three-task smoke profile has 3 tasks and 310 items in separate paths; those records are not P0 inputs. Counts and file-existence checks are in `data/smoke/diagnostics/wm_a_p0_readiness_20261114/audit_observations.json`.

Design section 12.2 requires `tasks -> propose -> execute -> core-set -> thoughts -> build-items -> p0`. `Pilot_Next_Steps.md` places P0 in Step 3 and full data generation in Step 4. The implementation cannot perform Step 3 with the current pilot profile because `p0.py` reads the outputs of those earlier stages. The design's stage dependency order is authoritative. Preparing the missing inputs would require local proposer inference, Docker execution, and inertness checks; none occurred in this audit.

Under separate authorization, a reproducible preparation procedure is: run `inert tasks` with the frozen MBPP selection seed and reserves, then `inert propose`, `inert execute`, `inert core-set`, `inert thoughts`, and `inert build-items` with the frozen configs and Docker sandbox. Freeze the first 12 *ready* pilot tasks and 100 eligible items before any WM-A call, and record their IDs and hashes. The selection must not use Docker pass counts or expected model answers. The design says “any conditions” but does not specify how to distribute the 100 items across the 12 tasks. The current file-order slice could select all 100 from one task even when 12 tasks exist. The owner should specify the deterministic item-order rule before P0 input preparation; this audit did not choose one. The earlier instruction to keep P0 closed until the official WM-C smoke gate passes also remains in force.

## P0 implementation audit

- **Loading and offload:** `model_session` checks the model hash, binds the local server to `127.0.0.1`, uses context 8,192, and takes the frozen WM settings. Q4 tries 41 down to 0 GPU layers, stopping at the first loadable setting; Q3 uses 41 layers if the Q3 file exists. The server is lazy and local. Native reasoning output and true load feasibility cannot be proven offline.
- **Q3 fallback:** The former unconditional Q3 loop would fail with `FileNotFoundError` after a successful Q4 trial because Q3 is absent. P0 now tries Q3 only when its configured file is present. If Q4 cannot load and Q3 is absent, it stops for the owner without writing a false `drop_wm_a` result. If both builds exist and work, the faster measured trial remains selected as the design requires.
- **Preflight and errors:** P0 now requires 12 distinct task records before any model calls, as well as 100 eligible items. A missing Q4 file stops before a decision is written. OOM classification reads only the log named by the current server error; a stale OOM log cannot turn a port or lock failure into an offload retry. Non-OOM loading failures still stop. No threshold or decision rule changed.
- **Token escalation:** The frozen 1,024-token limit rises to 2,048 only when more than 5% of P0 calls finish at length without a visible `RESULT`. A wrong-denominator `RESULT` does not trigger escalation. The required deviation record now correctly says scoring had started after those calls. The parser and denominator rule are unchanged.
- **Measurement and conclusions:** P0 uses saved per-request HTTP latencies to compute median, p90, and throughput; server startup is outside those per-call timings. It samples GPU memory with `nvidia-smi` and now stops if no sample is available, rather than publishing a null peak. The registered `<=20`, `<=50`, and `>50` second decision bands are unchanged. The 10% parse-failure stop remains. A cache-only restart could still report only idle VRAM because the lazy server would not start; no P0 data exist yet, and this measurement limitation needs resolution before execution. Whether “time them end to end” includes server startup is also not explicit in section 10.

The code changes are confined to `src/inert/p0.py` and regression tests in `tests/test_p0_readiness.py`. No experimental threshold, seed, model identity, prompt, text condition, parser acceptance rule, or statistical rule changed. There is no new design deviation; the unresolved selection and timing questions are flagged here for owner clarification.

## Validation and preservation

| Check | Result |
| --- | --- |
| Targeted P0 tests | 5 new regression tests passed |
| Full pytest | **249 passed** in 61.36 seconds; log under `data/smoke/diagnostics/wm_a_p0_readiness_20261114/pytest_final.log` |
| Ruff lint | Passed |
| Ruff format | Passed; 63 files formatted |
| `git diff --check` | Passed |
| Historical preservation | 623 pre-inventoried files rehashed after validation; **0 changed or missing**. The earlier owner-accepted historical cache exception remains documented separately and was not rebaselined. |
| Inference or server start in this audit | None; no WM-A server lock or process was created. |

The complete Q4 weight and all new download/audit files remain under git-ignored `data/`. Neither historical smoke data nor pilot caches, scores, task records, or prompts were modified.

## Next authorized action

Resolve the 100-item ordering and cache-only VRAM measurement questions, and keep the official WM-C smoke gate closed unless separately authorized. Then authorize creation of the pilot inputs in design section 12.2 order. P0 execution requires 12 ready tasks, 100 frozen items, and a successful authorized gate; this report is **READY_FOR_P0_INPUT_PREPARATION**, not execution-ready.
