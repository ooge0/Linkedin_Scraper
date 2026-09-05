"""
rate_limiter.py

A small sliding-window rate limiter used to cap expensive scraper actions
(opening a job detail panel) to a maximum count per rolling time window.

A fixed-window reset (counter zeroed every wall-clock hour) would allow a
burst of up to 2x the cap right at the boundary. A rolling window bounds
any window_seconds-wide slice of time to max_per_window, which is what
"REQUESTS_PER_HOUR" needs to mean for a run that can span many hours.
"""

import time
from collections import deque
from typing import Callable


class RateLimiter:
    """
    Tracks timestamps of recent actions and reports whether another one
    is allowed without exceeding max_per_window actions in the last
    window_seconds.
    """

    def __init__(
        self,
        max_per_window: int,
        window_seconds: float = 3600.0,
        now_fn: Callable[[], float] = time.monotonic,
    ):
        self.max_per_window = max_per_window
        self.window_seconds = window_seconds
        self._now_fn = now_fn
        self._timestamps: deque[float] = deque()

    def _prune(self):
        cutoff = self._now_fn() - self.window_seconds
        while self._timestamps and self._timestamps[0] <= cutoff:
            self._timestamps.popleft()

    def allowed(self) -> bool:
        """True if one more action can happen right now without exceeding the cap."""
        self._prune()
        return len(self._timestamps) < self.max_per_window

    def record(self):
        """Record that an action just happened."""
        self._timestamps.append(self._now_fn())

    def count(self) -> int:
        """Actions currently inside the window, after pruning expired ones."""
        self._prune()
        return len(self._timestamps)
