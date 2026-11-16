from app.domain.cv import CV, Education, Project
from app.services.translation_guard import TranslationGuard
from tests.test_tailoring_guard import make_cv


def german(cv: CV) -> CV:
    return cv.model_copy(
        update={
            "header": cv.header.model_copy(
                update={
                    "headline": "Ingenieurstudentin",
                    "target_line": "Suche ein 6-monatiges Praktikum",
                    "location": "Marokko",
                }
            ),
            "profile": "Studentin im fünften Jahr mit 3 Praktika in der Webentwicklung.",
            "experiences": [
                cv.experiences[0].model_copy(
                    update={
                        "title": "Mobile Entwicklerin",
                        "bullets": [
                            "Android-App mit React Native entwickelt",
                            "REST-API integriert",
                        ],
                    }
                )
            ],
            "projects": [
                cv.projects[0].model_copy(
                    update={
                        "subtitle": "ML-Projekt",
                        "bullets": ["Modell mit Scikit-learn trainiert"],
                    }
                ),
                cv.projects[1].model_copy(
                    update={"bullets": ["Microservices mit Spring Boot aufgebaut"]}
                ),
            ],
            "education": [cv.education[0].model_copy(update={"degree": "Ingenieurstudium"})],
            "skills": [
                cv.skills[0].model_copy(update={"category": "Backend"}),
                cv.skills[1].model_copy(update={"category": "Frontend"}),
            ],
            "languages": [
                cv.languages[0].model_copy(update={"name": "Französisch", "level": "Fließend"})
            ],
            "interests": ["Schach"],
        }
    )


def arabic(cv: CV) -> CV:
    base = german(cv)
    return base.model_copy(
        update={
            "header": base.header.model_copy(
                update={"headline": "طالبة هندسة", "target_line": "أبحث عن تدريب مدته 6 أشهر"}
            ),
            "profile": "طالبة في السنة الخامسة لديها 3 تدريبات في تطوير الويب.",
            "experiences": [
                base.experiences[0].model_copy(
                    update={
                        "bullets": [
                            "تطوير تطبيق أندرويد باستخدام React Native",
                            "دمج واجهة REST API",
                        ]
                    }
                )
            ],
            "projects": [
                base.projects[0].model_copy(
                    update={"bullets": ["نموذج تعلم آلي باستخدام Scikit-learn"]}
                ),
                base.projects[1].model_copy(
                    update={"bullets": ["بنية خدمات مصغرة باستخدام Spring Boot"]}
                ),
            ],
        }
    )


def violations_of(translated: CV, language: str = "de", original: CV | None = None) -> list[str]:
    return TranslationGuard().violations(original or make_cv(), translated, language)


def test_a_faithful_german_translation_has_no_violations() -> None:
    assert violations_of(german(make_cv())) == []


def test_a_faithful_arabic_translation_has_no_violations() -> None:
    assert violations_of(arabic(make_cv()), "ar") == []


def test_a_changed_contact_detail_is_rejected() -> None:
    cv = german(make_cv())
    header = cv.header.model_copy(update={"email": "other@example.com"})

    assert violations_of(cv.model_copy(update={"header": header})) == ["header.email was changed"]


def test_a_changed_company_is_rejected() -> None:
    cv = german(make_cv())
    job = cv.experiences[0].model_copy(update={"company": "Globex"})

    found = violations_of(cv.model_copy(update={"experiences": [job]}))

    assert found == ["experience 1: company or city changed"]


def test_a_changed_school_is_rejected() -> None:
    cv = german(make_cv())
    study = cv.education[0].model_copy(update={"school": "Other School"})

    found = violations_of(cv.model_copy(update={"education": [study]}))

    assert found == ["education 1: school or city changed"]


def test_changed_skill_items_are_rejected() -> None:
    cv = german(make_cv())
    group = cv.skills[0].model_copy(update={"items": ["Python", "Flask"]})

    found = violations_of(cv.model_copy(update={"skills": [group, cv.skills[1]]}))

    assert found == ["skills group 1: the items were changed"]


def test_a_changed_certification_is_rejected() -> None:
    cv = german(make_cv())
    certification = cv.certifications[0].model_copy(update={"name": "Cert B"})

    found = violations_of(cv.model_copy(update={"certifications": [certification]}))

    assert found == ["certification 1: name or issuer changed"]


