import hashlib
import json
import sqlite3
import time
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Self
from urllib.parse import urlsplit

import httpx

from inert.schemas import Message


@dataclass(frozen=True)
class Completion:
    raw_output: str
    latency_s: float
    completion_tokens: int | None
    cache_hit: bool
    timestamp: str
    finish_reason: str | None


def local_url(url: str) -> str:
    parsed = urlsplit(url)
    if (
        parsed.scheme != "http"
        or parsed.hostname not in ("127.0.0.1", "::1", "localhost")
        or parsed.username
        or parsed.password
        or parsed.path not in ("", "/")
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("Only a local HTTP inference server origin is allowed.")
    return url.rstrip("/")


def completion_request(
    model_hash: str,
    flags: dict[str, Any],
    messages: list[Message],
    parameters: dict[str, Any],
) -> tuple[str, str, dict[str, Any]]:
    params = {key: parameters[key] for key in ("temperature", "top_p", "max_tokens", "seed")}
    payload = {"messages": [message.model_dump() for message in messages], **params}
    identity = {
        "model_file_sha256": model_hash,
        "server_flags_that_affect_output": flags,
        **payload,
    }
    serialized = json.dumps(identity, sort_keys=True, ensure_ascii=False, allow_nan=False)
    return hashlib.sha256(serialized.encode()).hexdigest(), serialized, payload


class CachedClient:
    def __init__(
        self,
        cache: Path,
        base_url: str,
        model_file_sha256: str,
        server_flags: dict[str, Any],
        timeout: float = 300,
        transport: httpx.BaseTransport | None = None,
        on_miss: Callable[[], None] | None = None,
    ) -> None:
        self.base_url = local_url(base_url)
        self.model_hash = model_file_sha256
        self.flags = server_flags
        self.on_miss = on_miss
        self.server_startup_seconds: float | None = None
        cache.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(cache)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS calls "
            "(key TEXT PRIMARY KEY, request TEXT NOT NULL, response TEXT NOT NULL, "
            "completion TEXT NOT NULL)"
        )
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS utilities (key TEXT PRIMARY KEY, response TEXT NOT NULL)"
        )
        self.http = httpx.Client(
            base_url=self.base_url,
            timeout=timeout,
            transport=transport,
            trust_env=False,
            follow_redirects=False,
        )

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *args: object) -> None:
        self.http.close()
        self.db.close()

    def complete(self, messages: list[Message], parameters: dict[str, Any]) -> Completion:
        key, serialized, payload = completion_request(
            self.model_hash, self.flags, messages, parameters
        )
        saved = self.db.execute("SELECT completion FROM calls WHERE key = ?", (key,)).fetchone()
        if saved:
            return replace(Completion(**json.loads(saved[0])), cache_hit=True)
        if self.on_miss is not None:
            self.on_miss()
        started = time.perf_counter()
        response = self.http.post("/v1/chat/completions", json=payload)
        response.raise_for_status()
        body = response.json()
        choice = body["choices"][0]
        message = choice["message"]
        content = message.get("content") or ""
        if message.get("reasoning_content"):
            content = "<think>" + message["reasoning_content"] + "</think>\n" + content
        result = Completion(
            content,
            time.perf_counter() - started,
            body.get("usage", {}).get("completion_tokens"),
            False,
            datetime.now(UTC).isoformat(),
            choice.get("finish_reason"),
        )
        from dataclasses import asdict

        with self.db:
            self.db.execute(
                "INSERT OR IGNORE INTO calls VALUES (?, ?, ?, ?)",
                (key, serialized, response.text, json.dumps(asdict(result))),
            )
        return result

    def tokenize(self, text: str) -> list[int]:
        tokens = self._utility("/tokenize", {"content": text, "add_special": False})["tokens"]
        if not isinstance(tokens, list) or any(type(x) is not int for x in tokens):
            raise ValueError("Invalid tokenizer response.")
        return tokens

    def detokenize(self, tokens: list[int]) -> str:
        return self._utility("/detokenize", {"tokens": tokens})["content"]

    def _utility(self, endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
        identity = json.dumps([self.model_hash, self.flags, endpoint, payload], sort_keys=True)
        key = hashlib.sha256(identity.encode()).hexdigest()
        row = self.db.execute("SELECT response FROM utilities WHERE key = ?", (key,)).fetchone()
        if row:
            return json.loads(row[0])
        if self.on_miss is not None:
            self.on_miss()
        response = self.http.post(endpoint, json=payload)
        response.raise_for_status()
        result = response.json()
        with self.db:
            self.db.execute("INSERT OR REPLACE INTO utilities VALUES (?, ?)", (key, response.text))
        return result
