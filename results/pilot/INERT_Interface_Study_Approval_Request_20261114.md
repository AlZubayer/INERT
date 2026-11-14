# INERT-INTERFACE-001 — owner approval request

**Status: `PROTOCOL_LOCKED_PENDING_OWNER_APPROVAL` (version 1.0.0, prepared 2026-11-14).** The full proposed preregistration is [INERT_Interface_Study_Protocol_20261114.md](INERT_Interface_Study_Protocol_20261114.md). Publication locks a design; it authorizes **no** model call.

## Decision requested

**Recommendation:** Approve only the **48-assignment development phase** of the new, bounded WM-B interface-validity study after reviewing the choices below. Require a separate owner unlock for the 144 held-out assignments after the development audit. This is preferable to resuming WM-A P0 or repeatedly adapting WM-C prompts because it directly checks whether a local world model can produce finalized, discriminating test-count predictions under a fixed interface. If this preparatory definition of “held-out” or any new threshold is unacceptable, withhold approval and amend the protocol **before** inference.

## Why the original pilot is paused

WM-A P0 stopped at 62/100 original responses and 61 matching live VRAM measurements; its 1,024-token responses had 53/62 parse failures. WM-B's separate three-task engineering run parsed 198/198 responses but got only 68/198 exact test counts, with Channel-D T0 balanced accuracy 0.50. The official WM-C smoke gate remains closed. The [viability assessment](INERT_Research_Viability_Assessment_20261114.md) assigned no official P0 or KT verdict. These records motivate a new interface study; they are not its results.

## What is proposed

| Item | Locked proposal |
| --- | --- |
| Study/model | `INERT-INTERFACE-001`; local `Qwen/Qwen2.5-7B-Instruct` Q4_K_M; two pinned shards and llama-server hash in protocol/manifest |
| Interfaces | **A:** unchanged official vendored T0 renderings. **B:** one new direct execution-prediction template with separate C and D payload wrappers and a final `RESULT: k/n` contract |
| Population | Six already exposed development tasks; 18 distinct held-out tasks from the official 50 after task-level world-model exposure exclusion; one Docker-verified passing and one failing core candidate each |
| Assignments | 48 development + 144 held-out = **192 maximum**; 12 or 36 assignments per interface/channel cell by phase |
| Allocation | **Three cumulative live HTTP GPU-hours** across both phases, 300-second reservation before each call, one local server at a time; startup and offline verification logged separately |
| Decoding | Temperature 0, top-p 1, seed 0, max tokens 1,024, context 8,192; no setting search during execution |
| Stage gate | Development stops after 48. Any cell with ≥2/12 finalized-answer failures, or any integrity/measurement fault, stops the study. A clean development audit still requires **new owner authorization** before held-out calls. |

The archived WM-B engineering calls had P90 HTTP latency 6.23 s; multiplying by 192 suggests about 0.33 HTTP hours as a rough planning point, **not a guarantee** for the new interface/tasks. The proposed three-hour cap leaves room for slower responses while bounding total inference. If the model uses the full 300-second timeout repeatedly, the cap would stop the study early and the result would be `INCONCLUSIVE`.

## Success and limits

For each held-out interface/channel cell, the **proposed new-study** criteria are finalized-answer validity ≥95% (at least 35/36), assignment-level balanced accuracy ≥0.65, correct identification of ≥50% of failing candidates (at least 9/18), assignment-level exact-count accuracy ≥50% (at least 18/36), and no unresolved truth/measurement integrity failure. Invalid predictions count as wrong for assignment-level accuracy. The unchanged legacy parser validity, conditional accuracy among finalized responses, and a deterministic always-pass baseline are reported separately. Task-cluster bootstrap intervals use 10,000 resamples, seed 0, for uncertainty context; they do not move cutoffs.

`INTERFACE_READY` means at least one specified interface/channel cell meets every criterion. `INTERFACE_LIMITED` means none is ready but a cell meets both balanced accuracy and failing-specificity cutoffs; report missing criteria. `INTERFACE_NOT_READY` means complete measurements with neither. `INCONCLUSIVE` means incomplete, violated, or materially untrustworthy measurements. Success would justify **designing a later, separately preregistered inert-text experiment** for only the supported channel(s); it would not pass the frozen smoke gate or establish KT-A/B/C. Limited success would identify the blocking metric and require a new design decision. Failure would argue against treating this local WM-B interface as an execution predictor. No category retroactively changes the original pilot.

## Frozen preparation and provenance

Offline preparation completed with **no inference**. The registry found 11 previously world-model-exposed task IDs, **nine within the official 50**, leaving 41 eligible unexposed official tasks before the seeded 18-task draw. The six development and 18 held-out IDs, 48 selected candidate truth records (kept separate), 192 exact model-facing message lists and their SHA-256 values, model/server settings, source hashes, and assignment order are frozen under ignored `data/interface_study_001/`. A's messages matched the unchanged official T0 items, and all 192 prompts passed the numeric-result leakage scan. The model shards and server binary were rehashed locally. The ignored directory is **not** to be committed. The publication commit for the protocol is discoverable through Git history for its path.

| Identity | SHA-256 |
| --- | --- |
| Canonical protocol (UTF-8, LF normalized) | `40d69ac197f741e7153adeabf9d34786dff7d899fe677748471f17deeeed7ee1` |
| Assignment manifest (canonical JSON, excludes its hash field) | `f7f3cf6dc46de9ccb48859b2f7c6cd7e0bccd8c9107fc182383494b4f4157d16` |
| Task split (canonical JSON) | `cc31a8169d90858091b844ce547d739838e6315b278affffe86e04ee37406ab5` |
| Exposure registry (canonical JSON) | `d671188df422f3c972d70e07d4555ed435749e51289771219e9f6e4f7e8cfbbb` |

The full protocol records the three B-template hashes and exact model, server, and analysis-plan versions. A future authorized runner must verify these hashes before any call. The pure offline preparation module does **not** contain an inference loop.

## Methodological choices requiring explicit approval

1. **Exposure definition:** “Held-out” excludes any task with a completed prior **world-model outcome-prediction** response in the audited archives. It does not exclude tasks seen by the separate code proposer during candidate generation; all official pilot tasks were proposer-exposed. Public MBPP pretraining exposure is unknown. If “never shown to any model” is required, the official 50-task sample cannot supply this held-out set.
2. **New interface and output metric:** B bundles task-focused framing, an explicit denominator, and a one-line final-answer instruction. The study-only finalized-answer metric rejects numeric results in unfinished reasoning and all `length` finishes; it does not alter `src/inert/parse.py`.
3. **New thresholds and decision categories:** The 95%/0.65/50%/50% criteria and `READY/LIMITED/NOT_READY/INCONCLUSIVE` categories are for this engineering study only. They are not the original pilot's preregistered thresholds.
4. **Resource/stage authorization:** Approve at most 48 development calls now under the three-hour shared cap, with a mandatory stop and owner review before any of the 144 held-out calls. No automatic prompt edits, model changes, candidate swaps, or task reselection follow a development failure.

**Approval state:** Pending. The owner should approve or request a versioned change to these four choices before any local inference. After a development audit, the owner must separately decide whether to unlock the fixed held-out phase. A Git commit is not approval.
