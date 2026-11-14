import hashlib
import json
import sys
from pathlib import Path

import httpx
import pytest

from inert.config import Paths, load_config
from inert.llm_client import CachedClient, completion_request
from inert.schemas import Message
from inert.server import ModelServer, ServerError


def test_local_only_and_cache_key(tmp_path: Path) -> None:
    for url in [
        "https://api.openai.com",
        "http://example.org",
        "http://127.0.0.1@evil.test",
        "http://localhost.evil.test",
        "http://127.0.0.1:80/redirect",
    ]:
        with pytest.raises(ValueError):
            CachedClient(tmp_path / "cache.sqlite", url, "a" * 64, {})
    calls = []

    def response(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "RESULT: 3/3"}}],
                "usage": {"completion_tokens": 8},
            },
        )

    transport = httpx.MockTransport(response)
    messages = [Message(role="user", content="fixture prompt")]
    params = dict(temperature=0.0, top_p=1.0, max_tokens=1024, seed=0)
    cache = tmp_path / "cache.sqlite"
    with CachedClient(
        cache, "http://127.0.0.1:8080", "a" * 64, {"ctx": 8192}, transport=transport
    ) as client:
        first = client.complete(messages, params)
        assert not first.cache_hit
        assert client.complete(messages, params).cache_hit
        assert client.complete(messages, {**params, "seed": 1}).cache_hit is False
    with CachedClient(
        cache, "http://127.0.0.1:8080", "a" * 64, {"ctx": 8192}, transport=transport
    ) as resumed:
        assert resumed.complete(messages, params).raw_output == first.raw_output
        assert resumed.complete(messages, params).timestamp == first.timestamp
    assert len(calls) == 2
    assert "fixture prompt" not in str(calls[0].url)
    with CachedClient(
        cache, "http://127.0.0.1:8080", "b" * 64, {"ctx": 8192}, transport=transport
    ) as other:
        assert not other.complete(messages, params).cache_hit
    assert len(calls) == 3


def test_completion_request_preserves_existing_cache_identity() -> None:
    messages = [Message(role="user", content="fixture prompt")]
    parameters = dict(temperature=0.0, top_p=1.0, max_tokens=1024, seed=0)
    flags = {"ctx": 8192}
    identity = {
        "model_file_sha256": "a" * 64,
        "server_flags_that_affect_output": flags,
        "messages": [message.model_dump() for message in messages],
        **parameters,
    }
    serialized = json.dumps(identity, sort_keys=True, ensure_ascii=False, allow_nan=False)
    key, actual, payload = completion_request("a" * 64, flags, messages, parameters)
    assert (key, actual) == (hashlib.sha256(serialized.encode()).hexdigest(), serialized)
    assert payload == {"messages": [message.model_dump() for message in messages], **parameters}


def test_failed_http_call_is_not_cached(tmp_path: Path) -> None:
    count = 0

    def response(request: httpx.Request) -> httpx.Response:
        nonlocal count
        count += 1
        return httpx.Response(500, text="failed")

    with CachedClient(
        tmp_path / "cache.sqlite",
        "http://127.0.0.1:8080",
        "a" * 64,
        {},
        transport=httpx.MockTransport(response),
    ) as client:
        for _ in range(2):
            with pytest.raises(httpx.HTTPStatusError):
                client.complete(
                    [Message(role="user", content="test")],
                    dict(temperature=0.0, top_p=1.0, max_tokens=10, seed=0),
                )
    assert count == 2


def test_cache_hit_never_starts_server(tmp_path: Path) -> None:
    starts = []
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200, json={"choices": [{"message": {"content": "RESULT: 1/3"}}]}
        )
    )
    parameters = dict(temperature=0.0, top_p=1.0, max_tokens=1024, seed=0)
    messages = [Message(role="user", content="private fixture prompt")]
    with CachedClient(
        tmp_path / "cache.sqlite",
        "http://127.0.0.1:8080",
        "a" * 64,
        {},
        transport=transport,
        on_miss=lambda: starts.append(True),
    ) as client:
        client.complete(messages, parameters)
    assert len(starts) == 1
    starts.clear()
    with CachedClient(
        tmp_path / "cache.sqlite",
        "http://127.0.0.1:8080",
        "a" * 64,
        {},
        transport=transport,
        on_miss=lambda: starts.append(True),
    ) as client:
        assert client.complete(messages, parameters).cache_hit
    assert starts == []


@pytest.mark.parametrize("changed", [{"temperature": 0.5}, {"top_p": 0.9}, {"max_tokens": 2048}])
def test_all_sampling_parameters_affect_cache(tmp_path: Path, changed: dict) -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200, json={"choices": [{"message": {"content": "RESULT: 1/3"}}]}
        )
    )
    parameters = dict(temperature=0.0, top_p=1.0, max_tokens=1024, seed=0)
    with CachedClient(
        tmp_path / "cache.sqlite", "http://127.0.0.1:8080", "a" * 64, {}, transport=transport
    ) as client:
        messages = [Message(role="user", content="fixture")]
        client.complete(messages, parameters)
        assert not client.complete(messages, {**parameters, **changed}).cache_hit


def test_one_server_at_a_time_and_cleanup(tmp_path: Path) -> None:
    script = tmp_path / "fake_server.py"
    script.write_text("import time\ntime.sleep(60)\n")
    cfg = load_config()["server"]
    paths = Paths(tmp_path)
    # This process is a hand-written test server, never a candidate or harness.
    server = ModelServer(paths, cfg, [sys.executable, str(script)], [], health=lambda: True)
    with server:
        assert paths.server_lock.exists()
        with pytest.raises(ServerError, match="already"):
            with ModelServer(paths, cfg, [sys.executable, str(script)], [], health=lambda: True):
                pass
        assert server.process.poll() is None
    assert server.process.poll() is not None
    assert not paths.server_lock.exists()


def test_server_startup_failure_releases_lock(tmp_path: Path) -> None:
    paths = Paths(tmp_path)
    cfg = {**load_config()["server"], "startup_seconds": 0.2}
    with pytest.raises(ServerError):
        with ModelServer(
            paths, cfg, [sys.executable, "-c", "raise SystemExit(1)"], [], health=lambda: False
        ):
            pass
    assert not paths.server_lock.exists()
