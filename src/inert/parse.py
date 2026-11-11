import re
from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class ParsedResult:
    parse_status: Literal["ok", "fail"]
    k_pred: int | None = None
    n_pred: int | None = None
    R_sim: float | None = None
    pred_pass: bool | None = None


def parse_result(raw: str, n_tests: int) -> ParsedResult:
    if n_tests <= 0:
        raise ValueError("n_tests must be positive.")
    visible = re.sub(r"<think>.*?</think>", "", raw, flags=re.S)
    matches = re.findall(r"RESULT:\s*(\d+)\s*/\s*(\d+)", visible)
    if not matches:
        return ParsedResult("fail")
    k, n = map(int, matches[-1])
    if n != n_tests or not 0 <= k <= n:
        return ParsedResult("fail", k, n)
    return ParsedResult("ok", k, n, k / n, k == n)
