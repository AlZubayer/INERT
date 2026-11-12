# Fresh candidate acquisition for the assertion/execution diagnostic

## Executive finding

**Acquisition succeeded; `READY_FOR_SELECTION_REVIEW`.** Five of the eight fixed MBPP task batches were processed. The fifth completed batch triggered the authorized early stop because there were importable `1/3` candidates from two different tasks. The local proposer made **80/128** possible calls, yielding **79** unique syntax-valid candidates and **79** original-three-test Docker executions. Six candidates returned exactly `RESULT: 1/3`, five from `mbpp-563` and one from `mbpp-622`; all six passed a separate Docker import probe. The balanced fresh-candidate pool is now available for a separately authorized selection review.

This acquisition made **zero WM-B or WM-C diagnostic calls**. It did not resume the blocked 48-call experiment, change the official smoke gate, or begin P0 or pilot scoring.

## Selection provenance

The source was the pinned `google-research-datasets/mbpp` **sanitized** configuration at revision `4bb6404fdc6cacfda99d4ac4205087b89d32030c`. Its four locally verified parquet SHA-256 hashes were:

| Split | SHA-256 |
|---|---|
| prompt | `73c623309b7b5d65fd5661204b35f779f8e66301aa9832d1ad4b8fc3b21151fd` |
| test | `e9e9efa2c0d59ef5e55537a9d126b8f875d5ac010a8d75628d76824884e15850` |
| train | `d95f8ad6d2fff08fe4826122d6e3e31f75716825d0c5c340d297aca5e9e0de0e` |
| validation | `27e065fcab3c863959933328a7fdbf404e1bcb5464b1be6fe0dcd9530e420204` |

All 427 source rows were reconciled against the existing hash-keyed task filter: 392 were eligible and unused, 30 lacked exactly three assertions, two needed forbidden external state, and three were already used by smoke or diagnostics. The approved safety check and strict `<1,500`-token filter covered the prompt, reference code, and complete original tests. Selected tasks were retokenized with the pinned Qwen2.5-Coder-7B tokenizer; their reference solutions were independently rerun in network-disabled Docker and all returned `RESULT: 3/3`. The previous diagnostic selection audit, including its earlier smoke scores, archives, manifests, and model-response caches, was verified at SHA-256 `6def12845d6b69f9179efd649d34d0ac79ac2934df50cd26ed3219f6c4ad2845`. No pilot task sample existed, so there was no pilot overlap.

The complete eligible ID list was sorted by task ID, shuffled with `random.Random(20261111)`, and the first eight were frozen **before proposer inference**. These are the fixed order and task-record hashes; the final three were not generated because the early-stop condition fired after task five.

| Order | Task ID | Task SHA-256 | Token count | Processed |
|---:|---|---|---:|---|
| 1 | `mbpp-125` | `de07a70146e90d683f18fd447c78ad6fdbe987f145b67576baed77bd1d712655` | 174 | Yes |
| 2 | `mbpp-603` | `36363aefd6edc39b2d4fc9689ab20e228a04d46d2c8aa0c6561246e51ebf70ad` | 261 | Yes |
| 3 | `mbpp-237` | `8489e92218596e7dafce4d2ec3bdbf8a8616ab2e03a9c7d4784360181c83eb42` | 284 | Yes |
| 4 | `mbpp-563` | `cac2e1738d6c784959723163bda0642c938a26f6d033b912764acd1d70bb81ab` | 96 | Yes |
| 5 | `mbpp-622` | `abbd1bd72a1f525bc4f147283be091de05b19eb7c95645e5aa4dd6aca7fbfb6a` | 337 | Yes |
| 6 | `mbpp-434` | `75c5f2bccbb50cef4bd93f846bada91b8b623bc538bf0b26562e5e24a0ca05e3` | 84 | No |
| 7 | `mbpp-632` | `7de7a42a3b9cc7412ad1fb7834e3f2940e49c10f91c93e884b82916a0254a9f7` | 157 | No |
| 8 | `mbpp-103` | `6e4e6c05f7e4a7cd05c0b8df83e36cd4bd20ecb49a6e37a5e0f2dbc0de15f5bc` | 133 | No |

