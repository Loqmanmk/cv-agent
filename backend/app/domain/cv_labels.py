from dataclasses import dataclass


@dataclass(frozen=True)
class CVLabels:
    """Fixed section titles of a CV, in one language."""

    lang: str
    direction: str
    profile: str
    experiences: str
    projects: str
    education: str
    skills: str
    certifications: str
    languages: str
    interests: str
    phone: str
    email: str
    location: str


FRENCH_LABELS = CVLabels(
    lang="fr",
    direction="ltr",
    profile="Profil",
    experiences="Expériences professionnelles",
    projects="Projets",
    education="Formations",
    skills="Compétences techniques",
    certifications="Certifications",
    languages="Langues",
    interests="Centres d’intérêt",
    phone="Téléphone",
    email="Email",
    location="Localisation",
)
