import base64
from pathlib import Path
from typing import Any

import httpx
from fastapi.testclient import TestClient

from app.api.dependencies import get_render_rate_limiter
from app.api.rate_limit import RateLimiter
from app.api.tracker_dependencies import get_tracker_service
from app.main import create_app
from app.services.tracker_service import TrackerService
from tests.test_api import make_settings
from tests.test_application_service import FAKE_PDF
from tests.test_docx_parser import make_png
from tests.test_letter_html_builder import make_letter
from tests.test_tailoring_guard import make_cv
from tests.test_tracker_service import make_tracker


def make_client(tmp_path: Path, limit: int = 100) -> tuple[TestClient, TrackerService]:
    service, _ = make_tracker(tmp_path)
    app = create_app(make_settings())
    limiter = RateLimiter(limit, 3600)
    app.dependency_overrides[get_tracker_service] = lambda: service
    app.dependency_overrides[get_render_rate_limiter] = lambda: limiter
    return TestClient(app, raise_server_exceptions=False), service


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


def test_saves_an_application_and_lists_it(tmp_path: Path) -> None:
    client, _ = make_client(tmp_path)

    created = save(client)
    listed = client.get("/tracker/applications")

    assert created.status_code == 201
    assert created.json()["id"] == 1
    assert created.json()["status"] == "saved"
    assert [item["job_title"] for item in listed.json()] == ["Stagiaire DataLab"]


def test_gets_one_application(tmp_path: Path) -> None:
    client, _ = make_client(tmp_path)
    save(client)

    response = client.get("/tracker/applications/1")

    assert response.status_code == 200
    assert response.json()["company"] == "Coface"


def test_updates_the_status_and_the_notes(tmp_path: Path) -> None:
    client, _ = make_client(tmp_path)
    save(client)

    response = client.patch(
        "/tracker/applications/1", json={"status": "interview", "notes": "Monday 10:00"}
    )

    assert response.status_code == 200
    assert (response.json()["status"], response.json()["notes"]) == ("interview", "Monday 10:00")


def test_downloads_both_pdfs_with_a_safe_file_name(tmp_path: Path) -> None:
    client, _ = make_client(tmp_path)
    save(client, company='Evil"; x=1')

    cv = client.get("/tracker/applications/1/cv.pdf")
    letter = client.get("/tracker/applications/1/letter.pdf")

    assert cv.content == FAKE_PDF
    assert cv.headers["content-type"] == "application/pdf"
    assert cv.headers["content-disposition"] == 'attachment; filename="cv-evil-x-1.pdf"'
    assert letter.headers["content-disposition"] == 'attachment; filename="letter-evil-x-1.pdf"'


def test_deletes_an_application(tmp_path: Path) -> None:
    client, _ = make_client(tmp_path)
    save(client)

    deleted = client.delete("/tracker/applications/1")

    assert deleted.status_code == 204
    assert client.get("/tracker/applications/1").status_code == 404
    assert client.get("/tracker/applications").json() == []


def test_unknown_applications_return_404(tmp_path: Path) -> None:
    client, _ = make_client(tmp_path)

    assert client.get("/tracker/applications/9").status_code == 404
    assert client.patch("/tracker/applications/9", json={"status": "offer"}).status_code == 404
    assert client.delete("/tracker/applications/9").status_code == 404
    assert client.get("/tracker/applications/9/cv.pdf").status_code == 404


def test_an_invalid_id_is_refused(tmp_path: Path) -> None:
    client, _ = make_client(tmp_path)

    assert client.get("/tracker/applications/0").status_code == 422
    assert client.get("/tracker/applications/abc").status_code == 422


def test_unknown_statuses_and_fields_are_refused(tmp_path: Path) -> None:
    client, _ = make_client(tmp_path)
    save(client)

    assert client.patch("/tracker/applications/1", json={"status": "hired"}).status_code == 422
    assert client.patch("/tracker/applications/1", json={"cv_pdf": "x"}).status_code == 422
    assert save(client, status="hired").status_code == 422
    assert save(client, salary="100k").status_code == 422


def test_text_that_is_too_long_is_refused(tmp_path: Path) -> None:
    client, _ = make_client(tmp_path)
    save(client)

    assert client.patch("/tracker/applications/1", json={"notes": "x" * 5001}).status_code == 422
    assert save(client, job_title="x" * 201).status_code == 422
    assert save(client, job_title="").status_code == 422


def test_an_invalid_photo_is_refused_and_nothing_is_saved(tmp_path: Path) -> None:
    client, _ = make_client(tmp_path)

    response = save(client, photo_base64=base64.b64encode(b"not an image").decode("ascii"))

    assert response.status_code == 422
    assert client.get("/tracker/applications").json() == []


def test_a_photo_that_is_not_base64_is_refused(tmp_path: Path) -> None:
    client, _ = make_client(tmp_path)

    assert save(client, photo_base64="!!! not base64 !!!").status_code == 422


def test_a_real_photo_is_accepted(tmp_path: Path) -> None:
    client, _ = make_client(tmp_path)

    response = save(client, photo_base64=base64.b64encode(make_png(300, 353)).decode("ascii"))

    assert response.status_code == 201


def test_a_link_that_is_not_a_web_address_is_not_stored(tmp_path: Path) -> None:
    client, _ = make_client(tmp_path)

    response = save(client, source_url="javascript:alert(1)")

    assert response.json()["source_url"] == ""


def test_saving_has_the_rendering_rate_limit(tmp_path: Path) -> None:
    client, _ = make_client(tmp_path, limit=1)

    statuses = [save(client).status_code for _ in range(2)]

    assert statuses == [201, 429]


def test_the_cors_policy_allows_the_methods_of_the_tracker(tmp_path: Path) -> None:
    client, _ = make_client(tmp_path)

    response = client.options(
        "/tracker/applications/1",
        headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "PATCH"},
    )

    assert "PATCH" in response.headers["access-control-allow-methods"]
    assert "DELETE" in response.headers["access-control-allow-methods"]
