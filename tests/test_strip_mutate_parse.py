import ast

import pytest

from inert.mutate import mutants
from inert.parse import parse_result
from inert.strip import natural_text, strip_text

SAMPLES = [
    ("# note\nx = 2\n", "x = 2"),
    ('"""module"""\nx = 2', "x = 2"),
    ('def f():\n    """doc"""\n    return 2', "def f():\n    return 2"),
    ('async def f():\n    """doc"""\n    return 2', "async def f():\n    return 2"),
    ('class A:\n    """doc"""', "class A:\n    pass"),
    ('def f():\n    """doc"""', "def f():\n    pass"),
    ('"""only doc"""', "pass"),
    ('x = "# not comment" # comment', 'x = "# not comment"'),
    (
        'def f():\n    x = 1\n    "keep"\n    return x',
        'def f():\n    x = 1\n    "keep"\n    return x',
    ),
    (
        'class A:\n    def f(self):\n        "doc"\n        return 4 # end',
        "class A:\n    def f(self):\n        return 4",
    ),
]


@pytest.mark.parametrize(("source", "expected"), SAMPLES)
def test_strip_examples(source: str, expected: str) -> None:
    assert ast.dump(ast.parse(strip_text(source))) == ast.dump(ast.parse(expected))
    assert strip_text(strip_text(source)) == strip_text(source)


@pytest.mark.docker
@pytest.mark.parametrize(
    ("source", "expected", "assertion"),
    [
        (*sample, assertion)
        for sample, assertion in zip(
            SAMPLES,
            [
                "assert x == 2",
                "assert x == 2",
                "assert f() == 2",
                "import asyncio\nassert asyncio.run(f()) == 2",
                "assert isinstance(A(), A)",
                "assert f() is None",
                "assert True",
                'assert x == "# not comment"',
                "assert f() == 1",
                "assert A().f() == 4",
            ],
            strict=True,
        )
    ],
)
def test_strip_behavior_in_sandbox(source: str, expected: str, assertion: str) -> None:
    from inert.config import Paths, load_config
    from inert.harness import render_harness
    from inert.sandbox import DockerSandbox

    sandbox = DockerSandbox(Paths.discover(), load_config()["sandbox"])
    harness = render_harness([assertion])
    original = sandbox.run(source, harness)
    stripped = sandbox.run(strip_text(source), harness)
    assert original.stdout == stripped.stdout == "RESULT: 1/1\n"


def test_natural_text_in_source_order() -> None:
    source = '# first\n"""module doc"""\ndef f():\n    "function doc"\n    x = "# string" # last\n'
    assert natural_text(source).splitlines() == ["first", "module doc", "function doc", "last"]
    assert natural_text('x = "# string"') == ""
    with pytest.raises(SyntaxError):
        strip_text("def broken(")


@pytest.mark.parametrize(
    ("source", "operator", "expected"),
    [
        ("def f(x): return x < 2", "comparison", "def f(x): return x <= 2"),
        ("def f(x): return x + 2", "off_by_one", "def f(x): return x + 3"),
        ("def f(x): return x + 2", "arithmetic", "def f(x): return x - 2"),
        ("def f(x): return x[1:4]", "boundary_slice", "def f(x): return x[1:4 - 1]"),
    ],
)
def test_mutator_first_site(source: str, operator: str, expected: str) -> None:
    found = dict(mutants(source))
    assert ast.dump(ast.parse(found[operator])) == ast.dump(ast.parse(expected))


def test_mutators_order_and_boolean_constants() -> None:
    found = mutants("def f(x): return x < 2 and x + 3 > 4")
    assert [name for name, _ in found] == ["comparison", "off_by_one", "arithmetic"]
    assert "True" in dict(mutants("def f(x): return True if x else 2"))["off_by_one"]
    assert not mutants("def f(): return True")
    assert "x <= 2" in dict(found)["comparison"]
    assert "x + 3 > 4" in dict(found)["comparison"]


@pytest.mark.parametrize(
    ("raw", "n_tests", "expected"),
    [
        ("RESULT: 3/5", 5, (3, 5)),
        ("RESULT: 1/5\nRESULT: 4 / 5", 5, (4, 5)),
        ("<think>RESULT: 5/5</think>RESULT: 2/5", 5, (2, 5)),
        ("<think>RESULT: 5/5</think>", 5, None),
        ("RESULT: 6/5", 5, None),
        ("RESULT: 2/4", 5, None),
        ("RESULT: -1/5", 5, None),
        ("no result", 5, None),
    ],
)
def test_parser(raw: str, n_tests: int, expected: tuple[int, int] | None) -> None:
    result = parse_result(raw, n_tests)
    assert result.parse_status == ("ok" if expected else "fail")
    if expected:
        assert (result.k_pred, result.n_pred) == expected
        assert result.R_sim == expected[0] / expected[1]
        assert result.pred_pass == (expected[0] == expected[1])
    else:
        assert result.R_sim is None and result.pred_pass is None
