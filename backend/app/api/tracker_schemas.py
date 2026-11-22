from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.domain.cv import CV
from app.domain.job import OfferLanguage
from app.domain.letter import CoverLetter
from app.domain.tracker import ApplicationStatus


class SaveApplicationBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_title: str = Field(min_length=1, max_length=200)
    company: str = Field(default="", max_length=200)
    language: OfferLanguage
    source_url: str = Field(default="", max_length=2000)
    status: ApplicationStatus = "saved"
    cv: CV
    letter: CoverLetter | None = None
    photo_base64: str | None = None


class UpdateApplicationBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: ApplicationStatus | None = None
    notes: str | None = Field(default=None, max_length=5000)


class ApplicationSummaryOut(BaseModel):
    id: int
    created_at: datetime
    job_title: str
    company: str
    language: str
    source_url: str
    status: ApplicationStatus
    notes: str
    has_letter: bool
