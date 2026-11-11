from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.domain.letter import Gender
from app.domain.plans import Plan
from app.domain.profile import CvLanguage
from app.services.profile_service import MAX_ADDRESS_CHARS, MAX_CITY_CHARS


class ProfileBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    address: str = Field(default="", max_length=MAX_ADDRESS_CHARS)
    city: str = Field(default="", max_length=MAX_CITY_CHARS)
    gender: Gender
    cv_language: CvLanguage


class ProfileOut(BaseModel):
    address: str
    city: str
    gender: Gender
    cv_language: CvLanguage
    is_complete: bool


class UsageOut(BaseModel):
    plan: Plan
    used: int
    limit: int
    resets_at: datetime
