import hashlib
import threading
import time
from collections import OrderedDict
from collections.abc import Callable

# Long enough to check the score of an offer and then create the application.
KEEP_SECONDS = 30 * 60.0
MAX_ENTRIES = 200


def key_of(data: str | bytes) -> str:
    raw = data.encode("utf-8") if isinstance(data, str) else data
    return hashlib.sha256(raw).hexdigest()


class ReadingCache[T]:
    """What the AI read from an offer or a CV, kept a short while in memory.

    Checking the match score reads the offer and the CV; creating the application right
    after reuses them instead of asking the AI again. Keys are hashes of the exact content,
    so an entry is only found again by someone who has that same content.
    """

    def __init__(
        self,
        keep_seconds: float = KEEP_SECONDS,
        max_entries: int = MAX_ENTRIES,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._keep = keep_seconds
        self._max = max_entries
        self._clock = clock
        self._lock = threading.Lock()
        self._entries: OrderedDict[str, tuple[float, T]] = OrderedDict()

    def get(self, key: str) -> T | None:
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return None
            saved_at, value = entry
            if self._clock() - saved_at > self._keep:
                del self._entries[key]
                return None
            return value

    def put(self, key: str, value: T) -> None:
        with self._lock:
            self._entries[key] = (self._clock(), value)
            self._entries.move_to_end(key)
            while len(self._entries) > self._max:
                self._entries.popitem(last=False)

    def get_or_make(self, key: str, make: Callable[[], T]) -> T:
        found = self.get(key)
        if found is not None:
            return found
        value = make()
        self.put(key, value)
        return value