def titled_projects() -> tuple[CV, CV]:
    original = make_cv()
    original = original.model_copy(
        update={
            "projects": [
                Project(title="PathFinder - ML project", bullets=["Model with Scikit-learn"]),
                original.projects[1],
            ]
        }
    )
    translated = german(make_cv())
    return original, translated


def test_the_project_name_stays_and_the_rest_of_the_title_is_translated() -> None:
    original, translated = titled_projects()
    projects = [
        Project(title="PathFinder - ML-Projekt", bullets=["Modell mit Scikit-learn trainiert"]),
        translated.projects[1],
    ]

    found = violations_of(translated.model_copy(update={"projects": projects}), original=original)

    assert found == []


def test_a_changed_project_name_is_rejected() -> None:
    original, translated = titled_projects()
    projects = [
        Project(title="Pfadfinder - ML-Projekt", bullets=["Modell mit Scikit-learn trainiert"]),
        translated.projects[1],
    ]

    found = violations_of(translated.model_copy(update={"projects": projects}), original=original)

    assert found == ["project 1: the project name 'PathFinder' was changed"]


def test_an_added_number_is_rejected() -> None:
    cv = german(make_cv()).model_copy(
        update={"profile": "Studentin im fünften Jahr mit 5 Praktika in der Webentwicklung."}
    )

    assert violations_of(cv) == ["profile: number '5' was added"]


def test_a_lost_year_is_rejected() -> None:
    cv = german(make_cv())
    job = cv.experiences[0].model_copy(update={"start": "August"})

    found = violations_of(cv.model_copy(update={"experiences": [job]}))

    assert found == ["experience 1 start: number '2026' was lost"]


def test_a_short_number_may_disappear_when_it_becomes_a_word() -> None:
    cv = german(make_cv()).model_copy(
        update={"profile": "Studentin im fünften Jahr mit Praktika in der Webentwicklung."}
    )

    assert violations_of(cv) == []


def test_removed_text_is_rejected() -> None:
    cv = german(make_cv())
    job = cv.experiences[0].model_copy(update={"bullets": ["", "REST-API integriert"]})

    found = violations_of(cv.model_copy(update={"experiences": [job]}))

    assert found == ["experience 1 bullet 1: the text was removed"]


def test_text_added_where_there_was_none_is_rejected() -> None:
    cv = german(make_cv())
    study: Education = cv.education[0].model_copy(update={"note": "Mit Auszeichnung"})

    found = violations_of(cv.model_copy(update={"education": [study]}))

    assert found == ["education 1 note: text was added where there was none"]


def test_a_changed_number_of_entries_is_rejected() -> None:
    found = violations_of(german(make_cv()).model_copy(update={"experiences": []}))

    assert found == ["the number of experiences changed"]


def test_a_changed_number_of_bullets_is_rejected() -> None:
    cv = german(make_cv())
    job = cv.experiences[0].model_copy(update={"bullets": ["REST-API integriert"]})

    found = violations_of(cv.model_copy(update={"experiences": [job]}))

    assert found == ["experience 1: the number of bullets changed"]


def test_an_untranslated_profile_is_rejected() -> None:
    cv = german(make_cv()).model_copy(update={"profile": make_cv().profile})

    assert violations_of(cv) == ["profile was not translated"]


def test_an_unchanged_cv_is_rejected_as_not_translated() -> None:
    found = violations_of(make_cv())

    assert "profile was not translated" in found
    assert "most bullets were not translated" in found


def test_a_headline_that_is_the_same_in_both_languages_is_accepted() -> None:
    original = make_cv().model_copy(
        update={"header": make_cv().header.model_copy(update={"headline": "Data Scientist"})}
    )
    translated = german(make_cv())
    translated = translated.model_copy(
        update={"header": translated.header.model_copy(update={"headline": "Data Scientist"})}
    )

    assert violations_of(translated, original=original) == []


def test_text_already_in_the_target_language_counts_as_translated() -> None:
    english = (
        "Fifth-year engineering student with a strong interest in data and the cloud, "
        "looking for an internship to build reliable systems with my team."
    )
    original = make_cv().model_copy(update={"profile": english})
    translated = german(make_cv()).model_copy(update={"profile": english})

    assert violations_of(translated, "en", original) == []


def test_arabic_must_contain_arabic_letters() -> None:
    found = violations_of(german(make_cv()), "ar")

    assert "headline was not translated" in found
    assert "most bullets were not translated" in found
