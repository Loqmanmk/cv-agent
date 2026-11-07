import threading
import time
from collections import defaultdict, deque
from collections.abc import Callable


class RateLimiter:
    """Sliding window: at most `max_requests` per `window_seconds` for each client."""

    def __init__(
        self,
        max_requests: int,
        window_seconds: float,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if max_requests < 1 or window_seconds <= 0:
            raise ValueError("max_requests must be at least 1 and window_seconds positive.")
        self._max = max_requests
        self._window = window_seconds
        self._clock = clock
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def acquire(self, client: str) -> float:
        """Record a request and return 0.0, or return the seconds to wait if over the limit."""
        now = self._clock()
        with self._lock:
            hits = self._hits[client]
            while hits and now - hits[0] >= self._window:
                hits.popleft()
            if len(hits) >= self._max:
                return self._window - (now - hits[0])
            hits.append(now)
            return 0.0
