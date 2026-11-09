import base64
import uuid
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.exc import OperationalError

from app.api.dependencies import get_render_rate_limiter
from app.api.rate_limit import RateLimiter
from app.api.tracker_dependencies import get_current_user_id, get_tracker_service
from app.main import create_app
from tests.db_helpers import add_user
from tests.test_api import make_settings
from tests.test_application_service import FAKE_PDF
from tests.test_docx_parser import make_png
from tests.test_letter_html_builder import make_letter
from tests.test_tailoring_guard import make_cv
from tests.test_tracker_service import make_tracker


class DownService:
    def list_applications(self, user_id: uuid.UUID) -> list[object]:
        raise OperationalError("SELECT 1", {}, Exception("secret host 10.0.0.5"))


def make_client(
    engine: Engine, user_id: uuid.UUID, limit: int = 100, service: object | None = None
) -> TestClient:
    real, _ = make_tracker(engine)
    app = create_app(make_settings())
    limiter = RateLimiter(limit, 3600)
    app.dependency_overrides[get_tracker_service] = lambda: service or real
    app.dependency_overrides[get_current_user_id] = lambda: user_id
    app.dependency_overrides[get_render_rate_limiter] = lambda: limiter
    return TestClient(app, raise_server_exceptions=False)


def body(**changes: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "job_title": "Stagiaire DataLab",
        "company": "Coface",
        "language": "fr",
        "source_url": "https://example.com/job",
        "status": "saved",
        "cv": make_cv().model_dump(),
        "letter": make_letter().model_dump(),
        "photo_base64": None,
    }
    data.update(changes)
    return data


def save(client: TestClient, **changes: Any) -> httpx.Response:
    response: httpx.Response = client.post("/tracker/applications", json=body(**changes))
    return response


@pytest.fixture
def owner(clean_engine: Engine) -> uuid.UUID:
    return add_user(clean_engine, "owner@example.com")


def test_saves_an_application_and_lists_it(clean_engine: Engine, owner: uuid.UUID) -> None:
    client = make_client(clean_engine, owner)

    created = save(client)
    listed = client.get("/tracker/applications")

    assert created.status_code == 201
    assert created.json()["status"] == "saved"
    assert [item["job_title"] for item in listed.json()] == ["Stagiaire DataLab"]


def test_gets_one_application(clean_engine: Engine, owner: uuid.UUID) -> None:
    client = make_client(clean_engine, owner)
    application_id = save(client).json()["id"]

    response = client.get(f"/tracker/applications/{application_id}")

    assert response.status_code == 200
    assert response.json()["company"] == "Coface"


def test_updates_the_status_and_the_notes(clean_engine: Engine, owner: uuid.UUID) -> None:
    client = make_client(clean_engine, owner)
    application_id = save(client).json()["id"]

    response = client.patch(
        f"/tracker/applications/{application_id}",
        json={"status": "interview", "notes": "Monday 10:00"},
    )

    assert response.status_code == 200
    assert (response.json()["status"], response.json()["notes"]) == ("interview", "Monday 10:00")


def test_downloads_both_pdfs_with_a_safe_file_name(clean_engine: Engine, owner: uuid.UUID) -> None:
    client = make_client(clean_engine, owner)
    application_id = save(client, company='Evil"; x=1').json()["id"]

    cv = client.get(f"/tracker/applications/{application_id}/cv.pdf")
    letter = client.get(f"/tracker/applications/{application_id}/letter.pdf")

    assert cv.content == FAKE_PDF
    assert cv.headers["content-type"] == "application/pdf"
    assert cv.headers["content-disposition"] == 'attachment; filename="cv-evil-x-1.pdf"'
    assert letter.headers["content-disposition"] == 'attachment; filename="letter-evil-x-1.pdf"'


def test_deletes_an_application(clean_engine: Engine, owner: uuid.UUID) -> None:
    client = make_client(clean_engine, owner)
    application_id = save(client).json()["id"]

    deleted = client.delete(f"/tracker/applications/{application_id}")

    assert deleted.status_code == 204
    assert client.get(f"/tracker/applications/{application_id}").status_code == 404
    assert client.get("/tracker/applications").json() == []


def test_unknown_applications_return_404(clean_engine: Engine, owner: uuid.UUID) -> None:
    client = make_client(clean_engine, owner)

    assert client.get("/tracker/applications/999999").status_code == 404
    assert client.patch("/tracker/applications/999999", json={"status": "offer"}).status_code == 404
    assert client.delete("/tracker/applications/999999").status_code == 404
    assert client.get("/tracker/applications/999999/cv.pdf").status_code == 404


