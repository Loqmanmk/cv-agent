from typing import Annotated

from fastapi import APIRouter, Depends, File, Response, UploadFile

from app.api.account_dependencies import (
    get_profile_service,
    get_quota_service,
    get_saved_cv_service,
)
from app.api.account_schemas import ProfileBody, ProfileOut, SavedCvOut, UsageOut
from app.api.auth_dependencies import CurrentUserId
from app.api.dependencies import enforce_render_rate_limit
from app.domain.document import MAX_CV_BYTES
from app.domain.profile import Profile
from app.domain.saved_cv import SavedCvInfo
from app.services.profile_service import ProfileService
from app.services.quota_service import QuotaService
from app.services.saved_cv_service import SavedCvService

router = APIRouter(prefix="/me")

Profiles = Annotated[ProfileService, Depends(get_profile_service)]
Quotas = Annotated[QuotaService, Depends(get_quota_service)]
SavedCvs = Annotated[SavedCvService, Depends(get_saved_cv_service)]


def _profile_out(profile: Profile) -> ProfileOut:
    return ProfileOut(
        address=profile.address,
        city=profile.city,
        gender=profile.gender,
        cv_language=profile.cv_language,
        is_complete=profile.is_complete,
    )


@router.get("/profile", response_model=ProfileOut)
def read_profile(user_id: CurrentUserId, profiles: Profiles) -> ProfileOut:
    return _profile_out(profiles.get_profile(user_id))


@router.put("/profile", response_model=ProfileOut)
def save_profile(body: ProfileBody, user_id: CurrentUserId, profiles: Profiles) -> ProfileOut:
    saved = profiles.update_profile(user_id, body.address, body.city, body.gender, body.cv_language)
    return _profile_out(saved)


def _saved_cv_out(info: SavedCvInfo) -> SavedCvOut:
    return SavedCvOut(filename=info.filename, size=info.size, uploaded_at=info.uploaded_at)


@router.get("/cv", response_model=SavedCvOut | None)
def read_saved_cv(user_id: CurrentUserId, saved_cvs: SavedCvs) -> SavedCvOut | None:
    """The saved CV of the user (name, size, date), or null when there is none."""
    info = saved_cvs.info(user_id)
    return None if info is None else _saved_cv_out(info)


@router.put("/cv", response_model=SavedCvOut, dependencies=[Depends(enforce_render_rate_limit)])
def save_cv(
    cv_file: Annotated[UploadFile, File()], user_id: CurrentUserId, saved_cvs: SavedCvs
) -> SavedCvOut:
    content = cv_file.file.read(MAX_CV_BYTES + 1)
    return _saved_cv_out(saved_cvs.save(user_id, cv_file.filename or "", content))


@router.delete("/cv", status_code=204)
def delete_saved_cv(user_id: CurrentUserId, saved_cvs: SavedCvs) -> Response:
    saved_cvs.delete(user_id)
    return Response(status_code=204)


@router.get("/usage", response_model=UsageOut)
def read_usage(user_id: CurrentUserId, quotas: Quotas) -> UsageOut:
    summary = quotas.summary(user_id)
    return UsageOut(
        plan=summary.plan, used=summary.used, limit=summary.limit, resets_at=summary.resets_at
    )
