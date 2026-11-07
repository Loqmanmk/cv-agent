import pytest

from app.infrastructure.application_factory import (
    build_application_service,
    build_render_service,
)
from app.services.application_service import ApplicationService
from app.services.render_service import RenderService
from tests.test_config import IsolatedSettings


def test_the_factory_builds_the_service(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    assert isinstance(build_application_service(IsolatedSettings()), ApplicationService)


def test_the_factory_builds_the_render_service_without_an_api_key() -> None:
    assert isinstance(build_render_service(), RenderService)