def test_another_user_gets_a_404_and_cannot_see_the_application(
    clean_engine: Engine, owner: uuid.UUID
) -> None:
    stranger = add_user(clean_engine, "stranger@example.com")
    application_id = save(make_client(clean_engine, owner)).json()["id"]
    intruder = make_client(clean_engine, stranger)

    assert intruder.get("/tracker/applications").json() == []
    assert intruder.get(f"/tracker/applications/{application_id}").status_code == 404
    assert intruder.get(f"/tracker/applications/{application_id}/cv.pdf").status_code == 404
    assert intruder.get(f"/tracker/applications/{application_id}/letter.pdf").status_code == 404
    patched = intruder.patch(f"/tracker/applications/{application_id}", json={"notes": "x"})
    assert patched.status_code == 404
    assert intruder.delete(f"/tracker/applications/{application_id}").status_code == 404
    still_there = make_client(clean_engine, owner).get(f"/tracker/applications/{application_id}")
    assert still_there.status_code == 200


def test_an_invalid_id_is_refused(clean_engine: Engine, owner: uuid.UUID) -> None:
    client = make_client(clean_engine, owner)

    assert client.get("/tracker/applications/0").status_code == 422
    assert client.get("/tracker/applications/abc").status_code == 422


def test_unknown_statuses_and_fields_are_refused(clean_engine: Engine, owner: uuid.UUID) -> None:
    client = make_client(clean_engine, owner)
    application_id = save(client).json()["id"]
    url = f"/tracker/applications/{application_id}"

    assert client.patch(url, json={"status": "hired"}).status_code == 422
    assert client.patch(url, json={"cv_pdf": "x"}).status_code == 422
    assert save(client, status="hired").status_code == 422
    assert save(client, salary="100k").status_code == 422


def test_text_that_is_too_long_is_refused(clean_engine: Engine, owner: uuid.UUID) -> None:
    client = make_client(clean_engine, owner)
    application_id = save(client).json()["id"]

    patched = client.patch(f"/tracker/applications/{application_id}", json={"notes": "x" * 5001})
    assert patched.status_code == 422
    assert save(client, job_title="x" * 201).status_code == 422
    assert save(client, job_title="").status_code == 422


def test_an_invalid_photo_is_refused_and_nothing_is_saved(
    clean_engine: Engine, owner: uuid.UUID
) -> None:
    client = make_client(clean_engine, owner)

    response = save(client, photo_base64=base64.b64encode(b"not an image").decode("ascii"))

    assert response.status_code == 422
    assert client.get("/tracker/applications").json() == []


def test_a_photo_that_is_not_base64_is_refused(clean_engine: Engine, owner: uuid.UUID) -> None:
    assert (
        save(make_client(clean_engine, owner), photo_base64="!!! not base64 !!!").status_code == 422
    )


def test_a_real_photo_is_accepted(clean_engine: Engine, owner: uuid.UUID) -> None:
    photo = base64.b64encode(make_png(300, 353)).decode("ascii")

    assert save(make_client(clean_engine, owner), photo_base64=photo).status_code == 201


def test_a_link_that_is_not_a_web_address_is_not_stored(
    clean_engine: Engine, owner: uuid.UUID
) -> None:
    response = save(make_client(clean_engine, owner), source_url="javascript:alert(1)")

    assert response.json()["source_url"] == ""


def test_saving_has_the_rendering_rate_limit(clean_engine: Engine, owner: uuid.UUID) -> None:
    client = make_client(clean_engine, owner, limit=1)

    statuses = [save(client).status_code for _ in range(2)]

    assert statuses == [201, 429]


def test_the_cors_policy_allows_the_methods_of_the_tracker(
    clean_engine: Engine, owner: uuid.UUID
) -> None:
    response = make_client(clean_engine, owner).options(
        "/tracker/applications/1",
        headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "PATCH"},
    )

    assert "PATCH" in response.headers["access-control-allow-methods"]
    assert "DELETE" in response.headers["access-control-allow-methods"]


def test_a_database_outage_gives_a_503_without_leaking_details(
    clean_engine: Engine, owner: uuid.UUID
) -> None:
    client = make_client(clean_engine, owner, service=DownService())

    response = client.get("/tracker/applications")

    assert response.status_code == 503
    assert "secret host" not in response.text
    assert "10.0.0.5" not in response.text
