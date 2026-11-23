import uuid

import pytest

from app.domain.jobs import JobFailure, JobLimitError
from app.infrastructure.memory_job_store import (
    KEEP_FINISHED_SECONDS,
    MAX_JOBS,
    MAX_RUNNING_SECONDS,
    InMemoryJobStore,
)

ALICE = uuid.uuid4()
BOB = uuid.uuid4()


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def test_a_job_moves_through_its_stages_to_its_result() -> None:
    store = InMemoryJobStore()
    job = store.start(ALICE)

    store.set_stage(job.id, "tailoring")
    assert store.get(ALICE, job.id).stage == "tailoring"  # type: ignore[union-attr]

    store.finish(job.id, {"cv": "ok"})
    done = store.get(ALICE, job.id)
    assert done is not None
    assert (done.status, done.stage, done.result) == ("done", "finished", {"cv": "ok"})


def test_a_failed_job_keeps_its_failure() -> None:
    store = InMemoryJobStore()
    job = store.start(ALICE)

    store.fail(job.id, JobFailure(503, "busy"))

    failed = store.get(ALICE, job.id)
    assert failed is not None
    assert (failed.status, failed.failure) == ("failed", JobFailure(503, "busy"))


def test_only_the_user_who_started_a_job_can_see_it() -> None:
    store = InMemoryJobStore()
    job = store.start(ALICE)

    assert store.get(BOB, job.id) is None
    assert store.get(ALICE, uuid.uuid4()) is None


def test_one_running_job_per_user() -> None:
    store = InMemoryJobStore()
    first = store.start(ALICE)

    with pytest.raises(JobLimitError):
        store.start(ALICE)
    store.start(BOB)  # other users are not blocked
    store.finish(first.id, {})
    store.start(ALICE)  # a finished job no longer blocks


def test_a_finished_job_is_forgotten_after_a_while() -> None:
    clock = Clock()
    store = InMemoryJobStore(clock)
    job = store.start(ALICE)
    store.finish(job.id, {})

    clock.now += KEEP_FINISHED_SECONDS - 1
    assert store.get(ALICE, job.id) is not None
    clock.now += 2
    assert store.get(ALICE, job.id) is None


def test_a_job_stuck_running_stops_blocking_its_user() -> None:
    clock = Clock()
    store = InMemoryJobStore(clock)
    store.start(ALICE)

    clock.now += MAX_RUNNING_SECONDS + 1

    store.start(ALICE)


def test_past_the_cap_the_oldest_finished_jobs_go_first() -> None:
    clock = Clock()
    store = InMemoryJobStore(clock)
    running = store.start(ALICE)
    finished = []
    for _ in range(MAX_JOBS + 5):
        clock.now += 1
        job = store.start(uuid.uuid4())
        store.finish(job.id, {})
        finished.append(job)

    store.start(BOB)

    assert store.get(ALICE, running.id) is not None
    assert store.get(finished[0].user_id, finished[0].id) is None
    assert store.get(finished[-1].user_id, finished[-1].id) is not None
