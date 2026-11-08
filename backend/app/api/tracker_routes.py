import base64
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Response

from app.api.dependencies import enforce_render_rate_limit
from app.api.tracker_dependencies import get_tracker_service
from app.api.tracker_schemas import (
    ApplicationSummaryOut,
    SaveApplicationBody,
    UpdateApplicationBody,
)
from app.domain.document import InvalidPhotoError
from app.domain.tracker import ApplicationSummary
from app.services.tracker_service import SaveRequest, TrackerService, pdf_filename

router = APIRouter(prefix="/tracker")

ApplicationId = Annotated[int, Path(ge=1)]
Service = Annotated[TrackerService, Depends(get_tracker_service)]


def _decode_photo(value: str | None) -> bytes | None:
    if not value:
        return None
    try:
        return base64.b64decode(value, validate=True)
    except ValueError as exc:
        raise InvalidPhotoError("The photo is not valid base64 data.") from exc


def _out(summary: ApplicationSummary) -> ApplicationSummaryOut:
    return ApplicationSummaryOut(
        id=summary.id,
        created_at=summary.created_at,
        job_title=summary.job_title,
        company=summary.company,
        language=summary.language,
        source_url=summary.source_url,
        status=summary.status,
        notes=summary.notes,
    )


def _pdf(content: bytes, filename: str) -> Response:
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return Response(content=content, media_type="application/pdf", headers=headers)


@router.post(
    "/applications",
    status_code=201,
    response_model=ApplicationSummaryOut,
    dependencies=[Depends(enforce_render_rate_limit)],
)
def save_application(body: SaveApplicationBody, service: Service) -> ApplicationSummaryOut:
    summary = service.save(
        SaveRequest(
            job_title=body.job_title,
            company=body.company,
            language=body.language,
            source_url=body.source_url,
            status=body.status,
            cv=body.cv,
            letter=body.letter,
            photo_bytes=_decode_photo(body.photo_base64),
        )
    )
    return _out(summary)


@router.get("/applications", response_model=list[ApplicationSummaryOut])
def list_applications(service: Service) -> list[ApplicationSummaryOut]:
    return [_out(summary) for summary in service.list_applications()]


@router.get("/applications/{application_id}", response_model=ApplicationSummaryOut)
def get_application(application_id: ApplicationId, service: Service) -> ApplicationSummaryOut:
    return _out(service.get(application_id))


@router.patch("/applications/{application_id}", response_model=ApplicationSummaryOut)
def update_application(
    application_id: ApplicationId,
    body: UpdateApplicationBody,
    service: Service,
) -> ApplicationSummaryOut:
    return _out(service.update(application_id, body.status, body.notes))


@router.delete("/applications/{application_id}", status_code=204)
def delete_application(application_id: ApplicationId, service: Service) -> Response:
    service.delete(application_id)
    return Response(status_code=204)


@router.get("/applications/{application_id}/cv.pdf")
def download_cv(application_id: ApplicationId, service: Service) -> Response:
    summary = service.get(application_id)
    return _pdf(service.files(application_id).cv_pdf, pdf_filename("cv", summary.company))


@router.get("/applications/{application_id}/letter.pdf")
def download_letter(application_id: ApplicationId, service: Service) -> Response:
    summary = service.get(application_id)
    return _pdf(service.files(application_id).letter_pdf, pdf_filename("letter", summary.company))
