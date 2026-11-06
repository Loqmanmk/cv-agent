import pytest

from app.infrastructure.application_factory import build_application_service
from app.services.application_service import ApplicationService
from tests.test_config import IsolatedSettings


def test_the_factory_builds_the_service(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    assert isinstance(build_application_service(IsolatedSettings()), ApplicationService)
