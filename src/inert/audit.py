import logging
import time
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime

from inert.config import Paths
from inert.schemas import atomic_text


class StopRequired(RuntimeError):
    """A design gate requires the project owner's decision."""


def record_deviation(paths: Paths, description: str, scoring_started: bool) -> None:
    existing = (
        paths.deviations.read_text(encoding="utf-8")
        if paths.deviations.exists()
        else "# Pilot deviations\n"
    )
    stamp = datetime.now(UTC).isoformat()
    atomic_text(
        paths.deviations,
        existing
        + f"\n## {stamp}\n\n{description}\n\n"
        + f"Scoring had already started: {scoring_started}.\n",
    )


@contextmanager
def stage_log(paths: Paths, stage: str) -> Iterator[logging.Logger]:
    path = paths.log_file(stage)
    path.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger(f"inert.{stage}.{path.stem}")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    handler = logging.FileHandler(path, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)
    try:
        logger.info("Started stage %s", stage)
        yield logger
        logger.info("Completed stage %s", stage)
    except BaseException:
        logger.exception("Stage failed")
        raise
    finally:
        handler.close()
        logger.removeHandler(handler)


class Progress:
    def __init__(self, total: int, every: int = 1) -> None:
        self.total = total
        self.done = 0
        self.started = time.perf_counter()
        self.last_print = self.started
        self.every = every

    def advance(self) -> None:
        self.done += 1
        now = time.perf_counter()
        if self.done % self.every and self.done != self.total and now - self.last_print < 30:
            return
        self.last_print = now
        mean = (time.perf_counter() - self.started) / self.done
        left = self.total - self.done
        print(
            f"{self.done}/{self.total} items done; {left} left; "
            f"{mean:.2f} mean seconds/call; {mean * left:.0f}s remaining",
            flush=True,
        )
