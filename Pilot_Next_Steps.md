# INERT pilot: next steps

Written 2026-11-11. Implementation status updated 2026-11-12. Steps 0 and 1 are
complete. The isolated smoke run stopped at the parse-failure gate; P0, full
dataset generation, and pilot scoring have not run.

The pilot decides whether the full INERT project is built. It should take about one week of one person's time plus GPU time. The specification is `Pilot_Experimental_Design.md`; section numbers below refer to it.

## Where things stand

- **Done:** literature review; revised research questions; channel audit of 11 published world-model pipelines (outcome: conditional pass; the channel exists, most clearly for agent reasoning in web and tool pipelines, with one code/terminal case).
- **Constraint:** no API budget. Everything runs on one local 16 GB GPU.
- **Implemented:** Step 0 verification and the Step 1 pipeline. See
  `results/pilot/Step0_Verification.md` and `results/pilot/Step1_Validation.md`.
- **In progress:** the three-task smoke pipeline prepared tasks, candidates,
  ground truth, thoughts, and items. WM-C smoke scoring was stopped after the
  Channel-D prompt repair failed the parse gate (see Step 2 below).
- **Not done:** a complete smoke run, P0, full pilot data generation, or
  experimental results.

## Step 0: confirm the unknowns (half a day, no GPU)

These were not verified when the design was written. Resolve each one and record the answer in `configs/models.yaml` or `results/pilot/env.json`.

- [x] `Qwen/Qwen-AgentWorld-35B-A3B` exists, its licence allows this use, and a GGUF build is available or can be converted.
- [x] The installed llama.cpp supports that model's architecture.
- [x] `Qwen/Qwen2.5-7B-Instruct`, `Qwen/Qwen2.5-1.5B-Instruct` and `Qwen/Qwen2.5-Coder-7B-Instruct` exist with GGUF builds; licences recorded.
- [x] The MBPP sanitized dataset identifier is correct and loads.
- [x] Licences of `QwenLM/Qwen-AgentWorld` and `microsoft/Simia-Agent-Training` allow copying their prompt text.
- [x] The vendored prompt locations in section 7.3 match the pinned commits.
- [x] Docker runs on the machine with `--network none`.

Model file hashes are pinned from upstream LFS metadata and checked locally
before serving. WM-C and proposer weights were downloaded and hash-verified for
the smoke run. The WM-A Q4 download is incomplete; WM-B and WM-A Q3 weights are
not downloaded. The WM-A loading and latency gate remains Step 3/P0.

If any of these fails, stop and decide before going on. The one that matters most is the first.

## Step 1: build the pipeline (2 to 3 days, no GPU needed for most of it)

- [x] Repository skeleton, `pyproject.toml`, configs (section 12.1).
- [x] Schemas, config loader, paths.
- [x] Sandbox and harness, with tests (sections 6.4, 6.6).
- [x] Stripping, natural-text extraction, mutators, inertness checks, with tests (sections 6.5, 6.7).
- [x] Text conditions and both channel renderers, with tests (sections 7, 8).
- [x] Server lifecycle and cached client (sections 5.1, 12.3).
- [x] Parser, with tests (section 9.5).
- [x] Selection resampling, bootstrap, endpoints and decision rules, with tests on synthetic data (section 11).
- [x] Report writer (section 14).
- [x] All unit tests in section 12.4 pass.

Approved pre-scoring clarifications, including task tokenization, test imports,
and task-weighted enrichment, are recorded in `results/pilot/deviations.md`.
The full experimental design and its pre-registered values remain unchanged.

## Step 2: smoke run (2 hours)

Status on 2026-11-12: preparation and inertness checks completed for three
tasks. The first WM-C smoke scoring attempt had 9 parse failures in 20
persisted records, all in Channel D. A single owner-approved Section 9.5
prompt-adaptation repair was applied. In the interrupted rerun, Channel C had
2 failures in 18 records (11.1%) and Channel D had 4 in 12 (33.3%). Scoring
stopped as required; no further prompt adjustment or later stage has run.
See `results/pilot/deviations.md` for exact changes and cache handling.

