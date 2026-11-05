from app.services.pii_masker import PiiMasker


def test_masks_email() -> None:
    result = PiiMasker().mask("Mail: jane@example.com")

    assert result.text == "Mail: [[EMAIL_1]]"
    assert result.mapping == {"[[EMAIL_1]]": "jane@example.com"}


def test_masks_phone_number() -> None:
    result = PiiMasker().mask("Tel: +33 6 12 34 56 78")

    assert result.text == "Tel: [[PHONE_1]]"


def test_keeps_date_ranges() -> None:
    text = "Sept. 2021 - Juil. 2022 | 2021 - 2022"

    assert PiiMasker().mask(text).text == text


def test_masks_profile_links() -> None:
    result = PiiMasker().mask("linkedin.com/in/jane-doe | github.com/janedoe")

    assert result.text == "[[URL_1]] | [[URL_2]]"


def test_same_value_gets_the_same_placeholder() -> None:
    result = PiiMasker().mask("a@b.com and a@b.com")

    assert result.text == "[[EMAIL_1]] and [[EMAIL_1]]"
    assert len(result.mapping) == 1


def test_trailing_punctuation_stays_outside_the_placeholder() -> None:
    result = PiiMasker().mask("Code: github.com/janedoe.")

    assert result.text == "Code: [[URL_1]]."
    assert result.mapping["[[URL_1]]"] == "github.com/janedoe"


def test_restore_gives_back_the_original_text() -> None:
    masker = PiiMasker()
    original = "jane@example.com / +33 6 12 34 56 78"

    masked = masker.mask(original)

    assert masker.restore(masked.text, masked.mapping) == original


def test_quotes_around_a_value_stay_outside_the_placeholder() -> None:
    text = '"email": "jane@example.com",\n"github": "github.com/janedoe"'

    result = PiiMasker().mask(text)

    assert result.text == '"email": "[[EMAIL_1]]",\n"github": "[[URL_1]]"'
