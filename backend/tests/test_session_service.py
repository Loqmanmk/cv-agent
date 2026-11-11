import hashlib
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import Engine, text

from app.infrastructure.db.postgres_sessions import PostgresSessionRepository
from app.services.session_service import (
    ABSOLUTE_LIFETIME,
    IDLE_LIFETIME,
    TOUCH_INTERVAL,
    ActiveSession,
    SessionService,
    csrf_matches,
)
from tests.db_helpers import add_user


class FakeClock:
    def __init__(self) -> None:
        self.now = datetime(2026, 11, 9, 12, 0, tzinfo=UTC)

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
def sessions(clean_engine: Engine, clock: FakeClock) -> SessionService:
    return SessionService(PostgresSessionRepository(clean_engine), clock)


def session_count(engine: Engine) -> int:
    with engine.connect() as connection:
        return int(connection.execute(text("SELECT count(*) FROM sessions")).scalar_one())


def last_seen(engine: Engine) -> datetime:
    with engine.connect() as connection:
        value = connection.execute(text("SELECT last_seen_at FROM sessions")).scalar_one()
    assert isinstance(value, datetime)
    return value


def test_a_new_session_has_a_long_random_token_and_its_own_csrf_token(
    sessions: SessionService, user_id: uuid.UUID, clock: FakeClock
) -> None:
    started = sessions.start(user_id)

    assert len(started.token) >= 43
    assert len(started.csrf_token) >= 43
    assert started.token != started.csrf_token
    assert started.expires_at == clock.now + ABSOLUTE_LIFETIME


def test_every_login_gets_a_different_token_and_both_stay_valid(
    sessions: SessionService, user_id: uuid.UUID
) -> None:
    first = sessions.start(user_id)
    second = sessions.start(user_id)

    assert first.token != second.token
    assert sessions.authenticate(first.token) is not None
    assert sessions.authenticate(second.token) is not None


def test_the_database_stores_only_the_hash_of_the_token(
    sessions: SessionService, user_id: uuid.UUID, clean_engine: Engine
) -> None:
    started = sessions.start(user_id)

    with clean_engine.connect() as connection:
        stored = connection.execute(text("SELECT token_hash FROM sessions")).scalar_one()

    assert stored == hashlib.sha256(started.token.encode("ascii")).hexdigest()
    assert started.token not in stored


def test_the_tokens_never_appear_in_a_printed_session(
    sessions: SessionService, user_id: uuid.UUID
) -> None:
    started = sessions.start(user_id)
    active = sessions.authenticate(started.token)

    assert started.token not in repr(started)
    assert started.csrf_token not in repr(started)
    assert active is not None
    assert started.csrf_token not in repr(active)


def test_a_valid_token_gives_the_user_and_the_csrf_token(
    sessions: SessionService, user_id: uuid.UUID
) -> None:
    started = sessions.start(user_id)

    assert sessions.authenticate(started.token) == ActiveSession(user_id, started.csrf_token)


@pytest.mark.parametrize(
    "token",
    [None, "", " ", "unknown-but-well-formed-token", "has space", "x" * 129, "caf\u00e9", "../etc"],
)
def test_a_token_that_is_missing_unknown_or_malformed_gives_nothing(
    sessions: SessionService, user_id: uuid.UUID, token: str | None
) -> None:
    sessions.start(user_id)

    assert sessions.authenticate(token) is None


def test_a_session_ends_after_its_maximum_lifetime_even_if_it_is_used(
    sessions: SessionService, user_id: uuid.UUID, clock: FakeClock, clean_engine: Engine
) -> None:
    started = sessions.start(user_id)
    for _ in range(9):
        clock.advance(timedelta(days=3))
        assert sessions.authenticate(started.token) is not None

    clock.advance(timedelta(days=3, seconds=1))

    assert sessions.authenticate(started.token) is None
    assert session_count(clean_engine) == 0


def test_a_session_unused_for_a_week_ends(
    sessions: SessionService, user_id: uuid.UUID, clock: FakeClock, clean_engine: Engine
) -> None:
    started = sessions.start(user_id)

    clock.advance(IDLE_LIFETIME)

    assert sessions.authenticate(started.token) is None
    assert session_count(clean_engine) == 0


