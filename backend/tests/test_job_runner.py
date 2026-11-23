import uuid
from concurrent.futures import Executor, Future
from typing import Any

from app.api.errors import describe_error
from app.domain.jobs import JobFailure
from app.domain.llm import LLMUnavailableError
from app.infrastructure.memory_job_store import InMemoryJobStore
from app.services.job_runner import JobRunner, StageReporter
from tests.fakes import ImmediateExecutor

USER = uuid.uuid4()


class HeldExecutor(Executor):
    """Keeps the tasks without running them, to look at a job while it runs."""

    def __init__(self) -> None:
        self.tasks: list[tuple[Any, tuple[Any, ...]]] = []

    def submit(self, fn: Any, /, *args: Any, **kwargs: Any) -> Future[Any]:
        self.tasks.append((fn, args))
        return Future()

    def run_all(self) -> None:
        for fn, args in self.tasks:
            fn(*args)


def test_a_job_runs_in_the_background_and_reports_its_stages() -> None:
    executor = HeldExecutor()
    runner = JobRunner(InMemoryJobStore(), executor, describe_error)
    seen: list[str] = []

    def work(report: StageReporter) -> dict[str, object]:
        report("reading")
        seen.append(runner.get(USER, job.id).stage)  # type: ignore[union-attr]
        report("tailoring")
        return {"answer": 42}

    job = runner.submit(USER, work)
    assert runner.get(USER, job.id).status == "running"  # type: ignore[union-attr]

    executor.run_all()

    done = runner.get(USER, job.id)
    assert seen == ["reading"]
    assert done is not None
    assert (done.status, done.result) == ("done", {"answer": 42})


def test_a_failing_job_records_what_the_user_would_have_been_told() -> None:
    runner = JobRunner(InMemoryJobStore(), ImmediateExecutor(), describe_error)

    def work(_report: StageReporter) -> dict[str, object]:
        raise LLMUnavailableError("quota secret")

    job = runner.submit(USER, work)

    failed = runner.get(USER, job.id)
    assert failed is not None
    assert failed.status == "failed"
    assert failed.failure is not None
    assert failed.failure.status == 503
    assert "quota secret" not in failed.failure.detail


def test_an_unexpected_error_fails_the_job_without_its_internals() -> None:
    runner = JobRunner(InMemoryJobStore(), ImmediateExecutor(), describe_error)

    def work(_report: StageReporter) -> dict[str, object]:
        raise RuntimeError("internal secret")

    job = runner.submit(USER, work)

    failed = runner.get(USER, job.id)
    assert failed is not None
    assert failed.failure == JobFailure(500, "Something went wrong. Please try again.")
