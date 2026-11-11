import hashlib
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import Engine, text

from app.infrastructure.db.postgres_email_tokens import PostgresEmailTokenRepository
from app.services.email_token_service import EmailTokenService
from tests.db_helpers import add_user


class FakeClock:
    def __init__(self) -> None:
        self.now = datetime(2026, 11, 11, 12, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.now

    def advance(self, delta: timedelta) -> None:
        self.now += delta


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def user_id(clean_engine: Engine) -> uuid.UUID:
    return add_user(clean_engine, "jane@example.com")


@pytest.fixture
def tokens(clean_engine: Engine, clock: FakeClock) -> EmailTokenService:
    return EmailTokenService(PostgresEmailTokenRepository(clean_engine), clock)


def token_count(engine: Engine) -> int:
    with engine.connect() as connection:
        return int(connection.execute(text("SELECT count(*) FROM email_tokens")).scalar_one())


def test_a_token_gives_its_user_once(tokens: EmailTokenService, user_id: uuid.UUID) -> None:
    token = tokens.issue(user_id, "verify_email")

    assert len(token) >= 43
    assert tokens.consume(token, "verify_email") == user_id
    assert tokens.consume(token, "verify_email") is None


def test_the_database_stores_only_the_hash_of_the_token(
    tokens: EmailTokenService, user_id: uuid.UUID, clean_engine: Engine
) -> None:
    token = tokens.issue(user_id, "reset_password")

    with clean_engine.connect() as connection:
        stored = connection.execute(text("SELECT token_hash FROM email_tokens")).scalar_one()

    assert stored == hashlib.sha256(token.encode("ascii")).hexdigest()


def test_a_token_works_only_for_its_purpose_and_is_not_used_up_by_a_wrong_try(
    tokens: EmailTokenService, user_id: uuid.UUID
) -> None:
    token = tokens.issue(user_id, "verify_email")

    assert tokens.consume(token, "reset_password") is None
    assert tokens.consume(token, "verify_email") == user_id


def test_a_verification_link_lasts_two_days(
    tokens: EmailTokenService, user_id: uuid.UUID, clock: FakeClock
) -> None:
    token = tokens.issue(user_id, "verify_email")

    clock.advance(timedelta(hours=48))

    assert tokens.consume(token, "verify_email") is None


def test_a_reset_link_lasts_thirty_minutes(
    tokens: EmailTokenService, user_id: uuid.UUID, clock: FakeClock
) -> None:
    fresh = tokens.issue(user_id, "reset_password")
    clock.advance(timedelta(minutes=29))
    assert tokens.consume(fresh, "reset_password") == user_id

    late = tokens.issue(user_id, "reset_password")
    clock.advance(timedelta(minutes=31))

    assert tokens.consume(late, "reset_password") is None


def test_a_new_link_replaces_the_older_unused_one(
    tokens: EmailTokenService, user_id: uuid.UUID
) -> None:
    old = tokens.issue(user_id, "reset_password")
    new = tokens.issue(user_id, "reset_password")

    assert tokens.consume(old, "reset_password") is None
    assert tokens.consume(new, "reset_password") == user_id


def test_a_new_link_of_another_purpose_or_user_changes_nothing(
    tokens: EmailTokenService, user_id: uuid.UUID, clean_engine: Engine
) -> None:
    other = add_user(clean_engine, "other@example.com")
    verify = tokens.issue(user_id, "verify_email")
    theirs = tokens.issue(other, "verify_email")

    tokens.issue(user_id, "reset_password")

    assert tokens.consume(verify, "verify_email") == user_id
    assert tokens.consume(theirs, "verify_email") == other


@pytest.mark.parametrize(
    "token",
    [None, "", " ", "has space", "x" * 129, "caf\u00e9", "../etc", "unknown-but-well-formed"],
)
def test_a_missing_malformed_or_unknown_token_gives_nothing(
    tokens: EmailTokenService, user_id: uuid.UUID, token: str | None
) -> None:
    tokens.issue(user_id, "verify_email")

    assert tokens.consume(token, "verify_email") is None


def test_purging_removes_the_expired_tokens_only(
    tokens: EmailTokenService, user_id: uuid.UUID, clock: FakeClock, clean_engine: Engine
) -> None:
    tokens.issue(user_id, "reset_password")
    clock.advance(timedelta(hours=1))
    tokens.issue(user_id, "verify_email")

    assert tokens.purge_expired() == 1
    assert token_count(clean_engine) == 1
