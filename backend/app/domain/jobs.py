"""A generation that runs in the background, so a slow AI never times out the browser."""

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Literal

JobStatus = Literal["running", "done", "failed"]
# The steps of a generation, in order, as the user sees them.
Stage = Literal["queued", "reading", "translating", "tailoring", "rendering", "finished"]


class JobLimitError(Exception):
    """The user already has a generation running: one at a time."""


@dataclass(frozen=True)
class JobFailure:
    """Why a job failed, in the same words and status as a direct answer would give."""

    status: int
    detail: str
    violations: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class GenerationJob:
    id: uuid.UUID
    user_id: uuid.UUID
    status: JobStatus
    stage: Stage
    result: dict[str, object] | None = None
    failure: JobFailure | None = None


class JobStore(ABC):
    """Keeps the jobs while they run and for a short while after."""

    @abstractmethod
    def start(self, user_id: uuid.UUID) -> GenerationJob:
        """A new running job. Raises JobLimitError when the user already has one running."""

    @abstractmethod
    def set_stage(self, job_id: uuid.UUID, stage: Stage) -> None: ...

    @abstractmethod
    def finish(self, job_id: uuid.UUID, result: dict[str, object]) -> None: ...

    @abstractmethod
    def fail(self, job_id: uuid.UUID, failure: JobFailure) -> None: ...

    @abstractmethod
    def get(self, user_id: uuid.UUID, job_id: uuid.UUID) -> GenerationJob | None:
        """The job, only for the user who started it."""
