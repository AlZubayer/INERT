# Balanced assertion/execution diagnostic selection — 2026-11-12

## Selection status

**FROZEN_READY_FOR_48_CALL_DIAGNOSTIC.** Exactly eight fresh, uniquely identified MBPP candidates are selected, two in each Docker pass-count stratum. The selection is frozen in a SHA-256-verified local manifest. All eight recorded aggregate results were reproduced with the unchanged original three-test harness inside network-disabled Docker. No per-assertion oracle or world-model inference was run. The official smoke gate remains closed; P0 and pilot scoring remain unstarted.

## Eight frozen candidates

Selection order is by stratum `0/3`, `1/3`, `2/3`, `3/3`. Within `1/3`, the two explicitly approved acquisition-shortlisted candidates retain distinct tasks. Within every other stratum, the first two fresh candidate IDs in ascending lexical order were taken from the union of the original smoke pool and the acquisition pool. `acq-` sorts before `mbpp-`, so this rule selects eight acquisition candidates. No difficulty judgment or outcome-based exclusion was added beyond the prescribed stratum balance.

Every listed Docker output was present in the acquisition archive and was reproduced in a fresh aggregate Docker run. The listed SHA-256 values are for the exact stripped executable source and the ordered JSON array of all three original test strings, including any supplied imports. The latter uses UTF-8 JSON with `ensure_ascii=False` and separators `(",", ":")`.

| Rank | Candidate ID | Task | Docker output | Stripped-code SHA-256 | Original-tests SHA-256 |
|---:|---|---|---|---|---|
| 1 | `acq-mbpp-125-g06` | `mbpp-125` | `RESULT: 0/3` | `6b3757571f7b5efe0ee048f69fd1b979b9bb53c70a1009e5c770ac7bc88908b9` | `98c21f4e2af7b1d9b4ea1906d7c1b12ebc2efab6f66bd63279e53a1ff0be75ca` |
| 2 | `acq-mbpp-125-g07` | `mbpp-125` | `RESULT: 0/3` | `8ea1c1c85d11823334a8da5d8faed35ab094a37922bd24ef1d3fb64b5572f48a` | `98c21f4e2af7b1d9b4ea1906d7c1b12ebc2efab6f66bd63279e53a1ff0be75ca` |
| 3 | `acq-mbpp-563-g00` | `mbpp-563` | `RESULT: 1/3` | `e8f3ead65e325cf638e1e9921517543211ad1e12439e6fc4e071492443102a2b` | `f1237c800a3914aa74d2e27965c499981729caabf967a8885d403b2a49687f7b` |
| 4 | `acq-mbpp-622-g00` | `mbpp-622` | `RESULT: 1/3` | `8acd39c9c90b679904b5467a2d158e76af0bc59cfba18b8ad6eccb082496b51a` | `01aae2a121fdba46ba2268c63d05bc53df39b68623d510b90fba26c5a0dccad4` |
| 5 | `acq-mbpp-563-g10` | `mbpp-563` | `RESULT: 2/3` | `a4b9e6d9d6ac5c0d969ec9d30308912c8284f14befd050834163738996a84736` | `f1237c800a3914aa74d2e27965c499981729caabf967a8885d403b2a49687f7b` |
| 6 | `acq-mbpp-563-g13` | `mbpp-563` | `RESULT: 2/3` | `5ba350bd3f2f0147da456e0b07599429f7c22174b8f2a957094aa62378a9f937` | `f1237c800a3914aa74d2e27965c499981729caabf967a8885d403b2a49687f7b` |
| 7 | `acq-mbpp-125-g00` | `mbpp-125` | `RESULT: 3/3` | `9ce029fe958c6706f24634b75ed97dd3c99c636bd729851af259da796357bccf` | `98c21f4e2af7b1d9b4ea1906d7c1b12ebc2efab6f66bd63279e53a1ff0be75ca` |
| 8 | `acq-mbpp-125-g01` | `mbpp-125` | `RESULT: 3/3` | `cfb6edee691b7fe854e3bc04b2a2abf4a0468e9a3371a662e73dc4f0cca40ca5` | `98c21f4e2af7b1d9b4ea1906d7c1b12ebc2efab6f66bd63279e53a1ff0be75ca` |

All eight candidate IDs and stripped-code hashes are distinct. Their original task-record hashes are `de07a70146e90d683f18fd447c78ad6fdbe987f145b67576baed77bd1d712655` (`mbpp-125`), `cac2e1738d6c784959723163bda0642c938a26f6d033b912764acd1d70bb81ab` (`mbpp-563`), and `abbd1bd72a1f525bc4f147283be091de05b19eb7c95645e5aa4dd6aca7fbfb6a` (`mbpp-622`). Each raw proposer source also has its own SHA-256 in the manifest. Candidate and task record locations, generation index through the candidate record, selection rank, and recorded execution path are included there.

## Authorized clarification and freshness

The historical [blocked-selection report](Assertion_Execution_Diagnostic_20261112.md) used ascending candidate ID within every stratum. The owner subsequently authorized **one diagnostic-only clarification**: use the two acquisition-shortlisted `1/3` candidates, `acq-mbpp-563-g00` and `acq-mbpp-622-g00`, so that this newly available stratum spans distinct tasks. The ascending-ID rule remains in force for `0/3`, `2/3`, and `3/3`. This clarification changes no official pilot selection rule, frozen text condition, threshold, seed, parser, or decision rule. It was fixed before any WM-B/WM-C calls on these candidates.

