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
    colon: str = " :"


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

GERMAN_LABELS = CVLabels(
    lang="de",
    direction="ltr",
    profile="Profil",
    experiences="Berufserfahrung",
    projects="Projekte",
    education="Ausbildung",
    skills="Technische Kenntnisse",
    certifications="Zertifikate",
    languages="Sprachen",
    interests="Interessen",
    phone="Telefon",
    email="E-Mail",
    location="Wohnort",
    colon=":",
)

ENGLISH_LABELS = CVLabels(
    lang="en",
    direction="ltr",
    profile="Profile",
    experiences="Professional experience",
    projects="Projects",
    education="Education",
    skills="Technical skills",
    certifications="Certifications",
    languages="Languages",
    interests="Interests",
    phone="Phone",
    email="Email",
    location="Location",
    colon=":",
)

ARABIC_LABELS = CVLabels(
    lang="ar",
    direction="rtl",
    profile="الملف الشخصي",
    experiences="الخبرات المهنية",
    projects="المشاريع",
    education="التعليم",
    skills="المهارات التقنية",
    certifications="الشهادات",
    languages="اللغات",
    interests="الاهتمامات",
    phone="الهاتف",
    email="البريد الإلكتروني",
    location="مكان الإقامة",
    colon=":",
)

LABELS_BY_LANGUAGE: dict[str, CVLabels] = {
    "fr": FRENCH_LABELS,
    "de": GERMAN_LABELS,
    "en": ENGLISH_LABELS,
    "ar": ARABIC_LABELS,
}
