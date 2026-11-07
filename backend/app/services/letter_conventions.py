from dataclasses import dataclass

from app.domain.letter import Gender


class UnsupportedLetterLanguageError(Exception):
    """Raised when no letter conventions exist for the offer's language."""


@dataclass(frozen=True)
class LetterConventions:
    """Fixed wording and formats of a cover letter in one language."""

    language_name: str
    greeting: str
    subject: str
    subject_with_reference: str
    place_date: str
    months: tuple[str, ...]
    closing: dict[Gender, str]
    first_day: str = ""
    overclaims: tuple[str, ...] = ()


def _french_closing(adjective: str) -> str:
    return (
        f"Je serai {adjective} de pouvoir échanger avec vous de vive voix dans le cadre "
        "d’un entretien. En attendant, je reste à votre disposition pour toute information "
        "complémentaire et vous prie d’agréer, Madame, Monsieur, l’expression de mes "
        "salutations distinguées."
    )


FRENCH = LetterConventions(
    language_name="French",
    greeting="Madame, Monsieur,",
    subject="Objet : Candidature pour le poste de {title}",
    subject_with_reference="Objet : Candidature pour le poste de {title} - {reference}",
    place_date="Fait à {city}, le {day} {month} {year}",
    months=(
        "janvier",
        "février",
        "mars",
        "avril",
        "mai",
        "juin",
        "juillet",
        "août",
        "septembre",
        "octobre",
        "novembre",
        "décembre",
    ),
    closing={"m": _french_closing("heureux"), "f": _french_closing("heureuse")},
    first_day="1er",
    overclaims=("expertise", "expert", "experte", "maîtrise parfaite"),
)

_GERMAN_CLOSING = (
    "Über die Einladung zu einem persönlichen Gespräch würde ich mich sehr freuen. "
    "Für weitere Informationen stehe ich Ihnen gerne zur Verfügung.\n\n"
    "Mit freundlichen Grüßen"
)

GERMAN = LetterConventions(
    language_name="German",
    greeting="Sehr geehrte Damen und Herren,",
    subject="Bewerbung als {title}",
    subject_with_reference="Bewerbung als {title} - {reference}",
    place_date="{city}, {day}. {month} {year}",
    months=(
        "Januar",
        "Februar",
        "März",
        "April",
        "Mai",
        "Juni",
        "Juli",
        "August",
        "September",
        "Oktober",
        "November",
        "Dezember",
    ),
    closing={"m": _GERMAN_CLOSING, "f": _GERMAN_CLOSING},
    overclaims=("Experte", "Expertin", "Expertise", "Meister", "Meisterin"),
)

_ENGLISH_CLOSING = (
    "I would welcome the opportunity to discuss my application with you in an interview, "
    "and I am happy to provide any further information you may need.\n\n"
    "Yours sincerely,"
)

ENGLISH = LetterConventions(
    language_name="English",
    greeting="Dear Hiring Manager,",
    subject="Application for the position of {title}",
    subject_with_reference="Application for the position of {title} - {reference}",
    place_date="{city}, {day} {month} {year}",
    months=(
        "January",
        "February",
        "March",
        "April",
        "May",
        "June",
        "July",
        "August",
        "September",
        "October",
        "November",
        "December",
    ),
    closing={"m": _ENGLISH_CLOSING, "f": _ENGLISH_CLOSING},
    overclaims=("expert", "expertise", "mastery"),
)

_ARABIC_CLOSING = (
    "يسعدني أن تتاح لي فرصة مقابلتكم لمناقشة طلبي، "
    "وأنا رهن إشارتكم لتقديم أي معلومات إضافية.\n\n"
    "وتفضلوا بقبول فائق الاحترام والتقدير،"
)

ARABIC = LetterConventions(
    language_name="Arabic (Modern Standard Arabic)",
    greeting="تحية طيبة وبعد،",
    subject="الموضوع: الترشح لمنصب {title}",
    subject_with_reference="الموضوع: الترشح لمنصب {title} - {reference}",
    place_date="{city}، في {day} {month} {year}",
    months=(
        "يناير",
        "فبراير",
        "مارس",
        "أبريل",
        "مايو",
        "يونيو",
        "يوليو",
        "أغسطس",
        "سبتمبر",
        "أكتوبر",
        "نوفمبر",
        "ديسمبر",
    ),
    closing={"m": _ARABIC_CLOSING, "f": _ARABIC_CLOSING},
    overclaims=("خبير", "خبيرة", "متقن", "إتقان تام"),
)

_BY_LANGUAGE: dict[str, LetterConventions] = {
    "fr": FRENCH,
    "de": GERMAN,
    "en": ENGLISH,
    "ar": ARABIC,
}


def conventions_for(language: str) -> LetterConventions:
    try:
        return _BY_LANGUAGE[language]
    except KeyError:
        message = f"No letter conventions for language '{language}' yet."
        raise UnsupportedLetterLanguageError(message) from None
