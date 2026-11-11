import pytest
from sqlalchemy import Engine, text

from app.api.dependencies import get_application_service
from app.api.tracker_dependencies import get_tracker_service
from tests.auth_helpers import (
    EMAIL,
    ORIGIN,
    PASSWORD,
    build_auth_app,
    login,
    make_client,
    post_json,
    register,
    sign_in,
)
from tests.test_tracker_service import make_tracker

WRONG_PASSWORD = "wrong horse battery staple"


# def count(engine: Engine, table: str) -> int:
#   with engine.connect() as connection:
#      return int(connection.execute(text(f"SELECT count(*) FROM {table}")).scalar_one())

ALLOWED_TABLES = {"users", "sessions"}


def count(engine: Engine, table: str) -> int:
    if table not in ALLOWED_TABLES:
        raise ValueError("Invalid table name")

    queries = {
        "users": text("SELECT count(*) FROM users"),
        "sessions": text("SELECT count(*) FROM sessions"),
    }

    with engine.connect() as connection:
        return int(connection.execute(queries[table]).scalar_one())


def test_registration_can_be_closed(clean_engine: Engine) -> None:
    client = make_client(build_auth_app(clean_engine, registration_open=False))

    response = register(client)

    assert response.status_code == 403
    assert response.json() == {"detail": "Registration is closed."}
    assert count(clean_engine, "users") == 0


def test_registering_creates_an_account_and_never_echoes_the_password(
    clean_engine: Engine,
) -> None:
    client = make_client(build_auth_app(clean_engine))

    response = register(client, "  Jane.Doe@Example.COM ")

    assert response.status_code == 201
    assert response.json() == {"email": EMAIL}
    assert PASSWORD not in response.text


def test_the_same_email_cannot_register_twice(clean_engine: Engine) -> None:
    client = make_client(build_auth_app(clean_engine))
    register(client)

    response = register(client)

    assert response.status_code == 409
    assert "already exists" in response.json()["detail"]


def test_a_weak_password_is_refused_with_the_list_of_problems(clean_engine: Engine) -> None:
    client = make_client(build_auth_app(clean_engine))

    response = register(client, password="aaaa")

    assert response.status_code == 422
    assert "Use at least 12 characters." in response.json()["problems"]
    assert count(clean_engine, "users") == 0


def test_an_invalid_email_is_refused(clean_engine: Engine) -> None:
    client = make_client(build_auth_app(clean_engine))

    response = register(client, email="not an email")

    assert response.status_code == 422
    assert response.json() == {"detail": "Enter a valid email address."}


@pytest.mark.parametrize("origin", ["http://evil.example", "null"])
def test_registering_from_another_website_is_refused(clean_engine: Engine, origin: str) -> None:
    client = make_client(build_auth_app(clean_engine))

    response = post_json(
        client, "/auth/register", {"email": EMAIL, "password": PASSWORD}, origin=origin
    )

    assert response.status_code == 403
    assert count(clean_engine, "users") == 0


def test_registrations_are_limited_per_address(clean_engine: Engine) -> None:
    client = make_client(build_auth_app(clean_engine, register_limit=1))

    statuses = [register(client, f"user{number}@example.com").status_code for number in range(2)]

    assert statuses == [201, 429]


def test_a_login_sets_a_protected_cookie_and_returns_the_csrf_token(clean_engine: Engine) -> None:
    client = make_client(build_auth_app(clean_engine))
    register(client)

    response = login(client)

    header = response.headers["set-cookie"].lower()
    token = client.cookies.get("session")
    assert response.status_code == 200
    assert "httponly" in header
    assert "samesite=lax" in header
    assert token is not None
    assert token not in response.text
    assert response.json()["email"] == EMAIL
    assert len(response.json()["csrf_token"]) >= 43