The source reconciliation checked all **29** original smoke candidates and all **79** acquired candidates against their schema-validated raw/stripped code, task records, three-test strings, stored pass counts, and original execution records. IDs and stripped-code hashes are unique across all 108. The historical exposure audit, SHA-256 `6def12845d6b69f9179efd649d34d0ac79ac2934df50cd26ed3219f6c4ad2845`, marks five old candidates previously seen by a world model. The acquisition freshness audit, SHA-256 `a24bc890f40362a0e6cfcc3851fa52fea954c449fa80d76ced825e48a37ae2e9`, records no ID or code-hash overlap for the 79 new candidates.

For an independent check of new-source exposure, the selection stage verified the hashes of **28** historical evidence sources: three items files, four diagnostic manifests, four score files, and 17 WM response caches. It inspected scored item messages, completed manifest response cases, and **300** cached WM requests for exact candidate IDs, code hashes, and source text, including JSON-escaped newlines. There were **zero matches** for the 79 acquired candidates. The resulting pool has 54 fresh `0/3`, six fresh `1/3`, 12 fresh `2/3`, and 31 fresh `3/3` candidates; all eight frozen rows have empty prior-exposure evidence.

## Docker and source integrity

All eight candidates used their original generated source and the original three tests. Candidate schema validation checked that stripping each raw source reproduces its recorded executable source and code hash. Ordered test hashes and task hashes were checked again when the source archive was written. The network-disabled `python:3.11-slim` Docker image was `sha256:07d4824036af339fa1b6ef769cc99d9c10a141769538b52b3b597c84f7a7b535`, with 512 MB memory, one CPU, 64 PID limit, a read-only container, five seconds per test, and a 20-second wall limit. Fresh aggregate Docker stdout exactly matched each recorded `RESULT: k/3`; stderr was empty and return code was zero in all eight runs. Both `1/3` candidates also retain their earlier independent `RESULT: 1/1` import probes.

The `acq-mbpp-563-g00` proposer output contains a **top-level assertion for the shown first example**. It remains in both raw and stripped source. This can affect interpretation because the world model will see an assertion in `solution.py`; it is part of the real candidate and was neither edited nor used to exclude the candidate. Its function splits quoted values on `", "`, while the later original tests omit the space. Other selected candidates were retained solely by the fixed ID rule, with no manual code changes.

## Frozen records and methodological limits

The ignored local directory is `data/smoke/diagnostics/assertion_execution_20261112/selection_resume/`. Its artifacts are:

| Artifact | Purpose | SHA-256 |
|---|---|---|
| `selection_manifest.json` | Eight ranks, strata, IDs, hashes, source locations, rule, evidence links | `3aed60838f4c44dc5a8fa76b0bcf858ffb37f5d8de5c5ab8d267d0a50add37eb` |
| `source_archive.json` | Exact task prompts, raw/stripped candidate source, original tests; **no truth labels or selection annotations** | `e76c93a8483f370dc9d684d295264175739940355df79fbe37ceddceedd24378` |
| `oracle.json` | Recorded aggregate truth, fresh Docker rechecks, sandbox configuration and image ID; **evaluation only** | `b180a21fe9640783f9429b2e1040a0a53b89ea7441a53610f9b9f84079d49cfe` |
| `exposure_audit.json` | Full 108-candidate freshness pool and historical input scan | `837106ae86aaf0c7c76c7b6710fdd193e679f0b0561006ee4e1fb97d59a347a9` |
| `selection_manifest_checksum.json` | Manifest SHA-256 for later verification | `77bc50d3d07ec5002648183481210047cccbbbcc52b3e177a7f357538056b48d` |

The manifest also records source-file checksums for `data/smoke/{tasks,candidates,executions}.jsonl` and the acquisition archives. A repeated selection run produced the **same manifest SHA-256** without rerunning Docker. Future WM prompt construction must use the truth-free source archive, never the manifest's stratum labels or the separate oracle.

The eight rows cover only **three tasks**: four candidates from `mbpp-125`, three from `mbpp-563`, and one from `mbpp-622`. Candidates from the same task share tests and may have correlated prediction errors. Both `0/3` and both `3/3` rows come from `mbpp-125`; both `2/3` rows come from `mbpp-563`. The balanced sample was selected by executed outcome and lexical ID, so it is not a random or task-representative sample of generated solutions. No conclusion about WM reasoning follows from this selection alone.

Validation after freezing: `.venv\Scripts\python.exe -m pytest -q` **229 passed**; `.venv\Scripts\ruff.exe check src tests` **passed**; `.venv\Scripts\ruff.exe format --check src tests` **55 files already formatted**; `git diff --check` **passed**. Regression tests cover the deterministic ordering and balance, exposure exclusions, unique hashes, ordered original-test hashes, frozen writes, and local manifest/source/oracle reconciliation.

## Readiness

The previously blocked eight-candidate input set is **ready for the separately authorized 48-call assertion-reading/execution-reasoning diagnostic**. The selection and aggregate Docker verification are complete. The per-assertion Docker oracle, the three 16-call WM stages, and all diagnostic analysis remain unstarted. No official smoke, P0, or pilot scoring was resumed.
