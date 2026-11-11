import threading
import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import Engine, text

from app.domain.plans import Plan, Reservation, UnknownUserError
from app.infrastructure.db.postgres_usage import PostgresUsageRepository
from tests.db_helpers import add_user

NOW = datetime(2026, 11, 15, 12, 0, tzinfo=UTC)
MONTH = datetime(2026, 11, 1, tzinfo=UTC)
LAST_MONTH = datetime(2026, 10, 20, 12, 0, tzinfo=UTC)
LAST_MONTH_START = datetime(2026, 10, 1, tzinfo=UTC)
LIMITS: dict[Plan, int] = {"free": 2, "plus": 4, "pro": 4, "premium": 4}
PARALLEL_REQUESTS = 6


@pytest.fixture
def usage(clean_engine: Engine) -> PostgresUsageRepository:
    return PostgresUsageRepository(clean_engine)


@pytest.fixture
def user_id(clean_engine: Engine) -> uuid.UUID:
    return add_user(clean_engine, "jane@example.com")


def reserve(
    usage: PostgresUsageRepository,
    user_id: uuid.UUID,
    now: datetime = NOW,
    since: datetime = MONTH,
) -> Reservation:
    return usage.reserve(user_id, "application", now, since, LIMITS)


def test_uses_are_counted_until_the_limit_of_the_plan(
    usage: PostgresUsageRepository, user_id: uuid.UUID
) -> None:
    first, second, third = [reserve(usage, user_id) for _ in range(3)]

    assert first.id is not None
    assert second.id is not None
    assert (first.used, second.used) == (1, 2)
    assert third == Reservation(None, "free", 2)


def test_uses_of_an_earlier_month_do_not_count(
    usage: PostgresUsageRepository, user_id: uuid.UUID
) -> None:
    for _ in range(2):
        reserve(usage, user_id, LAST_MONTH, LAST_MONTH_START)

    result = reserve(usage, user_id)

    assert result.id is not None
    assert result.used == 1


def test_a_released_use_frees_a_place(usage: PostgresUsageRepository, user_id: uuid.UUID) -> None:
    first = reserve(usage, user_id)
    reserve(usage, user_id)
    assert first.id is not None

    usage.release(user_id, first.id)

    assert reserve(usage, user_id).id is not None


def test_a_user_cannot_release_the_use_of_someone_else(
    usage: PostgresUsageRepository, user_id: uuid.UUID, clean_engine: Engine
) -> None:
    other = add_user(clean_engine, "other@example.com")
    first = reserve(usage, user_id)
    reserve(usage, user_id)
    assert first.id is not None

    usage.release(other, first.id)

    assert reserve(usage, user_id).id is None


def test_the_plan_decides_the_limit(
    usage: PostgresUsageRepository, user_id: uuid.UUID, clean_engine: Engine
) -> None:
    with clean_engine.begin() as connection:
        connection.execute(text("UPDATE users SET plan = 'plus'"))

    results = [reserve(usage, user_id) for _ in range(5)]

    assert [result.id is not None for result in results] == [True, True, True, True, False]
    assert results[-1].plan == "plus"


def test_counts_the_uses_since_a_date(usage: PostgresUsageRepository, user_id: uuid.UUID) -> None:
    reserve(usage, user_id)
    reserve(usage, user_id)

    assert usage.used_since(user_id, "application", MONTH) == 2
    assert usage.used_since(user_id, "application", datetime(2026, 12, 1, tzinfo=UTC)) == 0


def test_a_new_user_is_on_the_free_plan(usage: PostgresUsageRepository, user_id: uuid.UUID) -> None:
    assert usage.plan_of(user_id) == "free"


def test_an_unknown_user_is_reported(usage: PostgresUsageRepository) -> None:
    with pytest.raises(UnknownUserError):
        reserve(usage, uuid.uuid4())
    with pytest.raises(UnknownUserError):
        usage.plan_of(uuid.uuid4())


def test_parallel_requests_never_pass_the_limit_together(
    usage: PostgresUsageRepository, user_id: uuid.UUID
) -> None:
    barrier = threading.Barrier(PARALLEL_REQUESTS)
    results: list[Reservation] = []

    def attempt() -> None:
        barrier.wait()
        results.append(reserve(usage, user_id))

    threads = [threading.Thread(target=attempt) for _ in range(PARALLEL_REQUESTS)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert len(results) == PARALLEL_REQUESTS
    assert sum(result.id is not None for result in results) == LIMITS["free"]
