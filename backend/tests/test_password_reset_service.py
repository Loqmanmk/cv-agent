import re

import pytest
from sqlalchemy import Engine, text

from app.domain.accounts import InvalidCredentialsError, WeakPasswordError
from app.domain.mail import EmailMessage
from app.infrastructure.db.postgres_email_tokens import PostgresEmailTokenRepository
from app.infrastructure.db.postgres_sessions import PostgresSessionRepository
from app.infrastructure.db.postgres_users import PostgresUserRepository
from app.services.account_service import AccountService
from app.services.email_token_service import EmailTokenService
from app.services.password_reset import InvalidResetLinkError, PasswordResetService
from app.services.session_service import SessionService
from tests.account_helpers import fast_hasher
from tests.auth_helpers import RecordingEmailSender

EMAIL = "jane.doe@example.com"
OLD_PASSWORD = "correct horse battery staple"
NEW_PASSWORD = "a brand new long passphrase"
APP_URL = "https://app.example.com"
TOKEN_IN_LINK = re.compile(r"#token=([A-Za-z0-9_-]+)")


class Kit:
    def __init__(self, engine: Engine) -> None:
        self.sender = RecordingEmailSender()
        self.accounts = AccountService(PostgresUserRepository(engine), fast_hasher())
        self.tokens = EmailTokenService(PostgresEmailTokenRepository(engine))
        self.sessions = SessionService(PostgresSessionRepository(engine))
        self.resets = PasswordResetService(
            self.accounts, self.tokens, self.sessions, self.sender, APP_URL
        )


@pytest.fixture
def kit(clean_engine: Engine) -> Kit:
    tools = Kit(clean_engine)
    tools.accounts.register(EMAIL, OLD_PASSWORD)
    return tools


def token_of(message: EmailMessage) -> str:
    match = TOKEN_IN_LINK.search(message.text)
    assert match is not None
    return match.group(1)


def requested_token(kit: Kit) -> str:
    kit.resets.request(EMAIL)
    return token_of(kit.sender.messages[-1])


def test_asking_sends_a_reset_link_with_the_token_after_the_hash(kit: Kit) -> None:
    kit.resets.request(" Jane.Doe@Example.COM ")

    message = kit.sender.messages[0]
    assert message.to == EMAIL
    assert f"{APP_URL}/reset-password#token=" in message.text
    assert "30 minutes" in message.text


@pytest.mark.parametrize("email", ["nobody@example.com", "not an email", ""])
def test_asking_for_an_unknown_or_invalid_address_sends_nothing(kit: Kit, email: str) -> None:
    kit.resets.request(email)

    assert kit.sender.messages == []


def test_a_disabled_account_gets_no_link(kit: Kit, clean_engine: Engine) -> None:
    with clean_engine.begin() as connection:
        connection.execute(text("UPDATE users SET is_active = false"))

    kit.resets.request(EMAIL)

    assert kit.sender.messages == []


def test_resetting_replaces_the_password(kit: Kit) -> None:
    kit.resets.reset(requested_token(kit), NEW_PASSWORD)

    assert kit.accounts.authenticate(EMAIL, NEW_PASSWORD).email == EMAIL
    with pytest.raises(InvalidCredentialsError):
        kit.accounts.authenticate(EMAIL, OLD_PASSWORD)


def test_resetting_ends_every_session_and_verifies_the_address(kit: Kit) -> None:
    account = kit.accounts.authenticate(EMAIL, OLD_PASSWORD)
    laptop = kit.sessions.start(account.id)
    phone = kit.sessions.start(account.id)

    kit.resets.reset(requested_token(kit), NEW_PASSWORD)

    assert kit.sessions.authenticate(laptop.token) is None
    assert kit.sessions.authenticate(phone.token) is None
    refreshed = kit.accounts.get_account(account.id)
    assert refreshed is not None
    assert refreshed.email_verified_at is not None


def test_resetting_sends_a_warning_without_a_reset_token(kit: Kit) -> None:
    kit.resets.reset(requested_token(kit), NEW_PASSWORD)

    warning = kit.sender.messages[-1]
    assert warning.subject == "Your CV Agent password was changed"
    assert f"{APP_URL}/forgot-password" in warning.text
    assert "#token=" not in warning.text


def test_a_link_works_only_once(kit: Kit) -> None:
    token = requested_token(kit)
    kit.resets.reset(token, NEW_PASSWORD)

    with pytest.raises(InvalidResetLinkError):
        kit.resets.reset(token, "yet another long passphrase")


def test_a_weak_password_does_not_use_up_the_link(kit: Kit) -> None:
    token = requested_token(kit)

    with pytest.raises(WeakPasswordError):
        kit.resets.reset(token, "short")

    kit.resets.reset(token, NEW_PASSWORD)
    assert kit.accounts.authenticate(EMAIL, NEW_PASSWORD).email == EMAIL


def test_a_verification_link_cannot_reset_a_password(kit: Kit) -> None:
    account = kit.accounts.authenticate(EMAIL, OLD_PASSWORD)
    verify_token = kit.tokens.issue(account.id, "verify_email")

    with pytest.raises(InvalidResetLinkError):
        kit.resets.reset(verify_token, NEW_PASSWORD)


@pytest.mark.parametrize("token", [None, "", "garbage token", "unknown-but-well-formed"])
def test_a_bad_link_is_refused(kit: Kit, token: str | None) -> None:
    with pytest.raises(InvalidResetLinkError):
        kit.resets.reset(token, NEW_PASSWORD)


def test_a_disabled_account_cannot_be_reset(kit: Kit, clean_engine: Engine) -> None:
    token = requested_token(kit)
    with clean_engine.begin() as connection:
        connection.execute(text("UPDATE users SET is_active = false"))

    with pytest.raises(InvalidResetLinkError):
        kit.resets.reset(token, NEW_PASSWORD)