def test_every_failed_login_looks_the_same(clean_engine: Engine) -> None:
    client = make_client(build_auth_app(clean_engine))
    register(client)

    wrong = login(client, password=WRONG_PASSWORD)
    unknown = login(client, email="nobody@example.com")

    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json() == {"detail": "Invalid email or password."}
    assert "set-cookie" not in wrong.headers
    assert "set-cookie" not in unknown.headers


def test_too_many_attempts_on_one_account_are_blocked(clean_engine: Engine) -> None:
    client = make_client(build_auth_app(clean_engine, login_per_account=2))
    register(client)

    statuses = [login(client, password=WRONG_PASSWORD).status_code for _ in range(3)]
    blocked = login(client)

    assert statuses == [401, 401, 429]
    assert blocked.status_code == 429
    assert int(blocked.headers["retry-after"]) > 0
    assert login(client, email="other@example.com").status_code == 401


def test_too_many_attempts_from_one_address_are_blocked(clean_engine: Engine) -> None:
    client = make_client(build_auth_app(clean_engine, login_per_address=2))

    statuses = [login(client, email=f"user{number}@example.com").status_code for number in range(3)]

    assert statuses == [401, 401, 429]


@pytest.mark.parametrize("origin", ["http://evil.example", "null"])
def test_logging_in_from_another_website_is_refused(clean_engine: Engine, origin: str) -> None:
    client = make_client(build_auth_app(clean_engine))
    register(client)

    response = post_json(
        client, "/auth/login", {"email": EMAIL, "password": PASSWORD}, origin=origin
    )

    assert response.status_code == 403
    assert "set-cookie" not in response.headers


def test_a_client_that_is_not_a_browser_may_log_in_without_an_origin(
    clean_engine: Engine,
) -> None:
    client = make_client(build_auth_app(clean_engine))
    register(client)

    response = post_json(client, "/auth/login", {"email": EMAIL, "password": PASSWORD}, origin=None)

    assert response.status_code == 200


@pytest.mark.parametrize(
    "payload",
    [
        {"email": EMAIL, "password": PASSWORD, "extra": 1},
        {"email": EMAIL, "password": ""},
        {"email": "", "password": PASSWORD},
        {"email": EMAIL, "password": "x" * 1025},
        {"email": EMAIL},
    ],
)
def test_a_login_body_that_does_not_fit_is_refused(clean_engine: Engine, payload: object) -> None:
    client = make_client(build_auth_app(clean_engine))

    assert post_json(client, "/auth/login", payload).status_code == 422


def test_me_needs_a_login_and_returns_the_user_and_the_csrf_token(clean_engine: Engine) -> None:
    client = make_client(build_auth_app(clean_engine))
    assert client.get("/auth/me").status_code == 401

    csrf = sign_in(client)
    response = client.get("/auth/me")

    assert response.status_code == 200
    assert response.json() == {"email": EMAIL, "csrf_token": csrf}


def test_a_state_changing_request_needs_the_csrf_token(clean_engine: Engine) -> None:
    client = make_client(build_auth_app(clean_engine))
    csrf = sign_in(client)

    missing = post_json(client, "/auth/logout", None)
    wrong = post_json(client, "/auth/logout", None, csrf="wrong")

    assert missing.status_code == wrong.status_code == 403
    assert wrong.json() == {"detail": "Invalid CSRF token."}
    assert client.get("/auth/me").status_code == 200
    assert post_json(client, "/auth/logout", None, csrf=csrf).status_code == 204
    assert client.get("/auth/me").status_code == 401


def test_a_valid_session_is_not_enough_from_another_website(clean_engine: Engine) -> None:
    client = make_client(build_auth_app(clean_engine))
    csrf = sign_in(client)

    response = post_json(client, "/auth/logout", None, origin="http://evil.example", csrf=csrf)

    assert response.status_code == 403
    assert response.json() == {"detail": "Origin not allowed."}
    assert client.get("/auth/me").status_code == 200


