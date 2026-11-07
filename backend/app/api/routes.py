import base64
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.api.dependencies import enforce_rate_limit, get_application_service
from app.api.schemas import ApplicationResponse
from app.core.config import Settings, get_settings
from app.services.application_service import MAX_CV_BYTES, ApplicationRequest, ApplicationService

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post(
    "/applications",
    response_model=ApplicationResponse,
    dependencies=[Depends(enforce_rate_limit)],
)
def create_application(
    cv_file: Annotated[UploadFile, File()],
    job_text: Annotated[str, Form()],
    service: Annotated[ApplicationService, Depends(get_application_service)],
    settings: Annotated[Settings, Depends(get_settings)],
    include_photo: Annotated[bool, Form()] = True,
) -> ApplicationResponse:
    if not settings.applicant_city:
        raise HTTPException(
            status_code=503,
            detail="The server is not configured: applicant details are missing.",
        )
    request = ApplicationRequest(
        cv_filename=cv_file.filename or "",
        cv_content=cv_file.file.read(MAX_CV_BYTES + 1),
        job_text=job_text,
        address=settings.applicant_address,
        city=settings.applicant_city,
        gender=settings.applicant_gender,
        today=date.today(),
        include_photo=include_photo,
    )
    result = service.create(request)
    return ApplicationResponse(
        job_title=result.offer.title,
        company=result.offer.company,
        language=result.offer.language,
        photo_used=result.photo_used,
        cv_pdf_base64=base64.b64encode(result.cv_pdf).decode("ascii"),
        letter_pdf_base64=base64.b64encode(result.letter_pdf).decode("ascii"),
    )
