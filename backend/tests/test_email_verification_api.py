import re

import pytest
from sqlalchemy import Engine, text

from app.api.account_dependencies import get_profile_service, get_quota_service
from app.api.dependencies import get_application_service
from app.domain.mail import EmailMessage
from tests.auth_helpers import (
    EMAIL,
    ORIGIN,
    PASSWORD,
    RecordingEmailSender,
    build_auth_app,
    login,
    make_client,
    post_json,
    register,
    sign_in,
)
from tests.test_api import INCOMPLETE_PROFILE, FakeProfiles, FakeQuotas
from tests.test_application_service import make_docx

CHECK_INBOX = {"detail": "Check your inbox: we sent you a link to confirm your email address."}
TOKEN_IN_LINK = re.compile(r"#token=([A-Za-z0-9_-]+)")


def token_of(message: EmailMessage) -> str:
    match = TOKEN_IN_LINK.search(message.text)
    assert match is not None
    return match.group(1)


def user_count(engine: Engine) -> int:
    with engine.connect() as connection:
        return int(connection.execute(text("SELECT count(*) FROM users")).scalar_one())


def test_registering_answers_the_same_whether_the_address_is_new_or_not(
    clean_engine: Engine,
) -> None:
    sender = RecordingEmailSender()
    client = make_client(build_auth_app(clean_engine, sender=sender))

    first = register(client)
    second = register(client)

    assert first.status_code == second.status_code == 202
    assert first.json() == second.json() == CHECK_INBOX
    assert PASSWORD not in first.text
    assert user_count(clean_engine) == 1
    assert [message.subject for message in sender.messages] == [
        "Confirm your email address for CV Agent",
        "You already have a CV Agent account",
    ]


def test_registrations_are_limited_per_address(clean_engine: Engine) -> None:
    client = make_client(build_auth_app(clean_engine, register_limit=1))

    statuses = [register(client, f"user{number}@example.com").status_code for number in range(2)]

    assert statuses == [202, 429]


def test_the_emails_to_one_address_are_limited(clean_engine: Engine) -> None:
    sender = RecordingEmailSender()
    client = make_client(build_auth_app(clean_engine, emails_per_account=2, sender=sender))
    register(client)

    statuses = [
        post_json(client, "/auth/resend-verification", {"email": EMAIL}).status_code
        for _ in range(2)
    ]

    assert statuses == [202, 429]
    assert len(sender.messages) == 2


def test_resending_to_an_unknown_address_looks_the_same_and_sends_nothing(
    clean_engine: Engine,
) -> None:
    sender = RecordingEmailSender()
    client = make_client(build_auth_app(clean_engine, sender=sender))

    response = post_json(client, "/auth/resend-verification", {"email": "nobody@example.com"})

    assert response.status_code == 202
    assert response.json() == CHECK_INBOX
    assert sender.messages == []


def test_the_link_verifies_the_address_once(clean_engine: Engine) -> None:
    sender = RecordingEmailSender()
    client = make_client(build_auth_app(clean_engine, sender=sender))
    register(client)
    token = token_of(sender.messages[0])
    assert login(client).json()["email_verified"] is False

    first = post_json(client, "/auth/verify-email", {"token": token})
    second = post_json(client, "/auth/verify-email", {"token": token})

    assert first.status_code == 200
    assert first.json() == {"detail": "Your email address is verified."}
    assert second.status_code == 400
    assert "invalid or has expired" in second.json()["detail"]
    assert client.get("/auth/me").json()["email_verified"] is True


@pytest.mark.parametrize(
    "payload", [{"token": ""}, {"token": "x" * 257}, {}, {"token": "abc", "extra": 1}]
)
def test_a_verification_body_that_does_not_fit_is_refused(
    clean_engine: Engine, payload: object
) -> None:
    client = make_client(build_auth_app(clean_engine))

    assert post_json(client, "/auth/verify-email", payload).status_code == 422


@pytest.mark.parametrize("path", ["/auth/verify-email", "/auth/resend-verification"])
def test_these_requests_are_refused_from_another_website(clean_engine: Engine, path: str) -> None:
    client = make_client(build_auth_app(clean_engine))
    payload = {"token": "abc"} if path.endswith("email") else {"email": EMAIL}

    response = post_json(client, path, payload, origin="http://evil.example")

    assert response.status_code == 403


def test_an_unverified_user_cannot_create_an_application_until_verified(
    clean_engine: Engine,
) -> None:
    app = build_auth_app(clean_engine)
    app.dependency_overrides[get_application_service] = lambda: object()
    app.dependency_overrides[get_profile_service] = lambda: FakeProfiles(INCOMPLETE_PROFILE)
    app.dependency_overrides[get_quota_service] = lambda: FakeQuotas()
    client = make_client(app)
    csrf = sign_in(client)

    def create() -> int:
        response = client.post(
            "/applications",
            files={"cv_file": ("cv.docx", make_docx())},
            data={"job_text": "Acme seeks an intern."},
            headers={"Origin": ORIGIN, "X-CSRF-Token": csrf},
        )
        return int(response.status_code)

    assert create() == 403
    with clean_engine.begin() as connection:
        connection.execute(text("UPDATE users SET email_verified_at = now()"))
    assert create() == 422
