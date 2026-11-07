from app.services.translation_guard import TranslationViolationError
from tests.test_api import StubService, make_client, upload


def test_translation_rejections_return_the_violations() -> None:
    error = TranslationViolationError(["profile was not translated"])

    response = upload(make_client(StubService(error)))

    assert response.status_code == 502
    assert response.json()["violations"] == ["profile was not translated"]
