import hashlib
import json
import platform
import subprocess
from datetime import UTC, datetime
from importlib import metadata
from typing import Any

import httpx
import yaml

from inert.audit import StopRequired, stage_log
from inert.config import Paths, load_config
from inert.harness import render_harness
from inert.models import load_models
from inert.sandbox import DockerSandbox
from inert.schemas import atomic_text, write_json


def _fetch(paths: Paths, name: str, url: str, offline: bool) -> bytes:
    target = paths.data / "verification" / name
    if offline:
        return target.read_bytes()
    with httpx.Client(timeout=60, follow_redirects=True, trust_env=False) as client:
        response = client.get(url)
        response.raise_for_status()
    atomic_text(target, response.content.decode("utf-8"))
    return response.content


def load_mbpp(paths: Paths, registry: dict[str, Any], offline: bool = False) -> Any:
    from datasets import load_dataset

    source = registry["dataset"]
    files: dict[str, list[str]] = {}
    for entry in source["files"]:
        filename = entry["filename"]
        if not filename.endswith(".parquet"):
            continue
        target = (paths.data / "datasets" / filename).resolve()
        if not target.is_relative_to(paths.data.resolve()):
            raise ValueError("Unsafe dataset path.")
        if not target.exists():
            if offline:
                raise FileNotFoundError(target)
            url = f"https://huggingface.co/datasets/{source['id']}/resolve/{source['revision']}/{filename}"
            with httpx.Client(timeout=60, follow_redirects=True, trust_env=False) as client:
                response = client.get(url)
                response.raise_for_status()
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(response.content)
        content = target.read_bytes()
        actual = hashlib.sha256(content).hexdigest()
        if entry.get("sha256") and actual != entry["sha256"]:
            raise ValueError(f"Dataset SHA-256 mismatch: {filename}")
        # LFS blobId identifies the Git pointer, not the downloaded parquet bytes.
        if not entry.get("sha256") and entry.get("git_blob") and len(entry["git_blob"]) == 40:
            blob = hashlib.sha1(f"blob {len(content)}\0".encode() + content).hexdigest()
            if blob != entry["git_blob"]:
                raise ValueError(f"Dataset Git blob mismatch: {filename}")
        entry.update(sha256=actual, local_verified=True)
        split = target.name.split("-", 1)[0]
        files.setdefault(split, []).append(str(target))
    return load_dataset(
        "parquet", data_files=files, cache_dir=str(paths.data / "datasets" / "arrow")
    )


