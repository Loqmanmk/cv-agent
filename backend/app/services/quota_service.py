import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from app.domain.plans import PLAN_LIMITS, Plan, QuotaExceededError, UsageRepository

APPLICATION_LIMITS: dict[Plan, int] = {
    plan: limits.applications_per_month for plan, limits in PLAN_LIMITS.items()
}


def _utc_now() -> datetime:
    return datetime.now(UTC)


def month_start(moment: datetime) -> datetime:
    """Quotas follow calendar months in UTC, the same for every user in the world."""
    utc = moment.astimezone(UTC)
    return utc.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def next_month_start(moment: datetime) -> datetime:
    start = month_start(moment)
    if start.month == 12:
        return start.replace(year=start.year + 1, month=1)
    return start.replace(month=start.month + 1)


@dataclass(frozen=True)
class UsageSummary:
    plan: Plan
    used: int
    limit: int
    resets_at: datetime


class QuotaService:
    """Applies the monthly limits of each plan."""

    def __init__(self, usage: UsageRepository, clock: Callable[[], datetime] = _utc_now) -> None:
        self._usage = usage
        self._clock = clock

    def reserve_application(self, user_id: uuid.UUID) -> int:
        """Count one application, or raise QuotaExceededError. Returns the reservation id."""
        now = self._clock()
        reservation = self._usage.reserve(
            user_id, "application", now, month_start(now), APPLICATION_LIMITS
        )
        if reservation.id is None:
            raise QuotaExceededError(APPLICATION_LIMITS[reservation.plan], next_month_start(now))
        return reservation.id

    def release(self, user_id: uuid.UUID, reservation_id: int) -> None:
        """Give the use back, for example when the application failed."""
        self._usage.release(user_id, reservation_id)

    def summary(self, user_id: uuid.UUID) -> UsageSummary:
        now = self._clock()
        plan = self._usage.plan_of(user_id)
        used = self._usage.used_since(user_id, "application", month_start(now))
        return UsageSummary(plan, used, APPLICATION_LIMITS[plan], next_month_start(now))
