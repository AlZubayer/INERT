import hashlib
from pathlib import Path

import pytest

from inert.config import Paths, load_config
from inert.models import resolve_model
from inert.p0 import feasibility_decision
from inert.proposer import extract_code
from inert.verification import load_mbpp


def test_model_hash_verified_before_serving(tmp_path: Path) -> None:
    file = tmp_path / "data" / "model.gguf"
    file.parent.mkdir()
    file.write_bytes(b"handwritten model metadata fixture, not a real model")
    digest = hashlib.sha256(file.read_bytes()).hexdigest()
    model = {
        "files": [{"filename": "model-Q4_K_M.gguf", "path": "data/model.gguf", "sha256": digest}]
    }
    selected = resolve_model(Paths(tmp_path), model, "Q4_K_M")
    assert selected.files == [file]
    file.write_bytes(b"changed")
    with pytest.raises(ValueError, match="SHA-256"):
        resolve_model(Paths(tmp_path), model, "Q4_K_M")
    with pytest.raises(ValueError):
        resolve_model(
            Paths(tmp_path), {"files": [{**model["files"][0], "path": "../escape"}]}, "Q4_K_M"
        )


@pytest.mark.parametrize(
    ("seconds", "expected"), [(20, "full"), (20.1, "reduced"), (50, "reduced"), (50.1, "drop_wm_a")]
)
def test_p0_boundaries(seconds: float, expected: str) -> None:
    assert feasibility_decision(seconds, load_config()["thresholds"]) == expected


def test_extract_first_python_block_only() -> None:
    fence = chr(96) * 3
    text = f"Explanation\n{fence}python\ndef f(): return 1\n{fence}\n{fence}python\nwrong\n{fence}"
    assert extract_code(text) == "def f(): return 1"
    assert extract_code("def f(): return 2") == "def f(): return 2"


def test_lfs_dataset_uses_content_sha_not_git_pointer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    content = b"parquet fixture bytes"
    path = tmp_path / "data/datasets/sanitized/test-00000.parquet"
    path.parent.mkdir(parents=True)
    path.write_bytes(content)
    registry = {
        "dataset": {
            "files": [
                {
                    "filename": "sanitized/test-00000.parquet",
                    "sha256": hashlib.sha256(content).hexdigest(),
                    "git_blob": "0" * 40,
                }
            ]
        }
    }
    monkeypatch.setattr("datasets.load_dataset", lambda *args, **kwargs: {"loaded": True})
    assert load_mbpp(Paths(tmp_path), registry, offline=True) == {"loaded": True}
    path.write_bytes(b"corrupted")
    with pytest.raises(ValueError, match="SHA-256"):
        load_mbpp(Paths(tmp_path), registry, offline=True)
