import base64
import uuid
from datetime import UTC, datetime
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.account_dependencies import (
    get_profile_service,
    get_quota_service,
    get_saved_cv_service,
)
from app.api.auth_dependencies import require_user, require_verified_user
from app.api.dependencies import get_application_service, get_job_runner, get_rate_limiter
from app.api.errors import describe_error
from app.api.rate_limit import RateLimiter
from app.core.config import Settings, get_settings
from app.domain.cv import CV
from app.domain.document import MAX_CV_BYTES
from app.domain.jobs import Stage
from app.domain.llm import LLMError, LLMUnavailableError
from app.domain.plans import QuotaExceededError
from app.domain.profile import Profile, ProfileIncompleteError
from app.domain.saved_cv import NoSavedCvError, SavedCv
from app.infrastructure.memory_job_store import InMemoryJobStore
from app.main import MAX_REQUEST_BYTES, create_app
from app.services.application_service import (
    ApplicationRequest,
    ApplicationResult,
    InvalidApplicationInputError,
)
from app.services.cv_structurer import CVStructuringError
from app.services.job_analyzer import JobAnalysisError
from app.services.job_runner import JobRunner
from app.services.letter_conventions import UnsupportedLetterLanguageError
from app.services.letter_guard import LetterViolationError
from app.services.page_fitter import PageOverflowError
from app.services.tailoring_guard import TailoringViolationError
from tests.auth_helpers import FAKE_SESSION
from tests.fakes import ImmediateExecutor
from tests.test_application_service import FAKE_PDF, ai_answers, make_docx, make_service
from tests.test_config import IsolatedSettings
from tests.test_tailoring_guard import make_cv

ORIGIN = "http://localhost:3000"
COMPLETE_PROFILE = Profile(address="Oujda, Maroc", city="Oujda", gender="m", cv_language="fr")
INCOMPLETE_PROFILE = Profile(address="", city="", gender="m", cv_language="fr")
RESETS_AT = datetime(2026, 12, 1, tzinfo=UTC)
FREE_LIMIT = 3


class StubService:
    def __init__(self, error: Exception) -> None:
        self._error = error
        self.requests: list[ApplicationRequest] = []

    def create(self, request: ApplicationRequest, on_stage: object = None) -> ApplicationResult:
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


class FakeSavedCvs:
    def __init__(self, saved: SavedCv | None = None) -> None:
        self._saved = saved
        self.remembered: list[CV] = []

    def require(self, user_id: uuid.UUID) -> SavedCv:
        if self._saved is None:
            raise NoSavedCvError
        return self._saved

    def remember_structure(self, user_id: uuid.UUID, content: bytes, structured: CV) -> None:
        self.remembered.append(structured)


def make_settings() -> Settings:
    return IsolatedSettings(cors_origins=ORIGIN)


def make_client(
    service: object,
    limit: int = 100,
    profiles: FakeProfiles | None = None,
    quotas: FakeQuotas | None = None,
    saved_cvs: FakeSavedCvs | None = None,
) -> TestClient:
    settings = make_settings()
    app = create_app(settings)
    limiter = RateLimiter(limit, 3600)
    profile_service = profiles or FakeProfiles()
    quota_service = quotas or FakeQuotas()
    saved_cv_service = saved_cvs or FakeSavedCvs()
    app.dependency_overrides[get_saved_cv_service] = lambda: saved_cv_service
    app.dependency_overrides[get_application_service] = lambda: service
    app.dependency_overrides[get_rate_limiter] = lambda: limiter
    app.dependency_overrides[require_user] = lambda: FAKE_SESSION
    app.dependency_overrides[require_verified_user] = lambda: FAKE_SESSION
    app.dependency_overrides[get_profile_service] = lambda: profile_service
    app.dependency_overrides[get_quota_service] = lambda: quota_service
    app.dependency_overrides[get_settings] = lambda: settings
    runner = JobRunner(InMemoryJobStore(), ImmediateExecutor(), describe_error)
    app.dependency_overrides[get_job_runner] = lambda: runner
    return TestClient(app, raise_server_exceptions=False)


def outcome(client: TestClient, started: httpx.Response) -> httpx.Response:
    """The answer the page ends with: the refusal itself, or the job's result or error."""
    if started.status_code != 202:
        return started
    job = client.get(f"/applications/jobs/{started.json()['job_id']}").json()
    if job["error"] is not None:
        error = job["error"]
        body = {"detail": error["detail"], "violations": error["violations"]}
        return httpx.Response(error["status"], json=body)
    return httpx.Response(200, json=job["result"])


def generate(client: TestClient, **data: str) -> httpx.Response:
    """Creates an application from the saved CV and waits for its end."""
    started: httpx.Response = client.post("/applications", data={"job_text": "x", **data})
    return outcome(client, started)


def upload(
    client: TestClient,
    filename: str = "cv.docx",
    content: bytes | None = None,
) -> httpx.Response:
    started: httpx.Response = client.post(
        "/applications",
        files={"cv_file": (filename, make_docx() if content is None else content)},
        data={"job_text": "Acme seeks an intern."},
    )
    return outcome(client, started)


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
    assert set(body["report"]) == {"matched_skills", "missing_skills", "changes", "score"}
    assert "Profile rewritten with the words of the offer." in body["report"]["changes"]
    assert set(body["report"]["score"]) == {
        "value",
        "required_matched",
        "required_total",
        "nice_matched",
        "nice_total",
    }


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


