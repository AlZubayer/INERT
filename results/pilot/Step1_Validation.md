# Step 1 implementation validation

Status: PASS. Pilot inference and experimental results have not run.

## Checks performed

- Full test suite: 156 passed, 0 failures, 0 errors, 0 skipped.
- Ruff lint and format checks: PASS.
- Public function annotations: PASS.
- Docker sandbox cleanup: no remaining INERT containers.
- Import-dependent MBPP references: 13 of 13 passed in Docker with the approved supplied imports.
- inert verify-env: PASS; evidence is recorded in env.json.

## Coverage

Tests cover stripping and behavioral preservation on the prescribed hand-written
samples; all fixed text conditions and both channels; static and dynamic
inertness; parser failures and denominator checks; sandbox passing, failing,
syntax-error, infinite-loop, network, read-only-root and cleanup cases; model
hash validation; cached requests and recovery; exclusive server ownership and
shutdown; task token boundaries and imports; core selection; item generation
and reruns; paired analyses; decision-rule boundaries; seeded task bootstrap
and selection; interruption recovery with exact generator states; equal task
weighting for enrichment with zero-claim and unequal-sized pools; report
provenance; reduced WM-A planning; and isolation of the smoke profile.

Candidate and harness fixtures execute only through src/inert/sandbox.py.
HTTP/model responses in unit tests are explicitly synthetic fixtures. They are
not pilot observations.

## Traceable artifacts

- step1_validation.json: machine-readable validation record and source hashes.
- ../../data/verification/pytest.xml: actual full-suite results.
- ../../data/verification/quality_checks.json: lint, format, annotation and cleanup evidence.
- ../../data/verification/import_reference_checks.json: raw reference-check outputs.
- env.json: Step 0 checks, versions, source revisions, licences and hashes.

Raw data and tool caches remain ignored by Git. Unit-test reports and synthetic
score fixtures are isolated under data/pytest-tmp/.

## Remaining experimental stages

Model GGUF hashes are pinned from upstream LFS metadata; weights have not been
downloaded or loaded. Every local shard must pass its SHA-256 check before
serving. The real three-task WM-C smoke run, WM-A P0, and pilot scoring have
not run. No pilot p0.json, summary.json, or Pilot_Results.md is asserted by
this validation.

The frozen design is unchanged. Approved pre-scoring clarifications are
recorded in deviations.md.
