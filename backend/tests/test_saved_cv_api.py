import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from app.api.account_dependencies import get_saved_cv_service
from app.api.dependencies import get_render_rate_limiter
from app.api.rate_limit import RateLimiter
from app.infrastructure.db.postgres_saved_cvs import PostgresSavedCvRepository
from app.services.saved_cv_service import SavedCvService
from tests.auth_helpers import ORIGIN, build_auth_app, make_client, sign_in
from tests.test_application_service import make_docx, make_pdf


def build(engine: Engine) -> FastAPI:
    app = build_auth_app(engine)
    saved_cvs = SavedCvService(PostgresSavedCvRepository(engine))
    limiter = RateLimiter(100, 3600)
    app.dependency_overrides[get_saved_cv_service] = lambda: saved_cvs
    app.dependency_overrides[get_render_rate_limiter] = lambda: limiter
    return app


def headers(csrf: str | None) -> dict[str, str]:
    values = {"Origin": ORIGIN}
    if csrf is not None:
        values["X-CSRF-Token"] = csrf
    return values


def put_cv(
    client: TestClient, csrf: str | None, filename: str = "cv.docx", content: bytes | None = None
) -> httpx.Response:
    file = (filename, make_docx() if content is None else content)
    response: httpx.Response = client.put("/me/cv", files={"cv_file": file}, headers=headers(csrf))
    return response


def test_the_saved_cv_needs_a_login(clean_engine: Engine) -> None:
    client = make_client(build(clean_engine))

    assert client.get("/me/cv").status_code == 401
    assert put_cv(client, csrf=None).status_code == 401
    assert client.delete("/me/cv", headers=headers(None)).status_code == 401


def test_a_new_user_has_no_saved_cv(clean_engine: Engine) -> None:
    client = make_client(build(clean_engine))
    sign_in(client)

    response = client.get("/me/cv")

    assert response.status_code == 200
    assert response.json() is None


def test_an_uploaded_cv_is_kept_with_a_clean_name(clean_engine: Engine) -> None:
    client = make_client(build(clean_engine))
    csrf = sign_in(client)
    content = make_pdf()

    saved = put_cv(client, csrf, filename="C:\\fakepath\\My CV.pdf", content=content)

    assert saved.status_code == 200
    assert (saved.json()["filename"], saved.json()["size"]) == ("My CV.pdf", len(content))
    assert client.get("/me/cv").json() == saved.json()


def test_uploading_needs_the_csrf_token(clean_engine: Engine) -> None:
    client = make_client(build(clean_engine))
    csrf = sign_in(client)

    assert put_cv(client, csrf=None).status_code == 403
    assert put_cv(client, csrf="wrong").status_code == 403
    assert client.get("/me/cv").json() is None
    assert csrf


def test_a_file_that_is_not_a_cv_is_refused(clean_engine: Engine) -> None:
    client = make_client(build(clean_engine))
    csrf = sign_in(client)

    wrong_type = put_cv(client, csrf, filename="cv.txt", content=b"hello")
    renamed = put_cv(client, csrf, filename="cv.pdf", content=make_docx())

    assert (wrong_type.status_code, renamed.status_code) == (422, 422)
    assert "does not match" in renamed.json()["detail"]
    assert client.get("/me/cv").json() is None


def test_a_new_upload_replaces_the_saved_cv(clean_engine: Engine) -> None:
    client = make_client(build(clean_engine))
    csrf = sign_in(client)
    put_cv(client, csrf, filename="old.docx")

    put_cv(client, csrf, filename="new.pdf", content=make_pdf())

    assert client.get("/me/cv").json()["filename"] == "new.pdf"


def test_the_saved_cv_can_be_deleted(clean_engine: Engine) -> None:
    client = make_client(build(clean_engine))
    csrf = sign_in(client)
    put_cv(client, csrf)

    deleted = client.delete("/me/cv", headers=headers(csrf))

    assert deleted.status_code == 204
    assert client.get("/me/cv").json() is None


def test_each_user_only_sees_their_own_cv(clean_engine: Engine) -> None:
    app = build(clean_engine)
    jane, other = make_client(app), make_client(app)
    csrf = sign_in(jane)
    sign_in(other, "other@example.com")

    put_cv(jane, csrf)

    assert other.get("/me/cv").json() is None
