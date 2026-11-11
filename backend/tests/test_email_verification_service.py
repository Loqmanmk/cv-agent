import re
import uuid

import pytest
from sqlalchemy import Engine, text

from app.domain.accounts import WeakPasswordError
from app.domain.mail import EmailMessage, EmailSender
from app.infrastructure.db.postgres_email_tokens import PostgresEmailTokenRepository
from app.infrastructure.db.postgres_users import PostgresUserRepository
from app.services.account_service import AccountService
from app.services.email_token_service import EmailTokenService
from app.services.email_verification import VerificationService
from tests.account_helpers import fast_hasher
from tests.auth_helpers import RecordingEmailSender

EMAIL = "jane.doe@example.com"
PASSWORD = "correct horse battery staple"
APP_URL = "https://app.example.com"
TOKEN_IN_LINK = re.compile(r"#token=([A-Za-z0-9_-]+)")


class FailingSender(EmailSender):
    def send(self, message: EmailMessage) -> None:
        raise ConnectionError("mail server down")


def build(
    engine: Engine, sender: EmailSender, base: str = APP_URL
) -> tuple[VerificationService, AccountService]:
    accounts = AccountService(PostgresUserRepository(engine), fast_hasher())
    tokens = EmailTokenService(PostgresEmailTokenRepository(engine))
    return VerificationService(accounts, tokens, sender, base), accounts


def token_of(message: EmailMessage) -> str:
    match = TOKEN_IN_LINK.search(message.text)
    assert match is not None
    return match.group(1)


def user_count(engine: Engine) -> int:
    with engine.connect() as connection:
        return int(connection.execute(text("SELECT count(*) FROM users")).scalar_one())


@pytest.fixture
def sender() -> RecordingEmailSender:
    return RecordingEmailSender()


def test_registering_sends_a_link_with_the_token_after_the_hash(
    clean_engine: Engine, sender: RecordingEmailSender
) -> None:
    service, _ = build(clean_engine, sender)

    service.register(" Jane.Doe@Example.COM ", PASSWORD)

    message = sender.messages[0]
    assert len(sender.messages) == 1
    assert message.to == EMAIL
    assert f"{APP_URL}/verify-email#token=" in message.text
    assert "?token=" not in message.text


def test_the_link_verifies_the_address_once(
    clean_engine: Engine, sender: RecordingEmailSender
) -> None:
    service, accounts = build(clean_engine, sender)
    service.register(EMAIL, PASSWORD)
    token = token_of(sender.messages[0])

    assert service.verify(token) is True
    assert service.verify(token) is False
    account = accounts.find_account(EMAIL)
    assert account is not None
    assert account.email_verified_at is not None


def test_an_existing_address_gets_a_notice_and_no_new_account(
    clean_engine: Engine, sender: RecordingEmailSender
) -> None:
    service, _ = build(clean_engine, sender)
    service.register(EMAIL, PASSWORD)

    service.register(EMAIL.upper(), "another long passphrase")

    notice = sender.messages[1]
    assert user_count(clean_engine) == 1
    assert notice.to == EMAIL
    assert "already have one" in notice.text
    assert f"{APP_URL}/login" in notice.text
    assert "#token=" not in notice.text


def test_a_weak_password_sends_nothing(clean_engine: Engine, sender: RecordingEmailSender) -> None:
    service, _ = build(clean_engine, sender)

    with pytest.raises(WeakPasswordError):
        service.register(EMAIL, "aaaa")

    assert sender.messages == []


def test_resending_gives_a_new_link_and_the_old_one_stops_working(
    clean_engine: Engine, sender: RecordingEmailSender
) -> None:
    service, _ = build(clean_engine, sender)
    service.register(EMAIL, PASSWORD)
    old = token_of(sender.messages[0])

    service.resend(EMAIL)

    new = token_of(sender.messages[1])
    assert service.verify(old) is False
    assert service.verify(new) is True


@pytest.mark.parametrize("email", ["nobody@example.com", "not an email", ""])
def test_resending_to_an_unknown_or_invalid_address_sends_nothing(
    clean_engine: Engine, sender: RecordingEmailSender, email: str
) -> None:
    service, _ = build(clean_engine, sender)

    service.resend(email)

    assert sender.messages == []


def test_a_verified_address_gets_no_new_link(
    clean_engine: Engine, sender: RecordingEmailSender
) -> None:
    service, _ = build(clean_engine, sender)
    service.register(EMAIL, PASSWORD)
    service.verify(token_of(sender.messages[0]))

    service.resend(EMAIL)

    assert len(sender.messages) == 1


def test_a_disabled_account_gets_no_link(
    clean_engine: Engine, sender: RecordingEmailSender
) -> None:
    service, _ = build(clean_engine, sender)
    service.register(EMAIL, PASSWORD)
    with clean_engine.begin() as connection:
        connection.execute(text("UPDATE users SET is_active = false"))

    service.resend(EMAIL)

    assert len(sender.messages) == 1


@pytest.mark.parametrize("token", [None, "", "garbage token", "x" * 300])
def test_a_bad_token_verifies_nothing(clean_engine: Engine, token: str | None) -> None:
    service, _ = build(clean_engine, RecordingEmailSender())

    assert service.verify(token) is False


def test_a_delivery_failure_does_not_change_the_outcome(clean_engine: Engine) -> None:
    service, accounts = build(clean_engine, FailingSender())

    service.register(EMAIL, PASSWORD)
    service.register(EMAIL, PASSWORD)
    service.resend(EMAIL)

    assert accounts.find_account(EMAIL) is not None


def test_a_trailing_slash_in_the_address_of_the_site_is_ignored(
    clean_engine: Engine, sender: RecordingEmailSender
) -> None:
    service, _ = build(clean_engine, sender, base="https://app.example.com/")

    service.register(EMAIL, PASSWORD)

    assert "https://app.example.com/verify-email#token=" in sender.messages[0].text


@pytest.mark.parametrize("base", ["", "app.example.com", "javascript:alert(1)", "ftp://x.y"])
def test_the_address_of_the_site_must_be_a_web_address(clean_engine: Engine, base: str) -> None:
    with pytest.raises(ValueError, match="APP_BASE_URL"):
        build(clean_engine, RecordingEmailSender(), base=base)


def test_finding_an_account_by_email_is_not_case_sensitive(clean_engine: Engine) -> None:
    service, accounts = build(clean_engine, RecordingEmailSender())
    service.register(EMAIL, PASSWORD)

    found = accounts.find_account(" JANE.DOE@example.com ")

    assert found is not None
    assert isinstance(found.id, uuid.UUID)
