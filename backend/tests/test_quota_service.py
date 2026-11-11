import uuid
from datetime import UTC, datetime, timedelta, timezone

import pytest
from sqlalchemy import Engine, text

from app.domain.plans import PLAN_LIMITS, PLANS, QuotaExceededError, UnknownUserError
from app.infrastructure.db.postgres_usage import PostgresUsageRepository
from app.services.quota_service import QuotaService, month_start, next_month_start
from tests.db_helpers import add_user

FREE_LIMIT = PLAN_LIMITS["free"].applications_per_month
NEXT_MONTH = datetime(2026, 12, 1, tzinfo=UTC)


class FakeClock:
    def __init__(self) -> None:
        self.now = datetime(2026, 11, 15, 12, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.now


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def user_id(clean_engine: Engine) -> uuid.UUID:
    return add_user(clean_engine, "jane@example.com")


@pytest.fixture
def quotas(clean_engine: Engine, clock: FakeClock) -> QuotaService:
    return QuotaService(PostgresUsageRepository(clean_engine), clock)


def use_the_whole_free_plan(quotas: QuotaService, user_id: uuid.UUID) -> list[int]:
    return [quotas.reserve_application(user_id) for _ in range(FREE_LIMIT)]


def test_the_month_starts_on_the_first_day_at_midnight_utc() -> None:
    assert month_start(datetime(2026, 11, 15, 12, 30, tzinfo=UTC)) == datetime(
        2026, 11, 1, tzinfo=UTC
    )


def test_the_month_is_counted_in_utc() -> None:
    late_evening_in_new_york = datetime(2026, 11, 30, 23, 30, tzinfo=timezone(timedelta(hours=-5)))

    assert month_start(late_evening_in_new_york) == NEXT_MONTH


def test_the_month_after_december_is_january() -> None:
    assert next_month_start(datetime(2026, 12, 20, tzinfo=UTC)) == datetime(2027, 1, 1, tzinfo=UTC)


def test_every_plan_has_a_limit_and_better_plans_allow_more() -> None:
    limits = [limits.applications_per_month for limits in PLAN_LIMITS.values()]

    assert list(PLAN_LIMITS) == list(PLANS)
    assert limits == sorted(limits)
    assert all(limit > 0 for limit in limits)


def test_the_free_plan_stops_at_its_limit(quotas: QuotaService, user_id: uuid.UUID) -> None:
    ids = use_the_whole_free_plan(quotas, user_id)

    with pytest.raises(QuotaExceededError) as raised:
        quotas.reserve_application(user_id)

    assert len(set(ids)) == FREE_LIMIT
    assert raised.value.limit == FREE_LIMIT
    assert raised.value.resets_at == NEXT_MONTH


def test_the_limit_resets_with_the_new_month(
    quotas: QuotaService, user_id: uuid.UUID, clock: FakeClock
) -> None:
    use_the_whole_free_plan(quotas, user_id)

    clock.now = NEXT_MONTH + timedelta(seconds=1)

    assert quotas.reserve_application(user_id) > 0


def test_a_released_application_does_not_count(quotas: QuotaService, user_id: uuid.UUID) -> None:
    ids = use_the_whole_free_plan(quotas, user_id)

    quotas.release(user_id, ids[0])

    assert quotas.reserve_application(user_id) > 0


def test_the_summary_shows_the_plan_the_use_and_the_reset(
    quotas: QuotaService, user_id: uuid.UUID
) -> None:
    quotas.reserve_application(user_id)

    summary = quotas.summary(user_id)

    assert (summary.plan, summary.used, summary.limit) == ("free", 1, FREE_LIMIT)
    assert summary.resets_at == NEXT_MONTH


def test_a_better_plan_allows_more(
    quotas: QuotaService, user_id: uuid.UUID, clean_engine: Engine
) -> None:
    with clean_engine.begin() as connection:
        connection.execute(text("UPDATE users SET plan = 'pro'"))

    for _ in range(FREE_LIMIT + 1):
        quotas.reserve_application(user_id)

    assert quotas.summary(user_id).limit == PLAN_LIMITS["pro"].applications_per_month


def test_an_unknown_user_is_reported(quotas: QuotaService) -> None:
    with pytest.raises(UnknownUserError):
        quotas.reserve_application(uuid.uuid4())
    with pytest.raises(UnknownUserError):
        quotas.summary(uuid.uuid4())