The ignored local evidence is under `data/smoke/diagnostics/assertion_candidate_acquisition_20261112/`. SHA-256: eligibility audit `ed40f87ef4c8d8fbb22f15b06a3ce1e56d9346376c7a2523eee0864374475bb7`; task-selection manifest `463429468e371ac5cb4b9ab2ee3ecf885004f5b5392312ce7c17cf6b302d91e4`; fixed 128-attempt manifest `e558de4d853f2537e894bd6eb3f7b10cf166ca27af5a80f5fba080d9824906eb`; eight reference Docker checks `d1cff5d31e4dbc1e1862659f76cd89d44494880a4affb6c7acc270444b42744f`.

## Generation and Docker outcomes

The unchanged `prompts/inhouse/proposer_code.txt` had SHA-256 `195f113c64109060e69b27454b1940441fe794123faf3fea1b01eda9b1b01d0b`. The pinned local `Qwen/Qwen2.5-Coder-7B-Instruct` Q4_K_M GGUF had SHA-256 `509287f78cb4d4cf6b3843734733b914b2c158e43e22a7f4bf5e963800894d3c` and Apache-2.0 license. Sampling used temperature `0.8`, top-p `0.95`, maximum completion `768`, context `8192`, and exactly 16 attempts per completed task. Each fixed seed was `1000 + task_index × 100 + generation_index`, where task index is zero-based in the table above. The manifest contains the exact two-message proposer input and input hash for every possible attempt. The proposer saw each task prompt and the original first test, as in the existing pipeline; it was not told a target pass count.

All 80 completed calls were new cache misses. Response archives preserve the raw API body, raw completion, extracted code, finish reason, token counts, and fixed input hash. There were **0 malformed responses**, **0 syntax failures**, **1 duplicate stripped-code hash**, and **79 accepted unique candidates** (98.75% of calls). The duplicate was `acq-mbpp-237-g10`, hash `ed2b45a439bb8f7862503491fddd556f68c2baa92a4aa91ec5be7a6357ca0a1d`. Existing extraction and comment/docstring stripping were reused; no generated source was edited. Deduplication included the original 29-candidate pool.

Every accepted candidate was run against its task's three unmodified assertions through the existing Python 3.11, network-disabled Docker sandbox and harness. Results below reconcile to 79 accepted candidates and 79 Docker executions. An import-only Docker probe was additionally recorded for `0/3` and `1/3` candidates.

| Task ID | Accepted candidates | 0/3 | 1/3 | 2/3 | 3/3 | Unusable |
|---|---:|---:|---:|---:|---:|---:|
| `mbpp-125` | 16 | 3 | 0 | 0 | 13 | 0 |
| `mbpp-603` | 16 | 16 | 0 | 0 | 0 | 0 |
| `mbpp-237` | 15 | 15 | 0 | 0 | 0 | 0 |
| `mbpp-563` | 16 | 3 | 5 | 2 | 6 | 0 |
| `mbpp-622` | 16 | 6 | 1 | 4 | 5 | 0 |
| **Total** | **79** | **43** | **6** | **6** | **24** | **0** |

## Qualifying `1/3` candidates and freshness

Every row below has original-three-test Docker stdout **`RESULT: 1/3`**, return code `0`, and a successful independent import probe with stdout **`RESULT: 1/1`**, empty stderr, and return code `0`. The freshness audit compared both IDs and stripped-code hashes of all 79 new candidates with the 29-candidate prior smoke pool; none overlapped. That prior audit had already traced candidate exposure through historical scores, items, diagnostic manifests, and archived WM-B/WM-C caches. The new task IDs are also outside the three earlier smoke tasks. The separate freshness archive SHA-256 is `a24bc890f40362a0e6cfcc3851fa52fea954c449fa80d76ced825e48a37ae2e9`.

