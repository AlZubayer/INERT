# Step 0 verification

Status: PASS

| Check | Status |
| --- | --- |
| python_311 | PASS |
| gpu | PASS |
| llama_cpp_architecture_and_cuda | PASS |
| wm_a | PASS |
| wm_b | PASS |
| wm_c | PASS |
| proposer | PASS |
| mbpp_sanitized_load | PASS |
| mbpp_import_dependent_references | PASS |
| pinned_prompt_locations_and_licenses | PASS |
| docker_network_none | PASS |

Evidence and versions: `env.json`. Pinned identifiers, licences and model file
hashes: `../../configs/models.yaml`. Model hashes come from pinned LFS metadata;
local weight verification is mandatory before serving. WM-A loading and latency
remain untested until Step 3/P0. No inference or pilot scoring ran in Step 0.
