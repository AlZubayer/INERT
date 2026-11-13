import hashlib
import sqlite3
from pathlib import Path

import pytest

from inert.config import Paths, load_config
from inert.harness import render_harness
from inert.sandbox import DockerSandbox, SandboxError


@pytest.mark.docker
@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("def f(x): return x", "RESULT: 3/3\n"),
        ("def f(x): return 0", "RESULT: 0/3\n"),
        ("def broken(", "RESULT: 0/3\n"),
        ("def f(x):\n    while True: pass", "RESULT: 0/3\n"),
        (
            "import socket\ndef f(x):\n"
            '    socket.create_connection(("1.1.1.1", 80), timeout=0.2)\n    return x',
            "RESULT: 0/3\n",
        ),
    ],
)
def test_sandbox_cases(source: str, expected: str, tmp_path: Path) -> None:
    cfg = load_config()
    sandbox = DockerSandbox(Paths(tmp_path), cfg["sandbox"])
    result = sandbox.run(source, render_harness(["assert f(1) == 1"] * 3))
    assert result.stdout == expected
    assert result.returncode == 0


@pytest.mark.docker
def test_sandbox_top_level_timeout_cleanup(tmp_path: Path) -> None:
    cfg = load_config()
    sandbox = DockerSandbox(Paths(tmp_path), {**cfg["sandbox"], "wall_seconds": 1})
    with pytest.raises(SandboxError, match="timed out"):
        sandbox.run("while True: pass", render_harness(["assert True"] * 3))


@pytest.mark.docker
def test_sandbox_has_no_network_or_writable_root(tmp_path: Path) -> None:
    source = """import os
def f():
    assert not os.path.exists('/work/AGENTS.md')
    assert len(os.listdir('/sys/class/net')) == 1
    try:
        open('/forbidden', 'w')
    except OSError:
        return True
    return False
"""
    sandbox = DockerSandbox(Paths(tmp_path), load_config()["sandbox"])
    result = sandbox.run(source, render_harness(["assert f()"] * 3))
    assert result.stdout == "RESULT: 3/3\n"


@pytest.mark.docker
def test_cache_bypass_and_cached_mode(tmp_path: Path) -> None:
    sandbox = DockerSandbox(Paths(tmp_path), load_config()["sandbox"])
    cache = sandbox.paths.cache("sandbox")
    harness = render_harness(["assert f(1) == 1"])
    source = "def f(x): return x"
    first = sandbox.run(source, harness, use_cache=False)
    assert first.stdout == "RESULT: 1/1\n"
    assert not cache.exists()
    cached = sandbox.run(source, harness, use_cache=True)
    assert cached == first
    with sqlite3.connect(cache) as database:
        assert database.execute("SELECT COUNT(*) FROM executions").fetchone()[0] == 1
    before = hashlib.sha256(cache.read_bytes()).hexdigest()
    assert sandbox.run(source, harness, use_cache=True) == first
    assert sandbox.run(source, harness, use_cache=False) == first
    assert hashlib.sha256(cache.read_bytes()).hexdigest() == before