def test_logging_out_kills_the_session_on_the_server_even_if_the_cookie_is_replayed(
    clean_engine: Engine,
) -> None:
    client = make_client(build_auth_app(clean_engine))
    csrf = sign_in(client)
    token = client.cookies.get("session")
    assert token is not None

    response = post_json(client, "/auth/logout", None, csrf=csrf)
    client.cookies.clear()
    client.cookies.set("session", token)

    assert "max-age=0" in response.headers["set-cookie"].lower()
    assert client.get("/auth/me").status_code == 401
    assert count(clean_engine, "sessions") == 0


def test_logging_out_everywhere_ends_the_session_of_every_device(clean_engine: Engine) -> None:
    app = build_auth_app(clean_engine)
    laptop, phone = make_client(app), make_client(app)
    csrf = sign_in(laptop)
    sign_in(phone)

    response = post_json(laptop, "/auth/logout-all", None, csrf=csrf)

    assert response.status_code == 204
    assert laptop.get("/auth/me").status_code == 401
    assert phone.get("/auth/me").status_code == 401


def test_logging_in_again_replaces_the_old_session(clean_engine: Engine) -> None:
    client = make_client(build_auth_app(clean_engine))
    sign_in(client)
    old = client.cookies.get("session")
    assert old is not None

    assert login(client).status_code == 200
    client.cookies.clear()
    client.cookies.set("session", old)

    assert client.get("/auth/me").status_code == 401
    assert count(clean_engine, "sessions") == 1


def test_an_expired_session_is_refused(clean_engine: Engine) -> None:
    client = make_client(build_auth_app(clean_engine))
    sign_in(client)
    with clean_engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE sessions SET created_at = now() - interval '2 days', "
                "last_seen_at = now() - interval '2 days', expires_at = now() - interval '1 day'"
            )
        )

    assert client.get("/auth/me").status_code == 401


def test_a_disabled_account_loses_its_session(clean_engine: Engine) -> None:
    client = make_client(build_auth_app(clean_engine))
    sign_in(client)
    with clean_engine.begin() as connection:
        connection.execute(text("UPDATE users SET is_active = false"))

    assert client.get("/auth/me").status_code == 401


@pytest.mark.parametrize("cookie", ["x" * 500, "has space", "caf%C3%A9", "../etc"])
def test_a_garbage_cookie_is_refused_without_an_error(clean_engine: Engine, cookie: str) -> None:
    client = make_client(build_auth_app(clean_engine))
    client.cookies.set("session", cookie)

    assert client.get("/auth/me").status_code == 401


def test_the_tracker_needs_a_login(clean_engine: Engine) -> None:
    app = build_auth_app(clean_engine)
    tracker, _ = make_tracker(clean_engine)
    app.dependency_overrides[get_tracker_service] = lambda: tracker
    client = make_client(app)
    assert client.get("/tracker/applications").status_code == 401

    sign_in(client)

    assert client.get("/tracker/applications").json() == []
    assert post_json(client, "/tracker/applications", {}).status_code == 403


@pytest.mark.parametrize("path", ["/render", "/job-offers/fetch"])
def test_the_other_protected_routes_refuse_anonymous_requests(
    clean_engine: Engine, path: str
) -> None:
    client = make_client(build_auth_app(clean_engine))

    assert post_json(client, path, {}).status_code == 401


def test_creating_an_application_needs_a_login(clean_engine: Engine) -> None:
    app = build_auth_app(clean_engine)
    app.dependency_overrides[get_application_service] = lambda: object()
    client = make_client(app)

    response = client.post(
        "/applications", files={"cv_file": ("cv.docx", b"x")}, data={"job_text": "x"}
    )

    assert response.status_code == 401


def test_the_browser_may_send_cookies_and_the_csrf_header(clean_engine: Engine) -> None:
    client = make_client(build_auth_app(clean_engine))

    response = client.options(
        "/auth/login",
        headers={
            "Origin": ORIGIN,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "x-csrf-token,content-type",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-credentials"] == "true"
    assert "x-csrf-token" in response.headers["access-control-allow-headers"].lower()
