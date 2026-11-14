import hashlib
import json
from collections.abc import Callable
from pathlib import Path
from typing import Annotated, Any

import typer

from inert.analyze import analyze_records
from inert.audit import StopRequired, stage_log
from inert.config import Paths, load_config
from inert.models import model_session
from inert.p0 import run_p0
from inert.p0_selection import prepare_p0_manifest
from inert.pipeline import build_items, choose_core, execute_candidates
from inert.planning import model_items
from inert.proposer import generate_candidates, generate_thoughts
from inert.report import write_report
from inert.sandbox import DockerSandbox
from inert.schemas import Candidate, Item, Score, Task, read_jsonl, write_json
from inert.score import check_model_validity, score_items
from inert.tasks import CpuTokenizer, prepare_tasks
from inert.verification import verify_environment

app = typer.Typer(
    no_args_is_help=True, help="INERT pilot: local models, Docker execution, resumable stages."
)


@app.callback()
def main(
    ctx: typer.Context,
    root: Annotated[Path | None, typer.Option("--root")] = None,
    smoke: Annotated[
        bool, typer.Option("--smoke", help="Isolate a 3-task WM-C smoke run.")
    ] = False,
    sandbox_cache: Annotated[
        Path | None,
        typer.Option("--sandbox-cache", help="Isolate the pilot Docker sandbox cache."),
    ] = None,
) -> None:
    base = root if root is not None else Paths.discover().root
    paths = Paths(base, "smoke" if smoke else "pilot", sandbox_cache_override=sandbox_cache)
    ctx.obj = {"paths": paths, "config": load_config(paths)}


