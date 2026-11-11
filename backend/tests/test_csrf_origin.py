import pytest

from app.api.csrf import origin_allowed

ALLOWED = ["http://localhost:3000", "https://app.example.com"]


def test_a_missing_origin_means_a_client_that_is_not_a_browser() -> None:
    assert origin_allowed(None, ALLOWED) is True


@pytest.mark.parametrize("origin", ALLOWED)
def test_the_configured_origins_are_allowed(origin: str) -> None:
    assert origin_allowed(origin, ALLOWED) is True


@pytest.mark.parametrize(
    "origin",
    [
        "null",
        "",
        "http://evil.example",
        "http://localhost:3001",
        "https://localhost:3000",
        "http://localhost:3000/",
        "http://localhost.evil.example:3000",
        "http://localhost:3000.evil.example",
    ],
)
def test_every_other_origin_is_refused(origin: str) -> None:
    assert origin_allowed(origin, ALLOWED) is False


def test_when_nothing_is_configured_every_browser_origin_is_refused() -> None:
    assert origin_allowed("http://localhost:3000", []) is False
    assert origin_allowed(None, []) is True
