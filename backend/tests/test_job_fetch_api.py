from fastapi.testclient import TestClient

from app.api.auth_dependencies import require_user
from app.api.dependencies import get_fetch_rate_limiter, get_job_fetch_service
from app.api.rate_limit import RateLimiter
from app.domain.job_source import JobFetchError
from app.main import create_app
from app.services.job_fetch_service import FetchedJobText
from tests.auth_helpers import FAKE_SESSION
from tests.test_api import make_settings

URL = "https://example.com/job"


class StubService:
    def __init__(self, error: Exception | None = None) -> None:
        self._error = error
        self.urls: list[str] = []

    def fetch_text(self, url: str) -> FetchedJobText:
        self.urls.append(url)
        if self._error is not None:
            raise self._error
        return FetchedJobText("The offer text", False, "https://example.com/final")


def make_client(service: object, limit: int = 100) -> TestClient:
    app = create_app(make_settings())
    limiter = RateLimiter(limit, 3600)
    app.dependency_overrides[get_job_fetch_service] = lambda: service
    app.dependency_overrides[get_fetch_rate_limiter] = lambda: limiter
    app.dependency_overrides[require_user] = lambda: FAKE_SESSION
    return TestClient(app, raise_server_exceptions=False)


def test_returns_the_text_of_the_offer() -> None:
    service = StubService()

    response = make_client(service).post("/job-offers/fetch", json={"url": URL})

    assert response.status_code == 200
    assert response.json() == {
        "text": "The offer text",
        "truncated": False,
        "source_url": "https://example.com/final",
    }
    assert service.urls == [URL]


def test_a_fetch_error_becomes_a_422_with_its_safe_message() -> None:
    client = make_client(StubService(JobFetchError("The page was not found. Check the link.")))

    response = client.post("/job-offers/fetch", json={"url": URL})

    assert response.status_code == 422
    assert response.json()["detail"] == "The page was not found. Check the link."


def test_unexpected_errors_do_not_leak_internals() -> None:
    client = make_client(StubService(RuntimeError("internal secret detail 10.0.0.5")))

    response = client.post("/job-offers/fetch", json={"url": URL})

    assert response.status_code == 500
    assert "internal secret detail" not in response.text


def test_a_missing_link_is_refused() -> None:
    assert make_client(StubService()).post("/job-offers/fetch", json={}).status_code == 422


def test_an_empty_or_huge_link_is_refused_before_any_fetch() -> None:
    service = StubService()
    client = make_client(service)

    assert client.post("/job-offers/fetch", json={"url": ""}).status_code == 422
    assert client.post("/job-offers/fetch", json={"url": "x" * 2001}).status_code == 422
    assert service.urls == []


def test_unknown_fields_are_refused() -> None:
    response = make_client(StubService()).post(
        "/job-offers/fetch", json={"url": URL, "method": "POST"}
    )

    assert response.status_code == 422


def test_fetching_has_its_own_rate_limit() -> None:
    client = make_client(StubService(), limit=1)

    statuses = [client.post("/job-offers/fetch", json={"url": URL}).status_code for _ in range(2)]

    assert statuses == [200, 429]