def test_without_a_file_or_a_saved_cv_the_user_is_asked_to_upload() -> None:
    stub = StubService(RuntimeError("must not run"))
    quotas = FakeQuotas()

    response = generate(make_client(stub, quotas=quotas))

    assert response.status_code == 422
    assert "no saved CV" in response.json()["detail"]
    assert stub.requests == []
    assert quotas.reserved == 0


def test_without_a_file_the_saved_cv_is_used() -> None:
    stub = StubService(InvalidApplicationInputError("bad"))
    saved = FakeSavedCvs(SavedCv(filename="saved.pdf", content=b"%PDF-saved"))

    generate(make_client(stub, saved_cvs=saved))

    assert (stub.requests[0].cv_filename, stub.requests[0].cv_content) == (
        "saved.pdf",
        b"%PDF-saved",
    )


def test_the_saved_cv_is_read_once_then_kept_for_next_time() -> None:
    service, _, _ = make_service(ai_answers())
    saved = FakeSavedCvs(SavedCv(filename="saved.docx", content=make_docx()))

    response = generate(make_client(service, saved_cvs=saved))

    assert response.status_code == 200
    assert len(saved.remembered) == 1


def test_a_saved_cv_already_read_is_passed_to_the_pipeline() -> None:
    stub = StubService(InvalidApplicationInputError("bad"))
    structured = make_cv()
    saved = FakeSavedCvs(SavedCv(filename="saved.pdf", content=b"%PDF", structured=structured))

    generate(make_client(stub, saved_cvs=saved))

    assert stub.requests[0].structured_cv == structured
    assert saved.remembered == []


def test_an_uploaded_file_wins_over_the_saved_cv() -> None:
    stub = StubService(InvalidApplicationInputError("bad"))
    saved = FakeSavedCvs(SavedCv(filename="saved.pdf", content=b"%PDF-saved"))

    upload(make_client(stub, saved_cvs=saved))

    assert stub.requests[0].cv_filename == "cv.docx"


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


class StagedService:
    """Reports the stages of a real generation, then fails, to look at the job."""

    def __init__(self) -> None:
        self.stages: list[Stage] = []

    def create(self, request: ApplicationRequest, on_stage: object = None) -> ApplicationResult:
        assert callable(on_stage)
        for stage in ("reading", "tailoring"):
            on_stage(stage)
            self.stages.append(stage)
        raise LLMUnavailableError("down")


def test_creating_an_application_answers_at_once_with_a_job_to_follow() -> None:
    service, _, _ = make_service(ai_answers())
    client = make_client(service)

    started = client.post(
        "/applications", files={"cv_file": ("cv.docx", make_docx())}, data={"job_text": "x"}
    )
    job = client.get(f"/applications/jobs/{started.json()['job_id']}").json()

    assert started.status_code == 202
    assert set(started.json()) == {"job_id", "status", "stage", "result", "error"}
    assert (job["status"], job["stage"], job["error"]) == ("done", "finished", None)
    assert job["result"]["company"] == "Acme"


def test_the_pipeline_reports_its_stages_to_the_job() -> None:
    service = StagedService()

    response = upload(make_client(service))

    assert service.stages == ["reading", "tailoring"]
    assert response.status_code == 503


def test_a_job_of_another_user_or_an_unknown_job_is_not_found() -> None:
    client = make_client(StubService(LLMUnavailableError("down")))
    started = client.post(
        "/applications", files={"cv_file": ("cv.docx", make_docx())}, data={"job_text": "x"}
    )
    job_id = started.json()["job_id"]
    other = make_client(StubService(LLMUnavailableError("down")))

    assert client.get(f"/applications/jobs/{uuid.uuid4()}").status_code == 404
    assert other.get(f"/applications/jobs/{job_id}").status_code == 404


def test_a_second_application_while_one_runs_is_refused_and_not_counted() -> None:
    quotas = FakeQuotas()
    client = make_client(object(), quotas=quotas)
    app = client.app
    assert isinstance(app, FastAPI)

    class NeverRuns(ImmediateExecutor):
        def submit(self, fn: Any, /, *args: Any, **kwargs: Any) -> Any:
            return None

    runner = JobRunner(InMemoryJobStore(), NeverRuns(), describe_error)
    app.dependency_overrides[get_job_runner] = lambda: runner
    files = {"cv_file": ("cv.docx", make_docx())}

    first = client.post("/applications", files=files, data={"job_text": "x"})
    second = client.post("/applications", files=files, data={"job_text": "x"})

    assert first.status_code == 202
    assert second.status_code == 409
    assert "already being created" in second.json()["detail"]
    assert (quotas.reserved, quotas.released) == (2, 1)


def test_the_documents_are_returned_even_if_the_saved_cv_cannot_be_kept() -> None:
    class BrokenSavedCvs(FakeSavedCvs):
        def remember_structure(self, user_id: uuid.UUID, content: bytes, structured: CV) -> None:
            raise RuntimeError("database hiccup")

    service, _, _ = make_service(ai_answers())
    saved = BrokenSavedCvs(SavedCv(filename="saved.docx", content=make_docx()))

    response = generate(make_client(service, saved_cvs=saved))

    assert response.status_code == 200
