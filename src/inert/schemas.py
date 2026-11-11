import hashlib
import json
import os
import tempfile
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path
from typing import Annotated, Any, Literal, Self, TypeVar

from pydantic import BaseModel, ConfigDict, Field, model_validator

from inert.strip import natural_text, strip_text

Probability = Annotated[float, Field(ge=0, le=1)]
Nonnegative = Annotated[int, Field(ge=0)]
Positive = Annotated[int, Field(gt=0)]
Channel = Literal["C", "D"]
Condition = Literal[
    "T0",
    "NEU_A",
    "NEU_B",
    "NAT",
    "TRUE",
    "MIS_OUTCOME",
    "MIS_VERIFY",
    "MIS_PROPERTY",
    "MIS_AUTHORITY",
    "CLAIM_POS",
]
Block = Literal["kt_ab", "kt_c_a", "kt_c_b"]


class Record(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True, allow_inf_nan=False)


class Endpoint(Record):
    estimate: float | None
    lower: float | None
    upper: float | None
    n_pairs: Nonnegative
    n_tasks: Nonnegative
    n_resamples: Nonnegative
    n_valid_resamples: Nonnegative
    reason: str | None = None


class Task(Record):
    task_id: str
    source: str
    prompt: str
    fn_name: str
    tests: list[str]
    n_tests: Positive
    reference_code: str

    @model_validator(mode="after")
    def check_tests(self) -> Self:
        if len(self.tests) != self.n_tests:
            raise ValueError("n_tests does not match tests.")
        if not self.fn_name.isidentifier():
            raise ValueError("fn_name must be a Python identifier.")
        return self


class Candidate(Record):
    cand_id: str
    task_id: str
    gen_index: Nonnegative
    origin: str
    raw_source: str
    code_stripped: str
    natural_text: str
    code_sha256: str
    n_tests: Positive | None = None
    n_passed: Nonnegative | None = None
    R_exec: Probability | None = None
    true_pass: bool | None = None
    harness_output: str | None = None
    in_core_set: bool = False

    @classmethod
    def from_source(
        cls, cand_id: str, task_id: str, gen_index: int, origin: str, source: str
    ) -> "Candidate":
        stripped = strip_text(source)
        return cls(
            cand_id=cand_id,
            task_id=task_id,
            gen_index=gen_index,
            origin=origin,
            raw_source=source,
            code_stripped=stripped,
            natural_text=natural_text(source),
            code_sha256=hashlib.sha256(stripped.encode()).hexdigest(),
        )

    @model_validator(mode="after")
    def check_integrity(self) -> Self:
        if self.origin not in ("proposer", "reference") and not self.origin.startswith("mutant:"):
            raise ValueError("Unknown candidate origin.")
        if hashlib.sha256(self.code_stripped.encode()).hexdigest() != self.code_sha256:
            raise ValueError("code_sha256 mismatch.")
        if strip_text(self.raw_source) != self.code_stripped:
            raise ValueError("code_stripped does not match raw_source.")
        if natural_text(self.raw_source) != self.natural_text:
            raise ValueError("natural_text does not match raw_source.")
        truth = (self.n_tests, self.n_passed, self.R_exec, self.true_pass, self.harness_output)
        if any(x is not None for x in truth):
            if any(x is None for x in truth):
                raise ValueError("Ground truth must be complete or entirely absent.")
            if self.n_passed > self.n_tests or self.R_exec != self.n_passed / self.n_tests:
                raise ValueError("Inconsistent executed reward.")
            if self.true_pass != (self.n_passed == self.n_tests):
                raise ValueError("Inconsistent true_pass.")
        return self


class Thought(Record):
    cand_id: str
    text: str
    seed: Nonnegative


class Message(Record):
    role: Literal["system", "user", "assistant"]
    content: str


class Item(Record):
    item_id: str
    task_id: str
    cand_id: str
    channel: Channel
    condition: Condition
    block: Block
    text: str
    messages: list[Message]
    prompt_family: Literal["vendored", "inhouse"]


class Score(Record):
    item_id: str
    wm_id: str
    raw_output: str
    parse_status: Literal["ok", "fail"]
    k_pred: Nonnegative | None
    n_pred: Nonnegative | None
    R_sim: Probability | None
    pred_pass: bool | None
    latency_s: Annotated[float, Field(ge=0)]
    completion_tokens: Nonnegative | None
    cache_hit: bool
    timestamp: str

    @model_validator(mode="after")
    def check_score(self) -> Self:
        stamp = datetime.fromisoformat(self.timestamp)
        if stamp.tzinfo is None:
            raise ValueError("Timestamp must include a timezone.")
        if self.parse_status == "fail":
            if self.R_sim is not None or self.pred_pass is not None:
                raise ValueError("Parse failures must not be imputed.")
        elif (
            self.k_pred is None
            or self.n_pred is None
            or self.n_pred == 0
            or self.k_pred > self.n_pred
            or self.R_sim != self.k_pred / self.n_pred
            or self.pred_pass != (self.k_pred == self.n_pred)
        ):
            raise ValueError("Inconsistent parsed reward.")
        return self


T = TypeVar("T", bound=BaseModel)


def read_jsonl(path: Path, schema: type[T]) -> list[T]:
    if not path.exists():
        return []
    records = []
    with path.open(encoding="utf-8") as stream:
        for number, line in enumerate(stream, 1):
            try:
                records.append(schema.model_validate_json(line))
            except ValueError as exc:
                raise ValueError(f"{path}: line {number}: {exc}") from exc
    return records


def write_jsonl(path: Path, records: Iterable[T], schema: type[T]) -> None:
    lines = []
    for record in records:
        if not isinstance(record, schema):
            raise TypeError(f"Expected {schema.__name__}.")
        validated = schema.model_validate_json(record.model_dump_json())
        lines.append(validated.model_dump_json() + "\n")
    atomic_text(path, "".join(lines))


def atomic_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="\n", dir=path.parent, delete=False
        ) as stream:
            temporary = Path(stream.name)
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def write_json(path: Path, value: Any) -> None:
    atomic_text(path, json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