| Candidate ID | Task | Generation index | Seed | Stripped-code SHA-256 | Shortlist |
|---|---|---:|---:|---|---|
| `acq-mbpp-563-g00` | `mbpp-563` | 0 | 1300 | `e8f3ead65e325cf638e1e9921517543211ad1e12439e6fc4e071492443102a2b` | Yes |
| `acq-mbpp-563-g01` | `mbpp-563` | 1 | 1301 | `5541416f31b8a0e0e87ada666f041533815acf70a71868a32c5a4f7f5e122cc6` | No |
| `acq-mbpp-563-g05` | `mbpp-563` | 5 | 1305 | `b8571c1652dcc4bfdbf11fb698c5b58c05e9a8c303bf1234f17ffed9f07cc0a3` | No |
| `acq-mbpp-563-g09` | `mbpp-563` | 9 | 1309 | `aee7f635c9f3690d8e7bcfc7fd7c436729a802e4a18dc7ade50582ef14b24c55` | No |
| `acq-mbpp-563-g14` | `mbpp-563` | 14 | 1314 | `4235700ff22b78fd71900eff4d079bc37b2774d8e32dcf594ab10c12a9187447` | No |
| `acq-mbpp-622-g00` | `mbpp-622` | 0 | 1400 | `8acd39c9c90b679904b5467a2d158e76af0bc59cfba18b8ad6eccb082496b51a` | Yes |

The deterministic distinct-task shortlist is `acq-mbpp-563-g00` followed by `acq-mbpp-622-g00`: earliest fixed task order, then earliest generation index, with unique code hashes. The other four qualifying candidates remain archived. This is an acquisition shortlist only; the original eight-candidate diagnostic matrix has not been selected.

The first shortlisted source implements `extract_values` by splitting on `", "` and stripping quotes. It includes the proposer's own top-level assertion for the first example; it was preserved exactly. The task's three original tests use `"Python", "PHP", "Java"`, then `"python","program","language"`, then `"red","blue","green","yellow"`. The source's delimiter assumption gives a concrete reason to expect different behavior across these inputs. The second shortlisted source implements `get_median` with two sorted-list pointers and a final `count % 2` branch. Its unmodified tests request medians for list sizes 5, 4, and 6, with expected values `16.0`, `8.5`, and `25.0`. Both are real proposer outputs whose aggregate pass count was independently established in Docker; no per-assertion outcome is inferred here.

## Full-pool readiness and limits

The earlier untouched pool contained 11 unexposed `0/3`, zero `1/3`, six `2/3`, and seven `3/3` candidates. Adding the 79 new unique Docker-classified candidates yields:

| Executed stratum | Earlier unexposed | New | Combined fresh | Required |
|---|---:|---:|---:|---:|
| 0/3 | 11 | 43 | **54** | 2 |
| 1/3 | 0 | 6 | **6** | 2 |
| 2/3 | 6 | 6 | **12** | 2 |
| 3/3 | 7 | 24 | **31** | 2 |

**`READY_FOR_SELECTION_REVIEW`** means the original two-per-stratum requirement can be met; it does not assert that the diagnostic or official smoke gate passed. The acquisition deliberately selected on Docker outcomes, so this pool is enriched for the desired `1/3` stratum. The six successes came from only two task families, five from one, and the early stop left three preselected tasks ungenerated. These facts limit task diversity and any population-level inference. Docker pass counts also do not predict WM-B or WM-C accuracy. No result here is a world-model score.

## Validation and recommendation

The isolated workflow preserves the pinned dataset, proposer prompt, generation settings, original assertions/imports, existing sandbox, and all earlier smoke and pilot data. Local response, candidate, execution, reference, and freshness archives remain under the ignored acquisition directory; nothing under `data/` is included in the publication.

Final local validation: `.venv\Scripts\python.exe -m pytest -q` **224 passed**; `.venv\Scripts\ruff.exe check src tests` **passed**; `.venv\Scripts\ruff.exe format --check src tests` **53 files already formatted**; `git diff --check` **passed**. The analysis record SHA-256 is `c1748f13ecbe4817218493110e0430560b3970ed6437c1ffc46e8190b6daef24`. Independent record reconciliation found 80 non-cached proposer responses, all with finish reason `stop` and nonempty raw bodies, plus 79 usable Docker execution records. No proposer server was left running.

**Recommendation:** review the deterministic fresh-candidate shortlist and the original diagnostic selection rule, then authorize a separate run of candidate selection for the previously blocked diagnostic if appropriate. **Zero WM-B/WM-C diagnostic calls were authorized or performed in this acquisition.** The official smoke gate remains closed; P0 and pilot scoring are unstarted.
