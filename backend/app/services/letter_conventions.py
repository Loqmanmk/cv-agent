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

_BY_LANGUAGE: dict[str, LetterConventions] = {"fr": FRENCH}


def conventions_for(language: str) -> LetterConventions:
    try:
        return _BY_LANGUAGE[language]
    except KeyError:
        message = f"No letter conventions for language '{language}' yet."
        raise UnsupportedLetterLanguageError(message) from None
