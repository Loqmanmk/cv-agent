import pytest

from tests.test_config import IsolatedSettings


def test_the_database_url_is_optional_and_never_printed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert IsolatedSettings().database_url is None

    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:secret-pw@localhost/db")
    settings = IsolatedSettings()

    assert settings.database_url is not None
    assert settings.database_url.get_secret_value().endswith("@localhost/db")
    assert "secret-pw" not in repr(settings)
