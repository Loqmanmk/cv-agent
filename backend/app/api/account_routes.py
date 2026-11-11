from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.account_dependencies import get_profile_service, get_quota_service
from app.api.account_schemas import ProfileBody, ProfileOut, UsageOut
from app.api.auth_dependencies import CurrentUserId
from app.domain.profile import Profile
from app.services.profile_service import ProfileService
from app.services.quota_service import QuotaService

router = APIRouter(prefix="/me")

Profiles = Annotated[ProfileService, Depends(get_profile_service)]
Quotas = Annotated[QuotaService, Depends(get_quota_service)]


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


@router.get("/usage", response_model=UsageOut)
def read_usage(user_id: CurrentUserId, quotas: Quotas) -> UsageOut:
    summary = quotas.summary(user_id)
    return UsageOut(
        plan=summary.plan, used=summary.used, limit=summary.limit, resets_at=summary.resets_at
    )
