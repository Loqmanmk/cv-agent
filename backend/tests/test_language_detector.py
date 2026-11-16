import pytest

from app.services.language_detector import detect_language

FRENCH = (
    "Élève-ingénieur en 5ème année, spécialisé en intelligence artificielle. Expérience en "
    "développement web avec React et Laravel, et mise en place de pipelines CI/CD pour une "
    "plateforme de suivi des patients dans un hôpital."
)
ENGLISH = (
    "Fifth-year engineering student specialised in artificial intelligence. Experience in "
    "web development with React and Laravel, and built CI/CD pipelines for a patient "
    "follow-up platform at a hospital."
)
GERMAN = (
    "Ingenieurstudent im fünften Jahr mit Schwerpunkt auf künstlicher Intelligenz. Erfahrung "
    "in der Webentwicklung mit React und Laravel sowie Aufbau von CI/CD-Pipelines für eine "
    "Plattform zur Betreuung der Patienten in einem Krankenhaus."
)
ARABIC = "طالب هندسة في السنة الخامسة متخصص في الذكاء الاصطناعي، خبرة في تطوير الويب باستخدام React"


@pytest.mark.parametrize(
    ("text", "language"),
    [(FRENCH, "fr"), (ENGLISH, "en"), (GERMAN, "de"), (ARABIC, "ar")],
)
def test_the_language_of_a_cv_is_found(text: str, language: str) -> None:
    assert detect_language(text) == language


@pytest.mark.parametrize(
    "text",
    ["", "Python, Docker, Kubernetes, React, FastAPI", "Loqman MAKOURI +212 600 000 000"],
)
def test_a_text_without_enough_words_gives_no_answer(text: str) -> None:
    assert detect_language(text) is None


def test_a_cv_mixing_two_languages_evenly_gives_no_answer() -> None:
    mixed = "le la et du pour avec dans " + "the and of to for with on"

    assert detect_language(mixed) is None
