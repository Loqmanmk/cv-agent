from app.services.reading_cache import ReadingCache, key_of


class Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def test_a_value_is_made_once_then_reused() -> None:
    cache = ReadingCache[str]()
    made: list[str] = []

    def make() -> str:
        made.append("x")
        return "value"

    assert cache.get_or_make("k", make) == "value"
    assert cache.get_or_make("k", make) == "value"
    assert made == ["x"]


def test_a_value_expires() -> None:
    clock = Clock()
    cache = ReadingCache[str](keep_seconds=10, clock=clock)
    cache.put("k", "value")

    clock.now = 10
    assert cache.get("k") == "value"
    clock.now = 11
    assert cache.get("k") is None


def test_the_oldest_value_goes_first_past_the_limit() -> None:
    cache = ReadingCache[int](max_entries=2)
    cache.put("a", 1)
    cache.put("b", 2)

    cache.put("c", 3)

    assert (cache.get("a"), cache.get("b"), cache.get("c")) == (None, 2, 3)


def test_keys_are_hashes_of_the_exact_content() -> None:
    assert key_of("offer") == key_of(b"offer")
    assert key_of("offer") != key_of("offer ")
    assert len(key_of("x")) == 64
