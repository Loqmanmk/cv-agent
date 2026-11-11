import threading
import time
from collections import defaultdict, deque
from collections.abc import Callable

MAX_TRACKED_KEYS = 10_000


class RateLimiter:
    """Sliding window: at most `max_requests` per `window_seconds` for each client.

    Counters live in memory, so they reset when the server restarts and are not shared between
    several server processes. Idle clients are forgotten, so random keys cannot fill the memory.
    """

    def __init__(
        self,
        max_requests: int,
        window_seconds: float,
        clock: Callable[[], float] = time.monotonic,
        max_keys: int = MAX_TRACKED_KEYS,
    ) -> None:
        if max_requests < 1 or window_seconds <= 0:
            raise ValueError("max_requests must be at least 1 and window_seconds positive.")
        self._max = max_requests
        self._window = window_seconds
        self._clock = clock
        self._max_keys = max_keys
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    @property
    def tracked_keys(self) -> int:
        return len(self._hits)

    def acquire(self, client: str) -> float:
        """Record a request and return 0.0, or return the seconds to wait if over the limit."""
        now = self._clock()
        with self._lock:
            if len(self._hits) > self._max_keys:
                self._sweep(now)
            hits = self._hits[client]
            while hits and now - hits[0] >= self._window:
                hits.popleft()
            if len(hits) >= self._max:
                return self._window - (now - hits[0])
            hits.append(now)
            return 0.0

    def _sweep(self, now: float) -> None:
        stale = [
            client
            for client, hits in self._hits.items()
            if not hits or now - hits[-1] >= self._window
        ]
        for client in stale:
            del self._hits[client]
