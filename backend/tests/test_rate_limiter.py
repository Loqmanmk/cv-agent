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
