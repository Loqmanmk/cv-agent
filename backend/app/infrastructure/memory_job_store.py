import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import replace

from app.domain.jobs import GenerationJob, JobFailure, JobLimitError, JobStore, Stage

# A finished job is kept long enough for the page to fetch it, then forgotten: it holds PDFs.
KEEP_FINISHED_SECONDS = 15 * 60.0
# A job that never ends (a crashed worker) stops blocking its user after this long.
MAX_RUNNING_SECONDS = 30 * 60.0
MAX_JOBS = 500


class InMemoryJobStore(JobStore):
    """Jobs in the memory of this process, safe to use from several threads.

    Enough for one server process. Several processes would need a shared store (Redis or the
    database) behind the same JobStore contract.
    """

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._lock = threading.Lock()
        self._jobs: dict[uuid.UUID, GenerationJob] = {}
        self._touched: dict[uuid.UUID, float] = {}

    def start(self, user_id: uuid.UUID) -> GenerationJob:
        with self._lock:
            self._forget_old()
            if any(
                job.user_id == user_id and job.status == "running" for job in self._jobs.values()
            ):
                raise JobLimitError
            job = GenerationJob(id=uuid.uuid4(), user_id=user_id, status="running", stage="queued")
            self._save(job)
            return job

    def set_stage(self, job_id: uuid.UUID, stage: Stage) -> None:
        self._update(job_id, lambda job: replace(job, stage=stage))

    def finish(self, job_id: uuid.UUID, result: dict[str, object]) -> None:
        self._update(
            job_id, lambda job: replace(job, status="done", stage="finished", result=result)
        )

    def fail(self, job_id: uuid.UUID, failure: JobFailure) -> None:
        self._update(job_id, lambda job: replace(job, status="failed", failure=failure))

    def get(self, user_id: uuid.UUID, job_id: uuid.UUID) -> GenerationJob | None:
        with self._lock:
            self._forget_old()
            job = self._jobs.get(job_id)
            return job if job is not None and job.user_id == user_id else None

    def _update(self, job_id: uuid.UUID, change: Callable[[GenerationJob], GenerationJob]) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is not None:
                self._save(change(job))

    def _save(self, job: GenerationJob) -> None:
        self._jobs[job.id] = job
        self._touched[job.id] = self._clock()

    def _forget_old(self) -> None:
        now = self._clock()
        for job_id, job in list(self._jobs.items()):
            limit = MAX_RUNNING_SECONDS if job.status == "running" else KEEP_FINISHED_SECONDS
            if now - self._touched[job_id] > limit:
                self._drop(job_id)
        # Past the cap, the oldest finished jobs go first; running jobs are never dropped.
        finished = sorted(
            (job_id for job_id, job in self._jobs.items() if job.status != "running"),
            key=self._touched.__getitem__,
        )
        for job_id in finished[: max(0, len(self._jobs) - MAX_JOBS)]:
            self._drop(job_id)

    def _drop(self, job_id: uuid.UUID) -> None:
        del self._jobs[job_id]
        del self._touched[job_id]
