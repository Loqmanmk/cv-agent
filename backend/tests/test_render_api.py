import base64
from typing import Any

from fastapi.testclient import TestClient

from app.api.auth_dependencies import require_user
from app.api.dependencies import get_render_rate_limiter, get_render_service
from app.api.rate_limit import RateLimiter
from app.main import create_app
from tests.auth_helpers import FAKE_SESSION
from tests.test_api import make_client, make_settings, upload
from tests.test_application_service import (
    FAKE_PDF,
    FakeConverter,
    ai_answers,
    make_docx,
    make_service,
)
from tests.test_docx_parser import make_png
from tests.test_letter_html_builder import make_letter
from tests.test_render_service import make_service as make_render_service
from tests.test_tailoring_guard import make_cv

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def make_render_client(limit: int = 100) -> tuple[TestClient, FakeConverter]:
    service, converter = make_render_service()
    app = create_app(make_settings())
    limiter = RateLimiter(limit, 3600)
    app.dependency_overrides[get_render_service] = lambda: service
    app.dependency_overrides[get_render_rate_limiter] = lambda: limiter
    app.dependency_overrides[require_user] = lambda: FAKE_SESSION
    return TestClient(app, raise_server_exceptions=False), converter


def payload(**overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "cv": make_cv().model_dump(),
        "letter": make_letter().model_dump(),
        "language": "fr",
        "photo_base64": None,
    }
    body.update(overrides)
    return body


def test_the_application_response_carries_the_data_for_the_review_screen() -> None:
    service, _, _ = make_service(ai_answers())

    body = upload(make_client(service)).json()

    assert body["cv"]["profile"] == "Rewritten profile."
    assert body["original_cv"]["profile"] == make_cv().profile
    assert body["letter"]["signature"] == "Jane Doe"
    assert body["photo_base64"] is None


def test_the_application_response_returns_the_clean_photo() -> None:
    service, _, _ = make_service(ai_answers())

    body = upload(make_client(service), content=make_docx(with_photo=True)).json()

    assert body["photo_used"] is True
    assert base64.b64decode(body["photo_base64"]).startswith(PNG_SIGNATURE)


def test_renders_the_documents() -> None:
    client, _ = make_render_client()

    response = client.post("/render", json=payload())

    assert response.status_code == 200
    assert base64.b64decode(response.json()["cv_pdf_base64"]) == FAKE_PDF
    assert base64.b64decode(response.json()["letter_pdf_base64"]) == FAKE_PDF


def test_renders_only_the_cv_when_there_is_no_letter() -> None:
    client, converter = make_render_client()

    response = client.post("/render", json=payload(letter=None))

    assert response.status_code == 200
    assert response.json()["letter_pdf_base64"] is None
    assert len(converter.pages) == 1


def test_renders_the_edited_text() -> None:
    client, converter = make_render_client()
    cv = make_cv().model_dump()
    cv["profile"] = "Edited by the user."

    client.post("/render", json=payload(cv=cv))

    assert any("Edited by the user." in page for page in converter.pages)


def test_sends_the_photo_back_into_the_cv() -> None:
    client, converter = make_render_client()
    photo = base64.b64encode(make_png(300, 353)).decode("ascii")

    response = client.post("/render", json=payload(photo_base64=photo))

    assert response.status_code == 200
    assert any("data:image/png;base64," in page for page in converter.pages)


def test_refuses_a_photo_that_is_not_base64() -> None:
    client, _ = make_render_client()

    response = client.post("/render", json=payload(photo_base64="!!! not base64 !!!"))

    assert response.status_code == 422
    assert "base64" in response.json()["detail"]


def test_refuses_a_photo_that_is_not_an_image() -> None:
    client, _ = make_render_client()
    photo = base64.b64encode(b"not an image").decode("ascii")

    assert client.post("/render", json=payload(photo_base64=photo)).status_code == 422


def test_refuses_unknown_fields_in_the_cv() -> None:
    client, _ = make_render_client()
    cv = make_cv().model_dump()
    cv["salary"] = "100k"

    assert client.post("/render", json=payload(cv=cv)).status_code == 422


def test_refuses_an_unsupported_language() -> None:
    client, _ = make_render_client()

    assert client.post("/render", json=payload(language="other")).status_code == 422


def test_refuses_an_unknown_language_value() -> None:
    client, _ = make_render_client()

    assert client.post("/render", json=payload(language="xx")).status_code == 422


def test_rendering_has_its_own_rate_limit() -> None:
    client, _ = make_render_client(limit=1)

    statuses = [client.post("/render", json=payload()).status_code for _ in range(2)]

    assert statuses == [200, 429]
