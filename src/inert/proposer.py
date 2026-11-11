import logging
import re

from inert.audit import Progress
from inert.config import Config, Paths
from inert.llm_client import CachedClient
from inert.schemas import Candidate, Message, Record, Task, Thought, read_jsonl, write_jsonl


class Attempt(Record):
    task_id: str
    gen_index: int
    seed: int
    status: str
    cand_id: str | None


def extract_code(response: str) -> str:
    fence = chr(96) * 3
    match = re.search(fence + r"(?:python|py)\s*\n(.*?)" + fence, response, re.S | re.I)
    return match[1].strip() if match else response.strip()


def _messages(paths: Paths, name: str, values: dict[str, str]) -> list[Message]:
    from inert.render import _fill

    template = (paths.prompts / "inhouse" / name).read_text(encoding="utf-8")
    system, user = _fill(template, values).split("\n\nUser:\n", 1)
    return [
        Message(role="system", content=system.removeprefix("System:\n")),
        Message(role="user", content=user.rstrip("\n")),
    ]


def generate_candidates(
    paths: Paths, config: Config, client: CachedClient, tasks: list[Task], logger: logging.Logger
) -> None:
    attempts_path = paths.data / "generation_attempts.jsonl"
    attempts = read_jsonl(attempts_path, Attempt)
    finished = {(a.task_id, a.gen_index) for a in attempts}
    candidates = read_jsonl(paths.candidates, Candidate)
    hashes = {(c.task_id, c.code_sha256) for c in candidates}
    by_id = {c.cand_id: c for c in candidates}
    total = sum(
        (task.task_id, k) not in finished
        for task in tasks
        for k in range(config["candidates"]["per_task"])
    )
    progress = Progress(total)
    params = config["sampling"]["proposer"]
    for index, task in enumerate(tasks):
        for k in range(config["candidates"]["per_task"]):
            if (task.task_id, k) in finished:
                continue
            seed = params["seed_base"] + index * params["task_stride"] + k
            result = client.complete(
                _messages(
                    paths,
                    "proposer_code.txt",
                    {"task_prompt": task.prompt, "first_test_assert": task.tests[0]},
                ),
                {**params, "seed": seed},
            )
            candidate = None
            status = "syntax_error"
            try:
                candidate = Candidate.from_source(
                    f"{task.task_id}-g{k:02}",
                    task.task_id,
                    k,
                    "proposer",
                    extract_code(result.raw_output),
                )
                if candidate.cand_id in by_id:
                    if by_id[candidate.cand_id].code_sha256 != candidate.code_sha256:
                        raise ValueError("Cached generation differs from checkpointed candidate.")
                    status = "accepted"
                elif (task.task_id, candidate.code_sha256) in hashes:
                    status = "duplicate"
                    candidate = None
                else:
                    status = "accepted"
                    hashes.add((task.task_id, candidate.code_sha256))
                    candidates.append(candidate)
                    by_id[candidate.cand_id] = candidate
            except SyntaxError:
                logger.info("Discarded syntax error: task=%s k=%s", task.task_id, k)
            attempts.append(
                Attempt(
                    task_id=task.task_id,
                    gen_index=k,
                    seed=seed,
                    status=status,
                    cand_id=candidate.cand_id if candidate else None,
                )
            )
            # Write candidates first: a crash can replay the cached attempt and deduplicate by ID.
            write_jsonl(paths.candidates, candidates, Candidate)
            write_jsonl(attempts_path, attempts, Attempt)
            progress.advance()


def generate_thoughts(
    paths: Paths,
    config: Config,
    client: CachedClient,
    tasks: list[Task],
    candidates: list[Candidate],
) -> None:
    thoughts = read_jsonl(paths.thoughts, Thought)
    done = {t.cand_id for t in thoughts}
    task_map = {task.task_id: task for task in tasks}
    core = [c for c in candidates if c.in_core_set]
    progress = Progress(sum(c.cand_id not in done for c in core))
    params = config["sampling"]["thought"]
    for index, candidate in enumerate(core):
        if candidate.cand_id in done:
            continue
        seed = params["seed_base"] + index
        text = ""
        if candidate.natural_text:
            result = client.complete(
                _messages(
                    paths,
                    "proposer_thought.txt",
                    {
                        "task_prompt": task_map[candidate.task_id].prompt,
                        "code_stripped": candidate.code_stripped,
                    },
                ),
                {**params, "seed": seed},
            )
            text = " ".join(
                re.split(r"(?<=[.!?])\s+", result.raw_output.strip())[: params["sentences"]]
            )
            tokens = client.tokenize(text)
            if len(tokens) > params["tokens"]:
                text = client.detokenize(tokens[: params["tokens"]])
        thoughts.append(Thought(cand_id=candidate.cand_id, text=text, seed=seed))
        write_jsonl(paths.thoughts, thoughts, Thought)
        progress.advance()
