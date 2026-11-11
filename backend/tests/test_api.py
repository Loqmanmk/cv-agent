import base64
import uuid
from datetime import UTC, datetime

import httpx
import pytest
from fastapi.testclient import TestClient

from app.api.account_dependencies import get_profile_service, get_quota_service
from app.api.auth_dependencies import require_user, require_verified_user
from app.api.dependencies import get_application_service, get_rate_limiter
from app.api.rate_limit import RateLimiter
from app.core.config import Settings, get_settings
from app.domain.llm import LLMError, LLMUnavailableError
from app.domain.plans import QuotaExceededError
from app.domain.profile import Profile, ProfileIncompleteError
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
COMPLETE_PROFILE = Profile(address="Oujda, Maroc", city="Oujda", gender="m", cv_language="fr")
INCOMPLETE_PROFILE = Profile(address="", city="", gender="m", cv_language="fr")
RESETS_AT = datetime(2026, 12, 1, tzinfo=UTC)
FREE_LIMIT = 3


class StubService:
    def __init__(self, error: Exception) -> None:
        self._error = error
        self.requests: list[ApplicationRequest] = []

    def create(self, request: ApplicationRequest) -> ApplicationResult:
        self.requests.append(request)
        raise self._error


class FakeProfiles:
    def __init__(self, profile: Profile = COMPLETE_PROFILE) -> None:
        self._profile = profile

    def require_complete(self, user_id: uuid.UUID) -> Profile:
        if not self._profile.is_complete:
            raise ProfileIncompleteError
        return self._profile


class FakeQuotas:
    def __init__(self, allowed: bool = True) -> None:
        self._allowed = allowed
        self.reserved = 0
        self.released = 0

    def reserve_application(self, user_id: uuid.UUID) -> int:
        if not self._allowed:
            raise QuotaExceededError(FREE_LIMIT, RESETS_AT)
        self.reserved += 1
        return self.reserved

    def release(self, user_id: uuid.UUID, reservation_id: int) -> None:
        self.released += 1


def make_settings() -> Settings:
    return IsolatedSettings(cors_origins=ORIGIN)


def make_client(
    service: object,
    limit: int = 100,
    profiles: FakeProfiles | None = None,
    quotas: FakeQuotas | None = None,
) -> TestClient:
    settings = make_settings()
    app = create_app(settings)
    limiter = RateLimiter(limit, 3600)
    profile_service = profiles or FakeProfiles()
    quota_service = quotas or FakeQuotas()
    app.dependency_overrides[get_application_service] = lambda: service
    app.dependency_overrides[get_rate_limiter] = lambda: limiter
    app.dependency_overrides[require_user] = lambda: FAKE_SESSION
    app.dependency_overrides[require_verified_user] = lambda: FAKE_SESSION
    app.dependency_overrides[get_profile_service] = lambda: profile_service
    app.dependency_overrides[get_quota_service] = lambda: quota_service
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


def test_creates_an_application_and_counts_it() -> None:
    service, _, _ = make_service(ai_answers())
    quotas = FakeQuotas()

    response = upload(make_client(service, quotas=quotas))

    body = response.json()
    assert response.status_code == 200
    assert (body["job_title"], body["company"], body["language"]) == ("Stagiaire", "Acme", "fr")
    assert body["photo_used"] is False
    assert base64.b64decode(body["cv_pdf_base64"]) == FAKE_PDF
    assert base64.b64decode(body["letter_pdf_base64"]) == FAKE_PDF
    assert (quotas.reserved, quotas.released) == (1, 0)


def test_the_profile_of_the_user_reaches_the_application() -> None:
    stub = StubService(InvalidApplicationInputError("bad"))
    profile = Profile(address="1 rue X", city="Rabat", gender="f", cv_language="de")

    upload(make_client(stub, profiles=FakeProfiles(profile)))

    request = stub.requests[0]
    assert (request.address, request.city, request.gender, request.cv_language) == (
        "1 rue X",
        "Rabat",
        "f",
        "de",
    )


def test_an_incomplete_profile_is_refused_before_any_ai_call() -> None:
    stub = StubService(RuntimeError("must not run"))
    quotas = FakeQuotas()

    response = upload(make_client(stub, profiles=FakeProfiles(INCOMPLETE_PROFILE), quotas=quotas))

    assert response.status_code == 422
    assert "Complete your profile" in response.json()["detail"]
    assert stub.requests == []
    assert quotas.reserved == 0


def test_a_user_over_the_monthly_limit_is_refused_before_any_ai_call() -> None:
    stub = StubService(RuntimeError("must not run"))

    response = upload(make_client(stub, quotas=FakeQuotas(allowed=False)))

    assert response.status_code == 402
    assert response.json()["limit"] == FREE_LIMIT
    assert response.json()["resets_at"].startswith("2026-12-01")
    assert stub.requests == []


def test_a_failed_application_is_not_counted() -> None:
    quotas = FakeQuotas()

    upload(make_client(StubService(LLMUnavailableError("down")), quotas=quotas))

    assert (quotas.reserved, quotas.released) == (1, 1)


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
