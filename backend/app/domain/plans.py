import uuid
from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Literal, TypeGuard, get_args

Plan = Literal["free", "plus", "pro", "premium"]
PLANS: tuple[str, ...] = get_args(Plan)
UsageKind = Literal["application"]
USAGE_KINDS: tuple[str, ...] = get_args(UsageKind)


def is_plan(value: str) -> TypeGuard[Plan]:
    return value in PLANS


@dataclass(frozen=True)
class PlanLimits:
    """What a plan allows. Add a field here for every new advantage of a plan."""

    applications_per_month: int


# Placeholders: the real numbers depend on what one application costs with a paid AI service.
PLAN_LIMITS: dict[Plan, PlanLimits] = {
    "free": PlanLimits(applications_per_month=3),
    "plus": PlanLimits(applications_per_month=15),
    "pro": PlanLimits(applications_per_month=50),
    "premium": PlanLimits(applications_per_month=150),
}


class UnknownUserError(Exception):
    """Raised when a user does not exist (any more)."""


class QuotaExceededError(Exception):
    """Raised when the plan of a user does not allow another application this month."""

    def __init__(self, limit: int, resets_at: datetime) -> None:
        super().__init__(f"Monthly limit reached: {limit} applications on your plan.")
        self.limit = limit
        self.resets_at = resets_at


@dataclass(frozen=True)
class Reservation:
    """The answer to a request for one use. `id` is None when the limit is reached."""

    id: int | None
    plan: Plan
    used: int


class UsageRepository(ABC):
    """Contract for anything that counts the use of the platform."""

    @abstractmethod
    def reserve(
        self,
        user_id: uuid.UUID,
        kind: UsageKind,
        now: datetime,
        since: datetime,
        limits: Mapping[Plan, int],
    ) -> Reservation:
        """Count one use if the plan allows it. Two parallel calls can never both pass the limit."""

    @abstractmethod
    def release(self, user_id: uuid.UUID, reservation_id: int) -> None: ...

    @abstractmethod
    def used_since(self, user_id: uuid.UUID, kind: UsageKind, since: datetime) -> int: ...

    @abstractmethod
    def plan_of(self, user_id: uuid.UUID) -> Plan: ...
