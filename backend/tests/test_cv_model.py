import pytest
from pydantic import ValidationError

from app.domain.cv import CV, Header


def make_header() -> Header:
    return Header(
        name="Jane Doe",
        headline="Software Engineer",
        phone="+00 000 000 000",
        email="jane@example.com",
    )


def test_minimal_cv_is_valid() -> None:
    cv = CV(header=make_header(), profile="Backend developer.")

    assert cv.header.name == "Jane Doe"
    assert cv.experiences == []


def test_missing_required_field_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Header(name="Jane Doe", headline="Software Engineer")  # type: ignore[call-arg]


def test_unknown_field_is_rejected() -> None:
    with pytest.raises(ValidationError):
        CV(
            header=make_header(),
            profile="Backend developer.",
            salary_expectation="100k",  # type: ignore[call-arg]
        )


def test_default_lists_are_not_shared_between_instances() -> None:
    first = CV(header=make_header(), profile="A")
    second = CV(header=make_header(), profile="B")

    first.interests.append("Chess")

    assert second.interests == []