- [ ] 3 tasks, WM-C only, every stage end to end.
- [ ] Open 10 rendered items by hand and read them. Check the text sits where it should and the `T0` items have no leftover artefacts.
- [ ] Check the report's numbers trace back to score records.

## Step 3: P0 feasibility gate (1 to 2 hours)

- [ ] Load WM-A; record offload setting and peak VRAM.
- [ ] Time 100 calls; record median and 90th-percentile latency and parse-failure rate.
- [ ] Apply the table in section 10: full design, reduced design, or drop WM-A.

## Step 4: generate data (half a day)

- [ ] Tasks, candidates, ground truth, core set, thoughts, items (stages 1 to 6).
- [ ] Dynamic inertness check passes for every core-set item.
- [ ] Record: tasks dropped, candidate pass rate, mutants used, share of candidates with empty natural text.

Watch for this: if most candidates have no comments at all, KT-B's primary endpoint and KT-C rung A will have little data. Report the share; do not change the proposer prompt to force comments.

## Step 5: score (GPU time; overnight runs)

- [ ] WM-B: KT-A/KT-B block, then check the validity precondition (section 11.2) before continuing.
- [ ] WM-C: KT-A/KT-B block.
- [ ] WM-A: KT-A/KT-B block.
- [ ] Preliminary KT-A verdict. If `KILL`, skip KT-C.
- [ ] KT-C blocks for WM-B, then WM-A (WM-C optional).

Rough GPU time, as estimates only: WM-B and WM-C a few hours each; WM-A anywhere from about 10 to about 38 hours depending on P0.

## Step 6: analyse and report (half a day)

- [ ] `inert analyze`, `inert report`.
- [ ] Read the ten example items in the report by hand.
- [ ] Commit `results/pilot/`.

## What to hand back

Send `results/pilot/Pilot_Results.md`, `results/pilot/summary.json` and `results/pilot/deviations.md`. The first line of the results file must be the decision row from section 11.6.

## What happens after, by outcome

| Pilot outcome | Next action |
| --- | --- |
| Build the full project | Update the proposal to the local-only, two-channel design. Scale to about 300 tasks. Add the LLM text-search rung, held-out-task and cross-model transfer, the neutralisation operators and the consistency detector. Consider the identifier channel and the reward-judge call as separate measurements. |
| Build a reduced project | Same as above without RQ3; present "pass only parsed actions and stripped code to the world model" as the defence. Expect a lower-tier venue. |
| Borderline (amplifies without harm) | Rerun KT-C on 100 tasks, once. Then decide. |
| Marginal on KT-A | Extend KT-A to 100 tasks, once. Then re-apply the decision table. |
| Weak tier only | Stop, or pivot to a short negative-result note: purpose-built and medium open world models resist inert agent text in this setting. |
| Stop | Write a one-page record of what was tested and found, so the idea is not re-attempted blind. |
| Inconclusive (all cells invalid) | Change the task set (harder if at ceiling, easier if at chance) and rerun KT-A only. |

## Open questions for the project owner

1. **If WM-A cannot run locally, is a pilot without a strong tier still worth the week?** My view: yes for a go/no-go on the mechanism, but a pass would then be weaker evidence.
2. **Is a "reduced project" outcome worth pursuing**, or is main-track potential a requirement?
3. **Who reads the ten example items?** A human check on them is the cheapest guard against a pipeline bug producing a false pass.
4. **Scoop watch.** Repeat the literature search weekly while the pilot runs. Closest known work: False Prophets (comment-based attacks on text world models, external attacker), Gaming the Judge (fixed-action reasoning rewrites against judges), CodeCrash (misleading comments in code reasoning).

## Things the pilot deliberately leaves out

- Frontier or hosted models.
- Training or fine-tuning of any model.
- Web-navigation tasks and real tool environments.
- The reward-judge call as a separate target.
- Identifier names, commit messages and string literals as text channels.
- Defences beyond measuring the cost of stripping.
