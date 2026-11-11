import base64

import httpx
import pytest
from fastapi.testclient import TestClient

from app.api.auth_dependencies import require_user
from app.api.dependencies import get_application_service, get_rate_limiter
from app.api.rate_limit import RateLimiter
from app.core.config import Settings, get_settings
from app.domain.llm import LLMError, LLMUnavailableError
from app.main import MAX_REQUEST_BYTES, create_app
from app.services.application_service import (
    MAX_CV_BYTES,
    ApplicationRequest,
    ApplicationResult,
    InvalidApplicationInputError,
)
from app.services.cv_structurer import CVStructuringError
from app.services.job_analyzer import JobAnalysisError
from app.services.letter_conventions import UnsupportedLetterLanguageError
from app.services.letter_guard import LetterViolationError
from app.services.page_fitter import PageOverflowError
from app.services.tailoring_guard import TailoringViolationError
from tests.auth_helpers import FAKE_SESSION
from tests.test_application_service import FAKE_PDF, ai_answers, make_docx, make_service
from tests.test_config import IsolatedSettings

ORIGIN = "http://localhost:3000"


class StubService:
    def __init__(self, error: Exception) -> None:
        self._error = error

    def create(self, request: ApplicationRequest) -> ApplicationResult:
        raise self._error


def make_settings(city: str = "Oujda") -> Settings:
    return IsolatedSettings(
        applicant_address="Oujda, Maroc",
        applicant_city=city,
        applicant_gender="m",
        cors_origins=ORIGIN,
    )


def make_client(service: object, limit: int = 100, city: str = "Oujda") -> TestClient:
    settings = make_settings(city)
    app = create_app(settings)
    limiter = RateLimiter(limit, 3600)
    app.dependency_overrides[get_application_service] = lambda: service
    app.dependency_overrides[get_rate_limiter] = lambda: limiter
    app.dependency_overrides[require_user] = lambda: FAKE_SESSION
    app.dependency_overrides[get_settings] = lambda: settings
    return TestClient(app, raise_server_exceptions=False)


def upload(
    client: TestClient,
    filename: str = "cv.docx",
    content: bytes | None = None,
) -> httpx.Response:
    response: httpx.Response = client.post(
        "/applications",
        files={"cv_file": (filename, make_docx() if content is None else content)},
        data={"job_text": "Acme seeks an intern."},
    )
    return response


def test_health_check() -> None:
    response = make_client(object()).get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_creates_an_application() -> None:
    service, _, _ = make_service(ai_answers())

    response = upload(make_client(service))

    body = response.json()
    assert response.status_code == 200
    assert (body["job_title"], body["company"], body["language"]) == ("Stagiaire", "Acme", "fr")
    assert body["photo_used"] is False
    assert base64.b64decode(body["cv_pdf_base64"]) == FAKE_PDF
    assert base64.b64decode(body["letter_pdf_base64"]) == FAKE_PDF


def test_a_missing_file_is_a_validation_error() -> None:
    response = make_client(object()).post("/applications", data={"job_text": "x"})

    assert response.status_code == 422


def test_a_renamed_file_is_refused_with_a_clean_message() -> None:
    service, provider, _ = make_service([])

    response = upload(make_client(service), filename="cv.pdf", content=make_docx())

    assert response.status_code == 422
    assert "does not match" in response.json()["detail"]
    assert provider.calls == []


@pytest.mark.parametrize(
    ("error", "status"),
    [
        pytest.param(InvalidApplicationInputError("bad"), 422, id="invalid-input"),
        pytest.param(JobAnalysisError("bad"), 422, id="job-analysis"),
        pytest.param(CVStructuringError("bad"), 422, id="cv-structuring"),
        pytest.param(UnsupportedLetterLanguageError("bad"), 422, id="language"),
        pytest.param(PageOverflowError("bad"), 422, id="overflow"),
        pytest.param(LLMUnavailableError("down"), 503, id="ai-unavailable"),
        pytest.param(LLMError("fail"), 502, id="ai-error"),
    ],
)
def test_domain_errors_become_the_right_http_status(error: Exception, status: int) -> None:
    response = upload(make_client(StubService(error)))

    assert response.status_code == status


def test_ai_errors_do_not_leak_their_details() -> None:
    response = upload(make_client(StubService(LLMUnavailableError("secret quota detail"))))

    assert "secret quota detail" not in response.text


@pytest.mark.parametrize("error_type", [TailoringViolationError, LetterViolationError])
def test_guard_rejections_return_the_violations(
    error_type: type[TailoringViolationError] | type[LetterViolationError],
) -> None:
    response = upload(make_client(StubService(error_type(["problem one"]))))

    assert response.status_code == 502
    assert response.json()["violations"] == ["problem one"]


def test_unexpected_errors_do_not_leak_internals() -> None:
    response = upload(make_client(StubService(RuntimeError("internal secret detail"))))

    assert response.status_code == 500
    assert "internal secret detail" not in response.text


def test_the_rate_limit_blocks_extra_requests() -> None:
    client = make_client(StubService(InvalidApplicationInputError("bad")), limit=2)

    statuses = [upload(client).status_code for _ in range(3)]
    third = upload(client)

    assert statuses == [422, 422, 429]
    assert int(third.headers["retry-after"]) > 0


def test_oversized_uploads_are_rejected_before_processing() -> None:
    client = make_client(StubService(InvalidApplicationInputError("bad")))

    response = upload(client, content=b"x" * (MAX_REQUEST_BYTES + 1))

    assert response.status_code == 413
    assert MAX_REQUEST_BYTES > MAX_CV_BYTES


def test_the_server_refuses_to_run_without_applicant_details() -> None:
    client = make_client(StubService(InvalidApplicationInputError("bad")), city="")

    assert upload(client).status_code == 503


def test_cors_allows_the_frontend_origin() -> None:
    response = make_client(object()).options(
        "/applications",
        headers={"Origin": ORIGIN, "Access-Control-Request-Method": "POST"},
    )

    assert response.headers["access-control-allow-origin"] == ORIGIN


def test_cors_refuses_other_origins() -> None:
    response = make_client(object()).options(
        "/applications",
        headers={"Origin": "http://evil.example", "Access-Control-Request-Method": "POST"},
    )

    assert "access-control-allow-origin" not in response.headers