def verify_environment(paths: Paths, offline: bool = False) -> dict[str, Any]:
    config, registry = load_config(paths), load_models(paths)
    result: dict[str, Any] = {
        "timestamp": datetime.now(UTC).isoformat(),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "packages": {
            name: metadata.version(name)
            for name in [
                "pydantic",
                "pyyaml",
                "numpy",
                "httpx",
                "datasets",
                "typer",
                "pytest",
                "ruff",
            ]
        },
        "checks": {},
        "inference_performed": False,
        "model_load_test": "NOT_RUN: Step 3/P0",
        "models": registry["models"],
    }
    with stage_log(paths, "verify-env") as logger:

        def check(name: str, operation: Any) -> None:
            try:
                evidence = operation()
                result["checks"][name] = {"status": "PASS", "evidence": evidence}
                logger.info("%s PASS", name)
            except Exception as exc:
                result["checks"][name] = {"status": "FAIL", "reason": str(exc)}
                logger.exception("%s FAIL", name)

        def command(arguments: list[str]) -> str:
            done = subprocess.run(arguments, capture_output=True, text=True, timeout=30)
            if done.returncode:
                raise RuntimeError(done.stderr or done.stdout)
            return (done.stdout + done.stderr).strip()

        def python_check() -> str:
            if platform.python_version_tuple()[:2] != ("3", "11"):
                raise RuntimeError("Python 3.11 is required.")
            return platform.python_version()

        check("python_311", python_check)
        check(
            "gpu",
            lambda: command(
                [
                    "nvidia-smi",
                    "--query-gpu=name,memory.total,driver_version",
                    "--format=csv,noheader",
                ]
            ),
        )
        executable = paths.root / registry["serving"]["executable"]

        def llama_check() -> dict[str, str]:
            version = command([str(executable), "--version"])
            devices = command([str(executable), "--list-devices"])
            if registry["serving"]["commit"] not in version or "CUDA0" not in devices:
                raise RuntimeError("Installed llama.cpp build/commit or CUDA backend differs.")
            body = _fetch(
                paths,
                "llama_arch.txt",
                registry["serving"]["architecture_source_url"]
                .replace("https://github.com/", "https://raw.githubusercontent.com/")
                .replace("/blob/", "/"),
                offline,
            )
            if registry["serving"]["architecture"].encode() not in body:
                raise RuntimeError(
                    "WM-A architecture is not supported in the pinned llama.cpp source."
                )
            return {
                "version": version,
                "devices": devices,
                "binary_sha256": hashlib.sha256(executable.read_bytes()).hexdigest(),
                "architecture_evidence_sha256": hashlib.sha256(body).hexdigest(),
            }

        check("llama_cpp_architecture_and_cuda", llama_check)
        for role, model in registry["models"].items():

            def model_check(role: str = role, model: dict = model) -> dict:
                source = json.loads(
                    _fetch(
                        paths,
                        f"{role}_source_api.json",
                        f"https://huggingface.co/api/models/{model['source']}/revision/{model['source_revision']}?blobs=true",
                        offline,
                    )
                )
                quant = json.loads(
                    _fetch(
                        paths,
                        f"{role}_quant_api.json",
                        f"https://huggingface.co/api/models/{model['gguf_repository']}/revision/{model['gguf_revision']}?blobs=true",
                        offline,
                    )
                )
                if source.get("cardData", {}).get("license") not in ("apache-2.0", "mit"):
                    raise RuntimeError("Model license requires review.")
                remote = {entry["rfilename"]: entry for entry in quant["siblings"]}
                for file in model["files"]:
                    if remote[file["filename"]]["lfs"]["sha256"] != file["sha256"]:
                        raise RuntimeError(
                            "Configured model file hash differs from pinned metadata."
                        )
                return {
                    "source": source["id"],
                    "source_revision": source["sha"],
                    "gguf_revision": quant["sha"],
                    "license": source["cardData"]["license"],
                    "hashes": {f["filename"]: f["sha256"] for f in model["files"]},
                    "hash_basis": "Pinned Hugging Face LFS metadata; model weights not downloaded.",
                }

            check(role, model_check)

        def dataset_check() -> dict:
            loaded = load_mbpp(paths, registry, offline)
            atomic_text(paths.configs / "models.yaml", yaml.safe_dump(registry, sort_keys=False))
            return {
                name: {"rows": len(split), "columns": split.column_names}
                for name, split in loaded.items()
            }

        check("mbpp_sanitized_load", dataset_check)

        def import_reference_check() -> dict:
            from inert.tasks import normalize_mbpp

            loaded = load_mbpp(paths, registry, offline=True)
            sandbox = DockerSandbox(paths, config["sandbox"])
            records = []
            for split in loaded.values():
                for row in split:
                    if not row["test_imports"]:
                        continue
                    task = normalize_mbpp(row)
                    harness = render_harness(task.tests, config["sandbox"]["test_seconds"])
                    output = sandbox.run(task.reference_code, harness, use_cache=False)
                    records.append(
                        {
                            "task_id": task.task_id,
                            "imports": row["test_imports"],
                            "n_tests": task.n_tests,
                            "stdout": output.stdout,
                            "stderr": output.stderr,
                            "returncode": output.returncode,
                            "harness_sha256": hashlib.sha256(harness.encode()).hexdigest(),
                            "reference_sha256": hashlib.sha256(
                                task.reference_code.encode()
                            ).hexdigest(),
                            "passed": output.returncode == 0
                            and output.stdout == f"RESULT: {task.n_tests}/{task.n_tests}\n",
                        }
                    )
            evidence_file = paths.data / "verification" / "import_reference_checks.json"
            write_json(evidence_file, records)
            if not all(record["passed"] for record in records):
                raise RuntimeError(
                    "An import-dependent reference failed; inspect the recorded outputs."
                )
            return {
                "checked": len(records),
                "passed": sum(r["passed"] for r in records),
                "source_file": str(evidence_file.relative_to(paths.root)),
                "sha256": hashlib.sha256(evidence_file.read_bytes()).hexdigest(),
            }

        check("mbpp_import_dependent_references", import_reference_check)

        def prompt_check() -> list[dict]:
            from inert.render import _prompt

            with (paths.prompts / "vendored" / "provenance.yaml").open(encoding="utf-8") as stream:
                provenance = yaml.safe_load(stream)["prompts"]
            for item in provenance:
                name = "wm_terminal.txt" if item["channel"] == "C" else "wm_tool.txt"
                url = f"https://raw.githubusercontent.com/{item['repository']}/{item['commit']}/{item['path']}"
                raw = _fetch(
                    paths, f"channel_{item['channel'].lower()}_pinned_source.txt", url, offline
                )
                if hashlib.sha256(raw).hexdigest() != item["source_sha256"]:
                    raise RuntimeError("Vendored source hash mismatch.")
                body = _prompt(paths.prompts / "vendored" / name)
                if hashlib.sha256(body.encode()).hexdigest() != item["prompt_sha256"]:
                    raise RuntimeError("Vendored prompt text changed.")
            with (paths.prompts / "vendored" / "provenance.yaml").open(encoding="utf-8") as stream:
                licenses = yaml.safe_load(stream)["license_files"]
            for license_file in licenses:
                local = (paths.prompts / "vendored" / license_file["path"]).read_bytes()
                raw = _fetch(paths, license_file["evidence_name"], license_file["url"], offline)
                if hashlib.sha256(local).hexdigest() != license_file["sha256"] or raw != local:
                    raise RuntimeError("Pinned license notice changed.")
            return provenance

        check("pinned_prompt_locations_and_licenses", prompt_check)

        def sandbox_check() -> dict[str, str]:
            sandbox = DockerSandbox(paths, config["sandbox"])
            output = sandbox.run(
                'import os\ndef verify(): return os.listdir("/sys/class/net") == ["lo"]',
                render_harness(["assert verify()"], config["sandbox"]["test_seconds"]),
                use_cache=False,
            )
            if output.stdout != "RESULT: 1/1\n" or output.returncode != 0:
                raise RuntimeError("Docker sandbox networking check failed: " + output.stderr)
            return {
                "stdout": output.stdout,
                "image": config["sandbox"]["image"],
                "image_digest": command(
                    [
                        "docker",
                        "image",
                        "inspect",
                        config["sandbox"]["image"],
                        "--format",
                        "{{json .RepoDigests}}",
                    ]
                ),
            }

        check("docker_network_none", sandbox_check)
        result["status"] = (
            "PASS" if all(v["status"] == "PASS" for v in result["checks"].values()) else "FAIL"
        )
        result["dataset"] = registry["dataset"]
        write_json(paths.environment, result)
        lines = [
            "# Step 0 verification",
            "",
            f"Status: {result['status']}",
            "",
            "| Check | Status |",
            "| --- | --- |",
        ]
        lines += [f"| {name} | {value['status']} |" for name, value in result["checks"].items()]
        lines += [
            "",
            "Evidence and versions: `env.json`. Pinned identifiers, licences and model file",
            "hashes: `../../configs/models.yaml`. Model hashes come from pinned LFS metadata;",
            "local weight verification is mandatory before serving. WM-A loading and latency",
            "remain untested until Step 3/P0. No inference or pilot scoring ran in Step 0.",
        ]
        atomic_text(paths.results / "Step0_Verification.md", "\n".join(lines) + "\n")
    if result["status"] != "PASS":
        raise StopRequired("Step 0 failed. See results/pilot/env.json; decide before continuing.")
    return result
