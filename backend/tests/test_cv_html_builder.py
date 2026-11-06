import base64

import pytest

from app.domain.cv import CV
from app.domain.cv_labels import FRENCH_LABELS
from app.domain.document import ExtractedImage
from app.infrastructure.cv_html_builder import CVHtmlBuilder, UnsupportedPhotoError
from tests.test_tailoring_guard import make_cv

PHOTO = ExtractedImage(data=b"fake", extension=".png", width=300, height=353)


def build(
    cv: CV | None = None,
    photo: ExtractedImage | None = PHOTO,
    font_size: float = 9.0,
) -> str:
    return CVHtmlBuilder().build(cv or make_cv(), photo, FRENCH_LABELS, font_size=font_size)


def test_contains_the_main_content() -> None:
    html = build()

    assert "Jane Doe" in html
    assert "Built an Android app with React Native" in html
    assert "Python, FastAPI" in html


def test_formats_the_period_of_an_entry() -> None:
    assert "Aug. 2026 – Sept. 2026" in build()


def test_photo_is_embedded_as_a_data_uri() -> None:
    encoded = base64.b64encode(b"fake").decode("ascii")

    assert f"data:image/png;base64,{encoded}" in build()


def test_no_image_tag_without_a_photo() -> None:
    assert "<img" not in build(photo=None)


def test_unsupported_photo_format_is_refused() -> None:
    bmp = ExtractedImage(data=b"x", extension=".bmp", width=100, height=100)

    with pytest.raises(UnsupportedPhotoError):
        build(photo=bmp)


def test_html_in_the_content_is_escaped() -> None:
    cv = make_cv()
    header = cv.header.model_copy(update={"name": "<script>alert(1)</script>"})

    html = build(cv.model_copy(update={"header": header}))

    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_empty_sections_are_omitted() -> None:
    html = build(make_cv().model_copy(update={"certifications": []}))

    assert FRENCH_LABELS.certifications not in html
    assert FRENCH_LABELS.languages in html


def test_font_size_is_a_parameter() -> None:
    assert "font-size: 8.5pt" in build(font_size=8.5)


def cv_with_links(linkedin: str, github: str = "") -> CV:
    cv = make_cv()
    header = cv.header.model_copy(update={"linkedin": linkedin, "github": github})
    return cv.model_copy(update={"header": header})


def test_links_without_a_scheme_get_https() -> None:
    html = build(cv_with_links("linkedin.com/in/jane", "github.com/jane"))

    assert '<a href="https://linkedin.com/in/jane">linkedin.com/in/jane</a>' in html
    assert '<a href="https://github.com/jane">github.com/jane</a>' in html


def test_existing_scheme_is_kept() -> None:
    html = build(cv_with_links("http://example.com/jane"))

    assert 'href="http://example.com/jane"' in html


def test_dangerous_links_are_shown_as_text_without_a_link() -> None:
    html = build(cv_with_links("javascript:alert(1)"))

    assert "javascript:alert(1)" in html
    assert 'href="javascript' not in html
    assert "<a " not in html


def test_text_that_is_not_a_domain_is_not_linked() -> None:
    assert "<a " not in build(cv_with_links("my linkedin profile"))
