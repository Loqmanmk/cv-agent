import pytest

from app.services.password_policy import (
    MAX_LENGTH,
    MIN_LENGTH,
    normalize_password,
    password_problems,
)

EMAIL = "jane.doe@example.com"


def test_a_good_passphrase_is_accepted() -> None:
    assert password_problems("correct horse battery staple", EMAIL) == []


def test_no_symbol_or_digit_is_required() -> None:
    assert password_problems("just lowercase words here", EMAIL) == []


def test_a_short_password_is_refused() -> None:
    problems = password_problems("x" * (MIN_LENGTH - 1), EMAIL)

    assert problems[0] == "Use at least 12 characters."


def test_the_shortest_allowed_password_is_accepted() -> None:
    assert password_problems("abcdefghijkl", EMAIL) == []


def test_a_password_that_is_too_long_is_refused() -> None:
    assert "Use at most 128 characters." in password_problems("ab" * MAX_LENGTH, EMAIL)


def test_the_longest_allowed_password_is_accepted() -> None:
    assert password_problems("abcdefgh" * 16, EMAIL) == []


def test_a_password_with_too_few_different_characters_is_refused() -> None:
    assert password_problems("abababababab", EMAIL) == ["Use more different characters."]


def test_the_email_name_may_not_be_part_of_the_password() -> None:
    assert password_problems("my-JANE.DOE-secret", EMAIL) == [
        "Do not use your email address in the password."
    ]


def test_a_very_short_email_name_is_not_checked() -> None:
    assert password_problems("abc is in this password", "abc@example.com") == []


@pytest.mark.parametrize("common", ["password1234", "PASSWORD12345", "123456789012"])
def test_common_passwords_are_refused(common: str) -> None:
    assert "This password is too common." in password_problems(common, EMAIL)


def test_all_problems_are_reported_together() -> None:
    assert len(password_problems("aaaa", EMAIL)) == 2


def test_the_same_text_typed_differently_becomes_the_same_password() -> None:
    assert normalize_password("cafe\u0301") == normalize_password("caf\u00e9")
    assert normalize_password("\uff50\uff41\uff53\uff53") == "pass"