def test_using_a_session_keeps_it_alive(
    sessions: SessionService, user_id: uuid.UUID, clock: FakeClock
) -> None:
    started = sessions.start(user_id)
    almost_a_week = IDLE_LIFETIME - timedelta(hours=1)

    clock.advance(almost_a_week)
    assert sessions.authenticate(started.token) is not None
    clock.advance(almost_a_week)
    assert sessions.authenticate(started.token) is not None
    clock.advance(IDLE_LIFETIME)

    assert sessions.authenticate(started.token) is None


def test_the_last_seen_time_is_not_written_on_every_request(
    sessions: SessionService, user_id: uuid.UUID, clock: FakeClock, clean_engine: Engine
) -> None:
    started = sessions.start(user_id)
    created = clock.now

    clock.advance(timedelta(minutes=1))
    sessions.authenticate(started.token)
    assert last_seen(clean_engine) == created

    clock.advance(TOUCH_INTERVAL)
    sessions.authenticate(started.token)
    assert last_seen(clean_engine) == clock.now


def test_a_disabled_account_loses_its_sessions(
    sessions: SessionService, user_id: uuid.UUID, clean_engine: Engine
) -> None:
    started = sessions.start(user_id)
    with clean_engine.begin() as connection:
        connection.execute(text("UPDATE users SET is_active = false"))

    assert sessions.authenticate(started.token) is None
    assert session_count(clean_engine) == 0


def test_logging_out_ends_only_that_session(sessions: SessionService, user_id: uuid.UUID) -> None:
    phone = sessions.start(user_id)
    laptop = sessions.start(user_id)

    sessions.end(phone.token)

    assert sessions.authenticate(phone.token) is None
    assert sessions.authenticate(laptop.token) is not None


def test_logging_out_twice_or_with_garbage_is_harmless(
    sessions: SessionService, user_id: uuid.UUID
) -> None:
    started = sessions.start(user_id)

    sessions.end(started.token)
    sessions.end(started.token)
    sessions.end(None)
    sessions.end("x" * 500)
    sessions.end("not a token")


def test_logging_out_everywhere_ends_every_session_of_that_user_only(
    sessions: SessionService, user_id: uuid.UUID, clean_engine: Engine
) -> None:
    other = add_user(clean_engine, "other@example.com")
    mine = [sessions.start(user_id), sessions.start(user_id)]
    theirs = sessions.start(other)

    sessions.end_all(user_id)

    assert all(sessions.authenticate(item.token) is None for item in mine)
    assert sessions.authenticate(theirs.token) is not None


def test_purging_removes_idle_sessions_and_keeps_the_others(
    sessions: SessionService, user_id: uuid.UUID, clock: FakeClock, clean_engine: Engine
) -> None:
    sessions.start(user_id)
    clock.advance(timedelta(days=8))
    fresh = sessions.start(user_id)

    removed = sessions.purge_expired()

    assert removed == 1
    assert session_count(clean_engine) == 1
    assert sessions.authenticate(fresh.token) is not None


def test_purging_removes_sessions_past_their_maximum_lifetime(
    clean_engine: Engine, user_id: uuid.UUID, clock: FakeClock
) -> None:
    short = SessionService(
        PostgresSessionRepository(clean_engine), clock, absolute_lifetime=timedelta(hours=1)
    )
    short.start(user_id)
    clock.advance(timedelta(hours=2))

    assert short.purge_expired() == 1
    assert session_count(clean_engine) == 0


def test_purging_with_nothing_to_remove_returns_zero(sessions: SessionService) -> None:
    assert sessions.purge_expired() == 0


@pytest.mark.parametrize(
    ("expected", "supplied", "result"),
    [
        ("abc", "abc", True),
        ("abc", "abd", False),
        ("abc", "ab", False),
        ("abc", "abcd", False),
        ("abc", "", False),
        ("abc", None, False),
        ("abc", "caf\u00e9", False),
    ],
)
def test_the_csrf_token_must_match_exactly(
    expected: str, supplied: str | None, result: bool
) -> None:
    assert csrf_matches(expected, supplied) is result
