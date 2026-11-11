# INERT pilot: next steps

Written 2026-11-11. Nothing below has been done yet.

The pilot decides whether the full INERT project is built. It should take about one week of one person's time plus GPU time. The specification is `Pilot_Experimental_Design.md`; section numbers below refer to it.

## Where things stand

- **Done:** literature review; revised research questions; channel audit of 11 published world-model pipelines (outcome: conditional pass; the channel exists, most clearly for agent reasoning in web and tool pipelines, with one code/terminal case).
- **Constraint:** no API budget. Everything runs on one local 16 GB GPU.
- **Not done:** any code, any model run, any result.

## Step 0: confirm the unknowns (half a day, no GPU)

These were not verified when the design was written. Resolve each one and record the answer in `configs/models.yaml` or `results/pilot/env.json`.

- [ ] `Qwen/Qwen-AgentWorld-35B-A3B` exists, its licence allows this use, and a GGUF build is available or can be converted.
- [ ] The installed llama.cpp supports that model's architecture.
- [ ] `Qwen/Qwen2.5-7B-Instruct`, `Qwen/Qwen2.5-1.5B-Instruct` and `Qwen/Qwen2.5-Coder-7B-Instruct` exist with GGUF builds; licences recorded.
- [ ] The MBPP sanitized dataset identifier is correct and loads.
- [ ] Licences of `QwenLM/Qwen-AgentWorld` and `microsoft/Simia-Agent-Training` allow copying their prompt text.
- [ ] The vendored prompt locations in section 7.3 match the pinned commits.
- [ ] Docker runs on the machine with `--network none`.

If any of these fails, stop and decide before going on. The one that matters most is the first.

## Step 1: build the pipeline (2 to 3 days, no GPU needed for most of it)

- [ ] Repository skeleton, `pyproject.toml`, configs (section 12.1).
- [ ] Schemas, config loader, paths.
- [ ] Sandbox and harness, with tests (sections 6.4, 6.6).
- [ ] Stripping, natural-text extraction, mutators, inertness checks, with tests (sections 6.5, 6.7).
- [ ] Text conditions and both channel renderers, with tests (sections 7, 8).
- [ ] Server lifecycle and cached client (sections 5.1, 12.3).
- [ ] Parser, with tests (section 9.5).
- [ ] Selection resampling, bootstrap, endpoints and decision rules, with tests on synthetic data (section 11).
- [ ] Report writer (section 14).
- [ ] All unit tests in section 12.4 pass.

## Step 2: smoke run (2 hours)

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
