import re

import pytest
from sqlalchemy import Engine

from app.domain.mail import EmailMessage
from tests.auth_helpers import (
    EMAIL,
    PASSWORD,
    RecordingEmailSender,
    build_auth_app,
    login,
    make_client,
    post_json,
    sign_in,
)

NEW_PASSWORD = "a brand new long passphrase"
RESET_SENT = {
    "detail": "If an account exists for this address, we sent a link to reset your password."
}
TOKEN_IN_LINK = re.compile(r"#token=([A-Za-z0-9_-]+)")


def last_token(sender: RecordingEmailSender) -> str:
    message: EmailMessage = sender.messages[-1]
    match = TOKEN_IN_LINK.search(message.text)
    assert match is not None
    return match.group(1)


def test_asking_answers_the_same_for_known_and_unknown_addresses(clean_engine: Engine) -> None:
    sender = RecordingEmailSender()
    client = make_client(build_auth_app(clean_engine, sender=sender))
    sign_in(client)
    sent_before = len(sender.messages)

    known = post_json(client, "/auth/forgot-password", {"email": EMAIL})
    unknown = post_json(client, "/auth/forgot-password", {"email": "nobody@example.com"})

    assert known.status_code == unknown.status_code == 202
    assert known.json() == unknown.json() == RESET_SENT
    assert len(sender.messages) == sent_before + 1


def test_asking_is_limited_per_address(clean_engine: Engine) -> None:
    client = make_client(build_auth_app(clean_engine, emails_per_account=1))

    statuses = [
        post_json(client, "/auth/forgot-password", {"email": EMAIL}).status_code for _ in range(2)
    ]

    assert statuses == [202, 429]


def test_a_reset_logs_out_everywhere_and_the_new_password_works(clean_engine: Engine) -> None:
    sender = RecordingEmailSender()
    client = make_client(build_auth_app(clean_engine, sender=sender))
    sign_in(client)
    post_json(client, "/auth/forgot-password", {"email": EMAIL})

    response = post_json(
        client, "/auth/reset-password", {"token": last_token(sender), "password": NEW_PASSWORD}
    )

    assert response.status_code == 200
    assert "every device was logged out" in response.json()["detail"]
    assert "max-age=0" in response.headers["set-cookie"].lower()
    assert client.get("/auth/me").status_code == 401
    assert login(client, password=PASSWORD).status_code == 401
    assert login(client, password=NEW_PASSWORD).status_code == 200


def test_a_weak_password_is_refused_with_its_problems(clean_engine: Engine) -> None:
    sender = RecordingEmailSender()
    client = make_client(build_auth_app(clean_engine, sender=sender))
    sign_in(client)
    post_json(client, "/auth/forgot-password", {"email": EMAIL})

    response = post_json(
        client, "/auth/reset-password", {"token": last_token(sender), "password": "short"}
    )

    assert response.status_code == 422
    assert "Use at least 12 characters." in response.json()["problems"]


def test_a_bad_link_is_refused(clean_engine: Engine) -> None:
    client = make_client(build_auth_app(clean_engine))

    response = post_json(
        client, "/auth/reset-password", {"token": "unknown-token", "password": NEW_PASSWORD}
    )

    assert response.status_code == 400
    assert "invalid or has expired" in response.json()["detail"]


@pytest.mark.parametrize("path", ["/auth/forgot-password", "/auth/reset-password"])
def test_these_requests_are_refused_from_another_website(clean_engine: Engine, path: str) -> None:
    client = make_client(build_auth_app(clean_engine))
    payload = (
        {"email": EMAIL} if path.endswith("forgot-password") else {"token": "x", "password": "y"}
    )

    assert post_json(client, path, payload, origin="http://evil.example").status_code == 403
