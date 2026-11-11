# INERT pilot

INERT tests whether inert agent text changes a local world model's predictions.
The frozen specification is [Pilot_Experimental_Design.md](Pilot_Experimental_Design.md).
Implementation status is tracked in [Pilot_Next_Steps.md](Pilot_Next_Steps.md).

## Setup

Use Python 3.11, Docker with Linux containers, and a CUDA build of llama.cpp.
Create a virtual environment and install the project with its development tools:

```powershell
py -3.11 -m venv .venv
.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

This workspace also has managed Python, uv, and the verified llama.cpp binaries
under the ignored `data/tools/` directory. Its existing virtual environment is
ready to use. The executable path and verified upstream revisions are recorded
in `configs/models.yaml`.

Model weights are not downloaded by verification. Download the exact GGUF files
listed in `configs/models.yaml` to their listed paths before running inference
or the CPU task tokenizer. Every shard is checked against its recorded SHA-256
before serving. WM-A's GPU offload setting is determined by P0.

```powershell
.venv\Scripts\inert.exe verify-env
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\ruff.exe check src tests
.venv\Scripts\ruff.exe format --check src tests
```

`verify-env` records real checks in `results/pilot/env.json`. Its `--offline`
option reuses downloaded metadata and dataset files, and repeats local checks.
Docker must be running and the prescribed `python:3.11-slim` image must be present.

## Stages

Each command writes explicit artifacts and can be rerun. Prepare tasks, propose
candidates, execute them, select the core set, generate thoughts, and build items:

```powershell
.venv\Scripts\inert.exe tasks
.venv\Scripts\inert.exe propose
.venv\Scripts\inert.exe execute
.venv\Scripts\inert.exe core-set
.venv\Scripts\inert.exe thoughts
.venv\Scripts\inert.exe build-items
.venv\Scripts\inert.exe p0 --wm wm_a
```

For the required smoke run, add the global `--smoke` option to each preparation
command. It selects three tasks, scores WM-C, and isolates its data and reports
from the pilot. P0 uses WM-A and is outside the smoke profile.

```powershell
.venv\Scripts\inert.exe --smoke score --wm wm_c --block kt_ab
.venv\Scripts\inert.exe --smoke score --wm wm_c --block kt_c
.venv\Scripts\inert.exe --smoke analyze
.venv\Scripts\inert.exe --smoke report
```

For the pilot, score `kt_ab` with WM-B, WM-C, then WM-A. A P0 drop or reduced
decision is applied to WM-A. Run `analyze` to inspect the preliminary KT-A verdict.
The `score --block kt_c` command skips KT-C when KT-A is KILL. After permitted
selection scoring, run `analyze` and `report` again.

The report checks that its source records still match the analysis hashes.
Missing results stay unavailable. Reports do not turn an unrun stage into a
negative experimental result.

## Execution and recovery

Candidate solutions, reference solutions, and generated harnesses execute only
through `src/inert/sandbox.py`. Containers receive exactly `solution.py` and
`run_tests.py` in tmpfs, have networking disabled, and use a read-only root,
resource limits, and an unprivileged user. There is no automatic host fallback.

Prompts and raw responses are stored in SQLite caches under `data/cache/`.
Cache hits do not start an inference server. Stage logs are under `data/logs/`.
Selection bootstrap checkpoints include generator states so interruption and
resumption produce the same result. JSONL records are validated on both read
and write; checkpoints are replaced atomically.

An active server owns `data/server.lock`, shared by pilot and smoke profiles.
Normal exit and errors stop that server and release the lock. After an abrupt
process or machine failure, inspect the recorded PID before removing a stale
lock; do not launch a second GPU model over a surviving server.

Approved pre-scoring clarifications are recorded in
[results/pilot/deviations.md](results/pilot/deviations.md). No pilot inference,
smoke run, or P0 result is claimed by the implementation tests.
