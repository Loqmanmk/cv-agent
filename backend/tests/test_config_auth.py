import pytest

from tests.test_config import IsolatedSettings


def test_the_defaults_are_safe_for_a_private_beta(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("COOKIE_SECURE", raising=False)
    monkeypatch.delenv("REGISTRATION_OPEN", raising=False)

    settings = IsolatedSettings()

    assert settings.registration_open is False
    assert settings.cookie_secure is False
    assert settings.session_cookie_name == "session"


def test_a_secure_cookie_gets_the_host_prefix(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COOKIE_SECURE", "true")

    assert IsolatedSettings().session_cookie_name == "__Host-session"


def test_registration_can_be_opened(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REGISTRATION_OPEN", "true")

    assert IsolatedSettings().registration_open is True
