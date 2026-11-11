import pytest

from app.api.rate_limit import RateLimiter


class Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def test_allows_requests_up_to_the_limit() -> None:
    limiter = RateLimiter(2, 60, Clock())

    assert limiter.acquire("a") == 0.0
    assert limiter.acquire("a") == 0.0


def test_blocks_the_request_over_the_limit_and_says_how_long_to_wait() -> None:
    clock = Clock()
    limiter = RateLimiter(2, 60, clock)
    limiter.acquire("a")
    clock.now = 10
    limiter.acquire("a")
    clock.now = 20

    assert limiter.acquire("a") == pytest.approx(40)


def test_allows_again_when_the_window_has_passed() -> None:
    clock = Clock()
    limiter = RateLimiter(1, 60, clock)
    limiter.acquire("a")
    clock.now = 61

    assert limiter.acquire("a") == 0.0


def test_clients_are_limited_independently() -> None:
    limiter = RateLimiter(1, 60, Clock())
    limiter.acquire("a")

    assert limiter.acquire("b") == 0.0


def test_rejects_invalid_settings() -> None:
    with pytest.raises(ValueError, match="at least 1"):
        RateLimiter(0, 60)


def test_idle_clients_are_forgotten_when_the_table_grows() -> None:
    clock = Clock()
    limiter = RateLimiter(5, 60, clock, max_keys=2)
    for name in ("a", "b", "c"):
        limiter.acquire(name)
    assert limiter.tracked_keys == 3

    clock.now = 120
    limiter.acquire("d")

    assert limiter.tracked_keys == 1


def test_active_clients_survive_the_sweep() -> None:
    clock = Clock()
    limiter = RateLimiter(5, 60, clock, max_keys=2)
    for name in ("a", "b", "c"):
        limiter.acquire(name)
    clock.now = 30
    limiter.acquire("a")

    clock.now = 70
    limiter.acquire("d")

    assert limiter.tracked_keys == 2


def test_a_blocked_client_stays_blocked_after_a_sweep() -> None:
    clock = Clock()
    limiter = RateLimiter(1, 60, clock, max_keys=1)
    limiter.acquire("a")
    limiter.acquire("b")

    assert limiter.acquire("a") > 0
