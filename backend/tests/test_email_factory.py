from pathlib import Path
from typing import Any

import pytest
from pydantic import SecretStr

from app.infrastructure.email_factory import build_email_sender
from app.infrastructure.outbox_sender import OutboxEmailSender
from app.infrastructure.smtp_sender import SmtpEmailSender
from tests.test_config import IsolatedSettings

SMTP: dict[str, Any] = {
    "email_backend": "smtp",
    "smtp_host": "smtp.example.com",
    "smtp_username": "smtp-user",
    "smtp_password": SecretStr("smtp-password"),
    "email_from_address": "no-reply@cvagent.example",
}


def settings(**values: Any) -> IsolatedSettings:
    return IsolatedSettings(**values)


def test_development_keeps_writing_emails_to_files(tmp_path: Path) -> None:
    sender = build_email_sender(settings(email_outbox_dir=str(tmp_path)))

    assert isinstance(sender, OutboxEmailSender)


def test_smtp_is_used_when_it_is_fully_configured() -> None:
    assert isinstance(build_email_sender(settings(**SMTP)), SmtpEmailSender)


@pytest.mark.parametrize(
    ("missing", "value"),
    [
        ("smtp_host", ""),
        ("smtp_username", " "),
        ("smtp_password", None),
        ("smtp_password", SecretStr("")),
        ("email_from_address", ""),
    ],
)
def test_an_incomplete_smtp_configuration_stops_the_start(missing: str, value: object) -> None:
    with pytest.raises(ValueError, match="these are empty"):
        build_email_sender(settings(**(SMTP | {missing: value})))


def test_the_error_names_the_settings_but_never_the_password() -> None:
    with pytest.raises(ValueError) as caught:
        build_email_sender(settings(**(SMTP | {"smtp_host": ""})))

    assert "SMTP_HOST" in str(caught.value)
    assert "smtp-password" not in str(caught.value)


@pytest.mark.parametrize(
    ("name", "value", "message"),
    [
        ("email_backend", "carrier-pigeon", "EMAIL_BACKEND"),
        ("smtp_security", "none", "SMTP_SECURITY"),
        ("email_from_address", "not-an-address", "EMAIL_FROM_ADDRESS"),
    ],
)
def test_a_wrong_value_is_refused(name: str, value: str, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        build_email_sender(settings(**(SMTP | {name: value})))
