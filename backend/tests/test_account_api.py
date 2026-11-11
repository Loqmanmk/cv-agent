import uuid
from datetime import UTC, datetime

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from app.api.account_dependencies import get_profile_service, get_quota_service
from app.infrastructure.db.postgres_profiles import PostgresProfileRepository
from app.infrastructure.db.postgres_usage import PostgresUsageRepository
from app.services.profile_service import MAX_CITY_CHARS, ProfileService
from app.services.quota_service import QuotaService
from tests.auth_helpers import EMAIL, ORIGIN, build_auth_app, make_client, sign_in

PROFILE = {
    "address": "12 rue Exemple, Oujda",
    "city": "Oujda",
    "gender": "f",
    "cv_language": "de",
}
DEFAULT = {"address": "", "city": "", "gender": "m", "cv_language": "fr", "is_complete": False}


def build(engine: Engine) -> FastAPI:
    app = build_auth_app(engine)
    profiles = ProfileService(PostgresProfileRepository(engine))
    quotas = QuotaService(PostgresUsageRepository(engine))
    app.dependency_overrides[get_profile_service] = lambda: profiles
    app.dependency_overrides[get_quota_service] = lambda: quotas
    return app


def put_profile(client: TestClient, payload: object, csrf: str | None) -> httpx.Response:
    headers = {"Origin": ORIGIN}
    if csrf is not None:
        headers["X-CSRF-Token"] = csrf
    response: httpx.Response = client.put("/me/profile", json=payload, headers=headers)
    return response


def user_id_of(engine: Engine, email: str = EMAIL) -> uuid.UUID:
    with engine.connect() as connection:
        value = connection.execute(
            text("SELECT id FROM users WHERE email = :email"), {"email": email}
        ).scalar_one()
    assert isinstance(value, uuid.UUID)
    return value


def test_the_profile_and_the_usage_need_a_login(clean_engine: Engine) -> None:
    client = make_client(build(clean_engine))

    assert client.get("/me/profile").status_code == 401
    assert client.get("/me/usage").status_code == 401
    assert put_profile(client, PROFILE, csrf=None).status_code == 401


def test_a_new_user_has_an_empty_profile_that_is_not_complete(clean_engine: Engine) -> None:
    client = make_client(build(clean_engine))
    sign_in(client)

    assert client.get("/me/profile").json() == DEFAULT


def test_the_profile_is_saved_and_cleaned(clean_engine: Engine) -> None:
    client = make_client(build(clean_engine))
    csrf = sign_in(client)

    saved = put_profile(client, {**PROFILE, "city": "  Oujda  "}, csrf)

    expected = {**PROFILE, "is_complete": True}
    assert saved.status_code == 200
    assert saved.json() == expected
    assert client.get("/me/profile").json() == expected


def test_saving_the_profile_needs_the_csrf_token(clean_engine: Engine) -> None:
    client = make_client(build(clean_engine))
    sign_in(client)

    assert put_profile(client, PROFILE, csrf=None).status_code == 403
    assert put_profile(client, PROFILE, csrf="wrong").status_code == 403
    assert client.get("/me/profile").json() == DEFAULT


@pytest.mark.parametrize(
    "payload",
    [
        {**PROFILE, "gender": "x"},
        {**PROFILE, "cv_language": "es"},
        {**PROFILE, "plan": "premium"},
        {**PROFILE, "city": "x" * (MAX_CITY_CHARS + 1)},
        {"city": "Oujda"},
    ],
)
def test_a_profile_with_wrong_values_is_refused(clean_engine: Engine, payload: object) -> None:
    client = make_client(build(clean_engine))
    csrf = sign_in(client)

    assert put_profile(client, payload, csrf).status_code == 422
    assert client.get("/me/profile").json() == DEFAULT


def test_each_user_has_their_own_profile(clean_engine: Engine) -> None:
    app = build(clean_engine)
    jane, other = make_client(app), make_client(app)
    csrf = sign_in(jane)
    sign_in(other, "other@example.com")

    put_profile(jane, PROFILE, csrf)

    assert other.get("/me/profile").json() == DEFAULT


def test_a_new_user_is_on_the_free_plan_with_nothing_used(clean_engine: Engine) -> None:
    client = make_client(build(clean_engine))
    sign_in(client)

    usage = client.get("/me/usage").json()

    assert (usage["plan"], usage["used"], usage["limit"]) == ("free", 0, 3)
    assert datetime.fromisoformat(usage["resets_at"]) > datetime.now(UTC)


def test_the_usage_counts_the_applications_of_this_month(clean_engine: Engine) -> None:
    client = make_client(build(clean_engine))
    sign_in(client)
    QuotaService(PostgresUsageRepository(clean_engine)).reserve_application(
        user_id_of(clean_engine)
    )

    assert client.get("/me/usage").json()["used"] == 1