def _run(ctx: typer.Context, stage: str, operation: Callable) -> Any:
    paths = ctx.obj["paths"]
    try:
        with stage_log(paths, stage) as logger:
            return operation(paths, ctx.obj["config"], logger)
    except (StopRequired, ValueError, FileNotFoundError, RuntimeError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(2) from exc


def _ready(paths: Paths) -> None:
    if (
        not paths.environment.exists()
        or json.loads(paths.environment.read_text())["status"] != "PASS"
    ):
        raise StopRequired(
            "Run inert verify-env and resolve Step 0 failures before pipeline execution."
        )


def _task_records(paths: Paths) -> list[Task]:
    records = read_jsonl(paths.tasks, Task)
    if not records:
        raise ValueError("No tasks prepared; run inert tasks first.")
    return records


@app.command("verify-env")
def verify_env(
    ctx: typer.Context, offline: Annotated[bool, typer.Option("--offline")] = False
) -> None:
    _run(ctx, "verify-env", lambda paths, config, logger: verify_environment(paths, offline))
    typer.echo("Step 0 verification PASS; see results/pilot/env.json.")


@app.command("tasks")
def tasks_command(ctx: typer.Context) -> None:
    def run(paths: Paths, config: dict, logger: Any) -> None:
        _ready(paths)
        prepare_tasks(
            paths,
            config,
            DockerSandbox(paths, config["sandbox"]),
            CpuTokenizer(paths, config),
            logger,
        )

    _run(ctx, "tasks", run)


@app.command("propose")
def propose(ctx: typer.Context) -> None:
    def run(paths: Paths, config: dict, logger: Any) -> None:
        _ready(paths)
        with model_session(paths, config, "proposer") as client:
            generate_candidates(paths, config, client, _task_records(paths), logger)

    _run(ctx, "propose", run)


@app.command("execute")
def execute(ctx: typer.Context) -> None:
    def run(paths: Paths, config: dict, logger: Any) -> None:
        _ready(paths)
        _task_records(paths)
        execute_candidates(paths, config, DockerSandbox(paths, config["sandbox"]), logger)

    _run(ctx, "execute", run)


@app.command("core-set")
def core_set(ctx: typer.Context) -> None:
    def run(paths: Paths, config: dict, logger: Any) -> None:
        _ready(paths)
        _task_records(paths)
        choose_core(paths, config, DockerSandbox(paths, config["sandbox"]), logger)

    _run(ctx, "core-set", run)


@app.command("thoughts")
def thoughts(ctx: typer.Context) -> None:
    def run(paths: Paths, config: dict, logger: Any) -> None:
        _ready(paths)
        with model_session(paths, config, "proposer") as client:
            generate_thoughts(
                paths, config, client, _task_records(paths), read_jsonl(paths.candidates, Candidate)
            )

    _run(ctx, "thoughts", run)


@app.command("build-items")
def items_command(
    ctx: typer.Context, prompt_family: Annotated[str, typer.Option("--prompt-family")] = "vendored"
) -> None:
    def run(paths: Paths, config: dict, logger: Any) -> None:
        _ready(paths)
        build_items(paths, config, DockerSandbox(paths, config["sandbox"]), logger, prompt_family)

    _run(ctx, "build-items", run)


@app.command("p0")
def p0_command(ctx: typer.Context, wm: Annotated[str, typer.Option("--wm")] = "wm_a") -> None:
    def run(paths: Paths, config: dict, logger: Any) -> None:
        _ready(paths)
        if wm != "wm_a":
            raise ValueError("P0 is defined only for WM-A.")
        if paths.profile == "smoke":
            raise ValueError("WM-A P0 is outside the WM-C smoke profile.")
        run_p0(paths, config, logger)

    _run(ctx, "p0", run)


@app.command("prepare-p0")
def prepare_p0_command(ctx: typer.Context) -> None:
    def run(paths: Paths, config: dict, logger: Any) -> None:
        _ready(paths)
        if paths.profile != "pilot":
            raise ValueError("P0 selection is defined only for the pilot profile.")
        manifest = prepare_p0_manifest(paths, config)
        logger.info("Frozen P0 selection: %s", manifest["manifest_sha256"])

    _run(ctx, "prepare-p0", run)


def _all_scores(paths: Paths, config: dict) -> list[Score]:
    return [
        score
        for model in config["scoring_order"]
        for score in read_jsonl(paths.scores(model), Score)
    ]


def _analyze(paths: Paths, config: dict) -> dict:
    scores = _all_scores(paths, config)
    if not scores:
        raise ValueError("No score records exist; analysis and pilot results were not generated.")
    p0_file = paths.results / "p0.json"
    p0 = json.loads(p0_file.read_text()) if p0_file.exists() else {"decision": "NOT_RUN"}
    status = (
        {"wm_a": "DROPPED"}
        if p0["decision"] == "drop_wm_a"
        else {"wm_a": "REDUCED"}
        if p0["decision"] == "reduced"
        else {}
    )
    result = analyze_records(
        _task_records(paths),
        read_jsonl(paths.candidates, Candidate),
        read_jsonl(paths.items, Item),
        scores,
        config,
        status,
        checkpoint_root=paths.data / "analysis_cache",
    )
    result["p0"] = p0
    result["scoring_environment"] = {}
    for wm in config["scoring_order"]:
        measured = [s for s in scores if s.wm_id == wm and not s.cache_hit]
        total_latency = sum(s.latency_s for s in measured)
        has_tokens = bool(measured) and all(s.completion_tokens is not None for s in measured)
        result["scoring_environment"][wm] = {
            "uncached_calls": len(measured),
            "mean_seconds": total_latency / len(measured) if measured else None,
            "tokens_per_second": sum(s.completion_tokens for s in measured) / total_latency
            if has_tokens and total_latency
            else None,
        }
    result["run_kind"] = paths.profile
    if paths.profile == "smoke":
        result["decision"] = "SMOKE RUN: pipeline verification only; no pilot decision."
    sources = [
        paths.tasks,
        paths.candidates,
        paths.items,
        *[paths.scores(model) for model in config["scoring_order"] if paths.scores(model).exists()],
    ]
    result["sources"] = {
        str(path.relative_to(paths.root)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sources
    }
    result["deviations"] = (
        paths.deviations.read_text(encoding="utf-8") if paths.deviations.exists() else "none"
    )
    drops = paths.data / "task_drops.json"
    result["data_quality"]["tasks_dropped"] = (
        json.loads(drops.read_text()) if drops.exists() else []
    )
    write_json(paths.summary, result)
    return result


@app.command("score")
def score_command(
    ctx: typer.Context,
    wm: Annotated[str, typer.Option("--wm")],
    block: Annotated[str, typer.Option("--block")] = "kt_ab",
) -> None:
    def run(paths: Paths, config: dict, logger: Any) -> None:
        _ready(paths)
        if wm not in config["scoring_order"] or block not in ("kt_ab", "kt_c"):
            raise ValueError("Unknown model or scoring block.")
        all_items = read_jsonl(paths.items, Item)
        items = [
            i
            for i in all_items
            if i.block == block or block == "kt_c" and i.block.startswith("kt_c_")
        ]
        p0_file = paths.results / "p0.json"
        p0 = json.loads(p0_file.read_text()) if p0_file.exists() else {"decision": "NOT_RUN"}
        if paths.profile == "pilot" and p0["decision"] == "NOT_RUN":
            raise StopRequired("Run P0 before pilot scoring; use --smoke for the WM-C smoke run.")
        if wm == "wm_a" and p0["decision"] == "drop_wm_a":
            raise StopRequired("WM-A was dropped at P0; it must not be scored.")
        items = model_items(
            items,
            _task_records(paths),
            read_jsonl(paths.candidates, Candidate),
            config,
            wm,
            p0["decision"],
        )
        if not items:
            raise ValueError("No items prepared for this block.")
        for prior in config["scoring_order"][: config["scoring_order"].index(wm)]:
            if block == "kt_c" and prior == "wm_c":
                continue
            if prior == "wm_a" and p0["decision"] == "drop_wm_a":
                continue
            prior_plan = model_items(
                [
                    i
                    for i in all_items
                    if i.block == block or block == "kt_c" and i.block.startswith("kt_c_")
                ],
                _task_records(paths),
                read_jsonl(paths.candidates, Candidate),
                config,
                prior,
                p0["decision"],
            )
            prior_done = {s.item_id for s in read_jsonl(paths.scores(prior), Score)}
            if not prior_plan or not {i.item_id for i in prior_plan} <= prior_done:
                raise StopRequired(
                    f"Scoring order requires completion of {prior}/{block} before {wm}."
                )
            if block == "kt_ab":
                check_model_validity(paths, config, prior, prior_plan)
        if block == "kt_c" and paths.profile != "smoke":
            summary = _analyze(paths, config)
            if summary["kt_a"] == "KILL":
                typer.echo("KT-A verdict KILL: KT-C is skipped under the design.")
                return
            if summary["kt_a"] in ("UNAVAILABLE", "INCONCLUSIVE"):
                raise StopRequired("KT-A is not ready or has no valid strong/medium cells.")
        already = {s.item_id for s in read_jsonl(paths.scores(wm), Score)}
        if all(i.item_id in already for i in items):
            if block == "kt_ab":
                check_model_validity(paths, config, wm, items)
            typer.echo("All requested items already scored.")
            return
        with model_session(paths, config, wm) as client:
            score_items(paths, config, wm, items, client, logger)
        if block == "kt_ab":
            check_model_validity(paths, config, wm, items)

    _run(ctx, "score", run)


@app.command("analyze")
def analyze_command(ctx: typer.Context) -> None:
    _run(ctx, "analyze", lambda paths, config, logger: _analyze(paths, config))


@app.command("report")
def report_command(ctx: typer.Context) -> None:
    def run(paths: Paths, config: dict, logger: Any) -> None:
        if not paths.summary.exists():
            raise ValueError("No analysis exists; run inert analyze after scoring.")
        summary = json.loads(paths.summary.read_text(encoding="utf-8"))
        for filename, expected in summary["sources"].items():
            source = (paths.root / filename).resolve()
            if (
                not source.is_relative_to(paths.data)
                or hashlib.sha256(source.read_bytes()).hexdigest() != expected
            ):
                raise ValueError("Source records changed; rerun inert analyze before reporting.")
        environment = (
            json.loads(paths.environment.read_text(encoding="utf-8"))
            if paths.environment.exists()
            else {"status": "NOT_RECORDED"}
        )
        write_report(
            paths,
            summary,
            environment,
            read_jsonl(paths.items, Item),
            _all_scores(paths, config),
            read_jsonl(paths.candidates, Candidate),
        )

    _run(ctx, "report", run)


if __name__ == "__main__":
    app()
