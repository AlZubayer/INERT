import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

Config = dict[str, Any]


@dataclass(frozen=True)
class Paths:
    root: Path
    profile: str = "pilot"

    def __post_init__(self) -> None:
        if self.profile not in ("pilot", "smoke"):
            raise ValueError("Unknown run profile.")
        object.__setattr__(self, "root", self.root.resolve())

    @classmethod
    def discover(cls, start: Path | None = None) -> "Paths":
        current = (start or Path.cwd()).resolve()
        for parent in [current, *current.parents]:
            if (parent / "Pilot_Experimental_Design.md").is_file():
                return cls(parent)
        raise FileNotFoundError("Cannot find INERT repository; supply --root.")

    @property
    def data(self) -> Path:
        return self.shared_data / "smoke" if self.profile == "smoke" else self.shared_data

    @property
    def shared_data(self) -> Path:
        return self.root / "data"

    @property
    def configs(self) -> Path:
        return self.root / "configs"

    @property
    def prompts(self) -> Path:
        return self.root / "prompts"

    @property
    def results(self) -> Path:
        base = self.root / "results" / "pilot"
        return base / "smoke" if self.profile == "smoke" else base

    @property
    def tasks(self) -> Path:
        return self.data / "tasks.jsonl"

    @property
    def reserves(self) -> Path:
        return self.data / "reserves.jsonl"

    @property
    def candidates(self) -> Path:
        return self.data / "candidates.jsonl"

    @property
    def thoughts(self) -> Path:
        return self.data / "thoughts.jsonl"

    @property
    def items(self) -> Path:
        return self.data / "items.jsonl"

    @property
    def summary(self) -> Path:
        return self.results / "summary.json"

    @property
    def report(self) -> Path:
        return self.results / "Pilot_Results.md"

    @property
    def environment(self) -> Path:
        return self.root / "results" / "pilot" / "env.json"

    @property
    def deviations(self) -> Path:
        return self.root / "results" / "pilot" / "deviations.md"

    @property
    def server_lock(self) -> Path:
        return self.shared_data / "server.lock"

    def cache(self, model: str) -> Path:
        return self.data / "cache" / f"{_identifier(model)}.sqlite"

    def scores(self, model: str) -> Path:
        return self.data / "scores" / f"{_identifier(model)}.jsonl"

    def log_file(self, stage: str) -> Path:
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S.%fZ")
        return self.data / "logs" / f"{_identifier(stage)}-{stamp}.log"


def _identifier(value: str) -> str:
    if not re.fullmatch(r"[a-z][a-z0-9_-]*", value):
        raise ValueError(f"Unsafe identifier: {value!r}")
    return value


def load_config(paths: Paths | None = None) -> Config:
    location = (paths or Paths.discover()).configs / "pilot.yaml"
    with location.open(encoding="utf-8") as stream:
        result = yaml.safe_load(stream)
    if not isinstance(result, dict):
        raise ValueError("Pilot configuration must be a YAML mapping.")
    for key in (
        "tasks",
        "candidates",
        "sampling",
        "server",
        "sandbox",
        "statistics",
        "selection",
        "thresholds",
        "templates",
    ):
        if not isinstance(result.get(key), dict):
            raise ValueError(f"Missing configuration mapping: {key}")
    if result["server"]["host"] != "127.0.0.1":
        raise ValueError("The inference server must bind to 127.0.0.1.")
    if paths is not None and paths.profile == "smoke":
        result["tasks"]["count"] = result["smoke"]["tasks"]
        result["scoring_order"] = result["smoke"]["models"]
    return result
