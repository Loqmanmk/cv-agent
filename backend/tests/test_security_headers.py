import pytest
from fastapi.testclient import TestClient

from app.api.security import HSTS_VALUE, SECURITY_HEADERS
from app.main import MAX_REQUEST_BYTES, create_app
from tests.test_config import IsolatedSettings

ORIGIN = "http://localhost:3000"


def make_client(hsts: bool = False) -> TestClient:
    settings = IsolatedSettings(cors_origins=ORIGIN, hsts_enabled=hsts)
    return TestClient(create_app(settings), raise_server_exceptions=False)


@pytest.mark.parametrize(
    ("method", "path"),
    [("get", "/health"), ("get", "/does-not-exist"), ("post", "/applications")],
)
def test_every_answer_carries_the_security_headers(method: str, path: str) -> None:
    response = getattr(make_client(), method)(path)

    for name, value in SECURITY_HEADERS.items():
        assert response.headers[name] == value


def test_the_api_is_never_cached_or_framed() -> None:
    headers = make_client().get("/health").headers

    assert headers["cache-control"] == "no-store"
    assert headers["x-frame-options"] == "DENY"
    assert "frame-ancestors 'none'" in headers["content-security-policy"]


def test_hsts_is_off_by_default() -> None:
    assert "strict-transport-security" not in make_client().get("/health").headers


def test_hsts_can_be_switched_on_for_https() -> None:
    headers = make_client(hsts=True).get("/health").headers

    assert headers["strict-transport-security"] == HSTS_VALUE


@pytest.mark.parametrize("path", ["/docs", "/redoc", "/openapi.json"])
def test_the_api_documentation_is_not_published(path: str) -> None:
    assert make_client().get(path).status_code == 404


def test_a_rejected_upload_still_lets_the_browser_read_the_error() -> None:
    response = make_client().post(
        "/applications",
        content=b"x" * (MAX_REQUEST_BYTES + 1),
        headers={"Origin": ORIGIN},
    )

    assert response.status_code == 413
    assert response.headers["access-control-allow-origin"] == ORIGIN
    assert response.headers["x-content-type-options"] == "nosniff"
