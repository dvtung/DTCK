"""Walk-forward / rolling-window split helpers (BACKTESTING.md §5, §17).

Prevents data leakage by construction: a test window never overlaps subsequent
training. ``run_type`` values are recorded on ``backtests.run_type`` (in-sample,
out-of-sample, walk-forward, rolling-window).
"""

from __future__ import annotations

from collections.abc import Iterator

__all__ = [
    "WalkForwardWindow",
    "walk_forward_windows",
    "rolling_windows",
    "RUN_IN_SAMPLE",
    "RUN_OUT_OF_SAMPLE",
    "RUN_WALK_FORWARD",
    "RUN_ROLLING",
]

RUN_IN_SAMPLE = "in-sample"
RUN_OUT_OF_SAMPLE = "out-of-sample"
RUN_WALK_FORWARD = "walk-forward"
RUN_ROLLING = "rolling-window"


class WalkForwardWindow:
    """One (train, test) split expressed as inclusive index ranges."""

    __slots__ = ("train_start", "train_end", "test_start", "test_end")

    def __init__(self, train_start: int, train_end: int, test_start: int, test_end: int) -> None:
        self.train_start = train_start
        self.train_end = train_end
        self.test_start = test_start
        self.test_end = test_end

    @property
    def train_len(self) -> int:
        return self.train_end - self.train_start + 1

    @property
    def test_len(self) -> int:
        return self.test_end - self.test_start + 1

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return (
            f"Window(train=[{self.train_start},{self.train_end}], "
            f"test=[{self.test_start},{self.test_end}])"
        )


def walk_forward_windows(
    n: int,
    train_len: int,
    test_len: int,
    step: int | None = None,
) -> Iterator[WalkForwardWindow]:
    """Yield walk-forward (train, test) windows over ``n`` observations.

    ``step`` defaults to ``test_len`` (non-overlapping test folds). Test window
    always immediately follows its train window, so features never leak future
    information. Requires ``n >= train_len + test_len``.
    """
    step = step or test_len
    if n < train_len + test_len or train_len < 1 or test_len < 1 or step < 1:
        return
    test_start = train_len
    while test_start + test_len - 1 < n:
        train_start = max(0, test_start - train_len)
        yield WalkForwardWindow(
            train_start=train_start,
            train_end=test_start - 1,
            test_start=test_start,
            test_end=test_start + test_len - 1,
        )
        test_start += step


def rolling_windows(n: int, window_len: int, step: int = 1) -> Iterator[tuple[int, int]]:
    """Yield fixed-size (start, end) inclusive rolling windows."""
    if n < window_len or window_len < 1 or step < 1:
        return
    start = 0
    while start + window_len - 1 < n:
        yield (start, start + window_len - 1)
        start += step
