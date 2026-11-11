import pytest

from app.domain.accounts import InvalidEmailError
from app.services.email_address import MESSAGE, normalize_email


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("jane@example.com", "jane@example.com"),
        ("  Jane.Doe@Example.COM  ", "jane.doe@example.com"),
        ("jane+jobs@example.com", "jane+jobs@example.com"),
    ],
)
def test_addresses_are_checked_and_lowercased(raw: str, expected: str) -> None:
    assert normalize_email(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "   ",
        "not an email",
        "jane@",
        "@example.com",
        "jane@@example.com",
        "jane@example",
        "jane@exa mple.com",
        "jane@exam\nple.com",
        "local@cvagent.invalid",
        "someone@anything.invalid",
        "x" * 300 + "@example.com",
    ],
)
def test_invalid_addresses_are_refused_with_a_safe_message(raw: str) -> None:
    with pytest.raises(InvalidEmailError) as raised:
        normalize_email(raw)

    assert str(raised.value) == MESSAGE
