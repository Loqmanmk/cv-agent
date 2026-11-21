from typing import Literal

from pydantic import Field

from app.domain.cv import DomainModel

OfferLanguage = Literal["fr", "en", "de", "ar", "other"]
ContractType = Literal["internship", "full_time", "part_time", "freelance", "unknown"]


class SkillField(DomainModel):
    """The heading of the CV skills section a skill of the offer belongs to."""

    skill: str
    field: str


class JobOffer(DomainModel):
    title: str
    company: str = ""
    company_address: str = ""
    contact_person: str = ""
    reference: str = ""
    location: str = ""
    sector: str = ""
    company_summary: str = ""
    language: OfferLanguage
    contract_type: ContractType
    required_skills: list[str] = Field(default_factory=list)
    nice_to_have_skills: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    missions: list[str] = Field(default_factory=list)
    skill_fields: list[SkillField] = Field(default_factory=list)
