import base64
import logging
import uuid
from dataclasses import asdict
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.api.account_dependencies import (
    get_profile_service,
    get_quota_service,
    get_saved_cv_service,
)
from app.api.auth_dependencies import CurrentUserId, require_user, require_verified_user
from app.api.dependencies import (
    enforce_fetch_rate_limit,
    enforce_rate_limit,
    enforce_render_rate_limit,
    get_application_service,
    get_job_fetch_service,
    get_job_runner,
    get_render_service,
)
from app.api.schemas import (
    ApplicationResponse,
    JobErrorOut,
    JobOut,
    JobTextResponse,
    JobUrlRequest,
    MatchReportOut,
    MatchScoreOut,
    MissingSkillOut,
    RenderRequestBody,
    RenderResponse,
)
from app.domain.document import MAX_CV_BYTES, InvalidPhotoError
from app.domain.jobs import GenerationJob, JobLimitError
from app.domain.saved_cv import SavedCv
from app.services.application_service import (
    ApplicationRequest,
    ApplicationResult,
    ApplicationService,
)
from app.services.job_fetch_service import JobFetchService
from app.services.job_runner import JobRunner, StageReporter
from app.services.profile_service import ProfileService
from app.services.quota_service import QuotaService
from app.services.render_service import RenderRequest, RenderService
from app.services.saved_cv_service import SavedCvService

logger = logging.getLogger(__name__)

router = APIRouter()


def _encode(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def _encode_optional(data: bytes | None) -> str | None:
    return _encode(data) if data is not None else None


def _decode_photo(value: str | None) -> bytes | None:
    if not value:
        return None
    try:
        return base64.b64decode(value, validate=True)
    except ValueError as exc:
        raise InvalidPhotoError("The photo is not valid base64 data.") from exc


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post(
    "/applications",
    response_model=JobOut,
    status_code=202,
    dependencies=[Depends(require_verified_user), Depends(enforce_rate_limit)],
)
def create_application(
    job_text: Annotated[str, Form()],
    service: Annotated[ApplicationService, Depends(get_application_service)],
    runner: Annotated[JobRunner, Depends(get_job_runner)],
    profiles: Annotated[ProfileService, Depends(get_profile_service)],
    quotas: Annotated[QuotaService, Depends(get_quota_service)],
    saved_cvs: Annotated[SavedCvService, Depends(get_saved_cv_service)],
    user_id: CurrentUserId,
    include_photo: Annotated[bool, Form()] = True,
    include_letter: Annotated[bool, Form()] = True,
    cv_file: Annotated[UploadFile | None, File()] = None,
) -> JobOut:
    """Starts the generation in the background and answers at once with its job.

    The quick checks (profile, saved CV, monthly quota) answer here directly; the AI work
    then runs in the background and the page follows it with GET /applications/jobs/{id}.
    Uses the uploaded file, or the saved CV of the user when no file is sent.
    """
    profile = profiles.require_complete(user_id)
    saved = None
    if cv_file is None:
        saved = saved_cvs.require(user_id)
        cv_filename, cv_content = saved.filename, saved.content
    else:
        cv_filename, cv_content = cv_file.filename or "", cv_file.file.read(MAX_CV_BYTES + 1)
    request = ApplicationRequest(
        cv_filename=cv_filename,
        cv_content=cv_content,
        job_text=job_text,
        address=profile.address,
        city=profile.city,
        gender=profile.gender,
        today=date.today(),
        include_photo=include_photo,
        cv_language=profile.cv_language,
        structured_cv=saved.structured if saved is not None else None,
        include_letter=include_letter,
    )
    reservation = quotas.reserve_application(user_id)

    def work(report: StageReporter) -> dict[str, object]:
        try:
            result = service.create(request, report)
        except Exception:
            # A failed application is not counted: users only use their quota for real documents.
            quotas.release(user_id, reservation)
            raise
        _remember_structure(saved_cvs, user_id, saved, result)
        return _application_response(result).model_dump(mode="json")

    try:
        job = runner.submit(user_id, work)
    except JobLimitError:
        quotas.release(user_id, reservation)
        raise
    return _job_out(job)


@router.get(
    "/applications/jobs/{job_id}",
    response_model=JobOut,
    dependencies=[Depends(require_user)],
)
def get_application_job(
    job_id: uuid.UUID,
    runner: Annotated[JobRunner, Depends(get_job_runner)],
    user_id: CurrentUserId,
) -> JobOut:
    """Where the generation is. Only the user who started it can see it."""
    job = runner.get(user_id, job_id)
    if job is None:
        detail = "This application was not found or has expired. Please create it again."
        raise HTTPException(status_code=404, detail=detail)
    return _job_out(job)


def _remember_structure(
    saved_cvs: SavedCvService,
    user_id: uuid.UUID,
    saved: SavedCv | None,
    result: ApplicationResult,
) -> None:
    """Keeps the CV as read, so the next application skips that step. Never fails the job."""
    if saved is None or saved.structured is not None:
        return
    try:
        saved_cvs.remember_structure(user_id, saved.content, result.structured_cv)
    except Exception:  # noqa: BLE001 - the documents are ready; this is only a speed-up
        logger.warning("Could not keep the structure of the saved CV", exc_info=True)


def _job_out(job: GenerationJob) -> JobOut:
    failure = job.failure
    return JobOut(
        job_id=job.id,
        status=job.status,
        stage=job.stage,
        result=ApplicationResponse.model_validate(job.result) if job.result is not None else None,
        error=JobErrorOut(
            status=failure.status, detail=failure.detail, violations=failure.violations
        )
        if failure is not None
        else None,
    )


def _application_response(result: ApplicationResult) -> ApplicationResponse:
    return ApplicationResponse(
        job_title=result.offer.title,
        company=result.offer.company,
        language=result.offer.language,
        photo_used=result.photo_used,
        cv_pdf_base64=_encode(result.cv_pdf),
        letter_pdf_base64=_encode_optional(result.letter_pdf),
        original_cv=result.original_cv,
        cv=result.cv,
        letter=result.letter,
        photo_base64=_encode(result.photo.data) if result.photo else None,
        report=MatchReportOut(
            matched_skills=result.report.matched_skills,
            missing_skills=[
                MissingSkillOut(name=skill.name, required=skill.required, group=skill.group)
                for skill in result.report.missing_skills
            ],
            changes=result.report.changes,
            score=MatchScoreOut(**asdict(result.report.score)),
        ),
    )


@router.post(
    "/render",
    response_model=RenderResponse,
    dependencies=[Depends(require_user), Depends(enforce_render_rate_limit)],
)
def render_documents(
    body: RenderRequestBody,
    service: Annotated[RenderService, Depends(get_render_service)],
) -> RenderResponse:
    documents = service.render(
        RenderRequest(
            cv=body.cv,
            letter=body.letter,
            language=body.language,
            photo_bytes=_decode_photo(body.photo_base64),
        )
    )
    return RenderResponse(
        cv_pdf_base64=_encode(documents.cv_pdf),
        letter_pdf_base64=_encode_optional(documents.letter_pdf),
    )


@router.post(
    "/job-offers/fetch",
    response_model=JobTextResponse,
    dependencies=[Depends(require_user), Depends(enforce_fetch_rate_limit)],
)
def fetch_job_offer(
    body: JobUrlRequest,
    service: Annotated[JobFetchService, Depends(get_job_fetch_service)],
) -> JobTextResponse:
    fetched = service.fetch_text(body.url)
    return JobTextResponse(
        text=fetched.text,
        truncated=fetched.truncated,
        source_url=fetched.source_url,
    )
