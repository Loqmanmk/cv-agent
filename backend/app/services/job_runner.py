import logging
import uuid
from collections.abc import Callable
from concurrent.futures import Executor

from app.domain.jobs import GenerationJob, JobFailure, JobStore, Stage

logger = logging.getLogger(__name__)

StageReporter = Callable[[Stage], None]
Work = Callable[[StageReporter], dict[str, object]]
Describe = Callable[[Exception], JobFailure]


class JobRunner:
    """Runs a generation in the background and records its stages, result or failure.

    The work receives a reporter to tell which stage it is in; it returns the answer the
    page will receive. Any error is turned into a failure with the same status and message
    the page would have had from a direct answer.
    """

    def __init__(self, store: JobStore, executor: Executor, describe: Describe) -> None:
        self._store = store
        self._executor = executor
        self._describe = describe

    def submit(self, user_id: uuid.UUID, work: Work) -> GenerationJob:
        job = self._store.start(user_id)
        self._executor.submit(self._run, job.id, work)
        return job

    def get(self, user_id: uuid.UUID, job_id: uuid.UUID) -> GenerationJob | None:
        return self._store.get(user_id, job_id)

    def _run(self, job_id: uuid.UUID, work: Work) -> None:
        try:
            result = work(lambda stage: self._store.set_stage(job_id, stage))
        except Exception as exc:  # noqa: BLE001 - every failure must end the job, not the thread
            self._store.fail(job_id, self._describe(exc))
            return
        self._store.finish(job_id, result)
