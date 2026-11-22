from pydantic import BaseModel, ConfigDict, Field

from app.domain.cv import CV
from app.domain.job import OfferLanguage
from app.domain.letter import CoverLetter


class MissingSkillOut(BaseModel):
    name: str
    required: bool
    group: str | None


class MatchScoreOut(BaseModel):
    value: int | None
    required_matched: int
    required_total: int
    nice_matched: int
    nice_total: int


class MatchReportOut(BaseModel):
    matched_skills: list[str]
    missing_skills: list[MissingSkillOut]
    changes: list[str]
    score: MatchScoreOut


class ApplicationResponse(BaseModel):
    job_title: str
    company: str
    language: str
    photo_used: bool
    cv_pdf_base64: str
    letter_pdf_base64: str | None
    original_cv: CV
    cv: CV
    letter: CoverLetter | None
    photo_base64: str | None
    report: MatchReportOut


class RenderRequestBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cv: CV
    letter: CoverLetter | None = None
    language: OfferLanguage
    photo_base64: str | None = None


class RenderResponse(BaseModel):
    cv_pdf_base64: str
    letter_pdf_base64: str | None


class JobUrlRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: str = Field(min_length=1, max_length=2000)


class JobTextResponse(BaseModel):
    text: str
    truncated: bool
    source_url: str
