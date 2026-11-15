import base64
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, UploadFile

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
    get_render_service,
)
from app.api.schemas import (
    ApplicationResponse,
    JobTextResponse,
    JobUrlRequest,
    RenderRequestBody,
    RenderResponse,
)
from app.domain.document import MAX_CV_BYTES, InvalidPhotoError
from app.services.application_service import ApplicationRequest, ApplicationService
from app.services.job_fetch_service import JobFetchService
from app.services.profile_service import ProfileService
from app.services.quota_service import QuotaService
from app.services.render_service import RenderRequest, RenderService
from app.services.saved_cv_service import SavedCvService

router = APIRouter()


def _encode(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


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
    response_model=ApplicationResponse,
    dependencies=[Depends(require_verified_user), Depends(enforce_rate_limit)],
)
def create_application(
    job_text: Annotated[str, Form()],
    service: Annotated[ApplicationService, Depends(get_application_service)],
    profiles: Annotated[ProfileService, Depends(get_profile_service)],
    quotas: Annotated[QuotaService, Depends(get_quota_service)],
    saved_cvs: Annotated[SavedCvService, Depends(get_saved_cv_service)],
    user_id: CurrentUserId,
    include_photo: Annotated[bool, Form()] = True,
    cv_file: Annotated[UploadFile | None, File()] = None,
) -> ApplicationResponse:
    """Uses the uploaded file, or the saved CV of the user when no file is sent."""
    profile = profiles.require_complete(user_id)
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
    )
    reservation = quotas.reserve_application(user_id)
    try:
        result = service.create(request)
    except Exception:
        # A failed application is not counted: users only use their quota for real documents.
        quotas.release(user_id, reservation)
        raise
    return ApplicationResponse(
        job_title=result.offer.title,
        company=result.offer.company,
        language=result.offer.language,
        photo_used=result.photo_used,
        cv_pdf_base64=_encode(result.cv_pdf),
        letter_pdf_base64=_encode(result.letter_pdf),
        original_cv=result.original_cv,
        cv=result.cv,
        letter=result.letter,
        photo_base64=_encode(result.photo.data) if result.photo else None,
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
        letter_pdf_base64=_encode(documents.letter_pdf),
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
