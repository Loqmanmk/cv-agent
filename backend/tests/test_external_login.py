import pytest
from sqlalchemy import Engine, text

from app.domain.accounts import InvalidCredentialsError
from app.domain.oauth import ExternalIdentity, OAuthError
from app.infrastructure.db.postgres_oauth import PostgresOAuthIdentityRepository
from app.infrastructure.db.postgres_sessions import PostgresSessionRepository
from app.infrastructure.db.postgres_users import PostgresUserRepository
from app.services.account_service import AccountService
from app.services.external_login import ExternalLoginService
from app.services.session_service import SessionService
from tests.account_helpers import fast_hasher

EMAIL = "jane.doe@gmail.com"
PASSWORD = "correct horse battery staple"


class Kit:
    def __init__(self, engine: Engine) -> None:
        users = PostgresUserRepository(engine)
        self.accounts = AccountService(users, fast_hasher())
        self.sessions = SessionService(PostgresSessionRepository(engine))
        self.login = ExternalLoginService(
            users, PostgresOAuthIdentityRepository(engine), self.sessions
        )


@pytest.fixture
def kit(clean_engine: Engine) -> Kit:
    return Kit(clean_engine)


def google(
    subject: str = "g-1", email: str = "Jane.Doe@gmail.com", verified: bool = True
) -> ExternalIdentity:
    return ExternalIdentity("google", subject, email, verified)


def count(engine: Engine, table: str) -> int:
    queries = {
        "users": "SELECT count(*) FROM users",
        "oauth_identities": "SELECT count(*) FROM oauth_identities",
    }
    with engine.connect() as connection:
        return int(connection.execute(text(queries[table])).scalar_one())


def test_a_new_google_user_gets_a_verified_account_without_a_password(
    kit: Kit, clean_engine: Engine
) -> None:
    account = kit.login.sign_in(google())

    assert account.email == EMAIL
    assert account.email_verified_at is not None
    assert count(clean_engine, "oauth_identities") == 1
    with pytest.raises(InvalidCredentialsError):
        kit.accounts.authenticate(EMAIL, "!")


def test_the_same_google_identity_finds_the_same_account_even_after_an_email_change(
    kit: Kit, clean_engine: Engine
) -> None:
    first = kit.login.sign_in(google())

    again = kit.login.sign_in(google(email="new.address@gmail.com"))

    assert again.id == first.id
    assert count(clean_engine, "users") == 1


def test_an_existing_confirmed_account_is_linked_and_keeps_its_password(
    kit: Kit, clean_engine: Engine
) -> None:
    registered = kit.accounts.register(EMAIL, PASSWORD)
    kit.accounts.mark_email_verified(registered.id)

    account = kit.login.sign_in(google())

    assert account.id == registered.id
    assert kit.accounts.authenticate(EMAIL, PASSWORD).id == registered.id
    assert count(clean_engine, "users") == 1


def test_an_unconfirmed_account_loses_its_password_and_sessions_before_linking(
    kit: Kit,
) -> None:
    squatter = kit.accounts.register(EMAIL, PASSWORD)
    squatter_session = kit.sessions.start(squatter.id)

    account = kit.login.sign_in(google())

    assert account.id == squatter.id
    assert account.email_verified_at is not None
    assert kit.sessions.authenticate(squatter_session.token) is None
    with pytest.raises(InvalidCredentialsError):
        kit.accounts.authenticate(EMAIL, PASSWORD)


def test_an_unverified_google_email_is_refused(kit: Kit, clean_engine: Engine) -> None:
    with pytest.raises(OAuthError, match="not verified"):
        kit.login.sign_in(google(verified=False))

    assert count(clean_engine, "users") == 0


def test_a_disabled_account_cannot_sign_in_with_google(kit: Kit, clean_engine: Engine) -> None:
    kit.login.sign_in(google())
    with clean_engine.begin() as connection:
        connection.execute(text("UPDATE users SET is_active = false"))

    with pytest.raises(OAuthError, match="cannot be used"):
        kit.login.sign_in(google())


@pytest.mark.parametrize("email", ["not an email", "someone@anything.invalid"])
def test_an_email_that_is_not_acceptable_is_refused(kit: Kit, email: str) -> None:
    with pytest.raises(OAuthError):
        kit.login.sign_in(google(email=email))


def test_two_different_google_identities_for_one_address_share_the_account(
    kit: Kit, clean_engine: Engine
) -> None:
    first = kit.login.sign_in(google(subject="g-1"))

    second = kit.login.sign_in(google(subject="g-2"))

    assert second.id == first.id
    assert count(clean_engine, "oauth_identities") == 2
