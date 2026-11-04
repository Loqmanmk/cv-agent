from pydantic import BaseModel, ConfigDict, Field


class DomainModel(BaseModel):
    """Base for every domain model: unknown fields are rejected."""

    model_config = ConfigDict(extra="forbid")


class Header(DomainModel):
    name: str
    headline: str
    target_line: str = ""
    phone: str
    email: str
    linkedin: str = ""
    github: str = ""
    location: str = ""


class Experience(DomainModel):
    title: str
    company: str
    city: str = ""
    start: str
    end: str
    bullets: list[str] = Field(default_factory=list)


class Project(DomainModel):
    title: str
    subtitle: str = ""
    bullets: list[str] = Field(default_factory=list)


class Education(DomainModel):
    degree: str
    school: str
    city: str = ""
    start: str
    end: str
    note: str = ""


class SkillGroup(DomainModel):
    category: str
    items: list[str] = Field(default_factory=list)


class Certification(DomainModel):
    name: str
    issuer: str = ""
    status: str = ""


class Language(DomainModel):
    name: str
    level: str


class CV(DomainModel):
    header: Header
    profile: str
    experiences: list[Experience] = Field(default_factory=list)
    projects: list[Project] = Field(default_factory=list)
    education: list[Education] = Field(default_factory=list)
    skills: list[SkillGroup] = Field(default_factory=list)
    certifications: list[Certification] = Field(default_factory=list)
    languages: list[Language] = Field(default_factory=list)
    interests: list[str] = Field(default_factory=list)
