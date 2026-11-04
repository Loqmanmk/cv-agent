from app.domain.document import ExtractedImage
from app.services.photo_selector import PhotoSelector


def image(width: int, height: int) -> ExtractedImage:
    return ExtractedImage(data=b"", extension=".png", width=width, height=height)


def test_returns_none_without_images() -> None:
    assert PhotoSelector().select([]) is None


def test_ignores_small_images() -> None:
    assert PhotoSelector().select([image(40, 40)]) is None


def test_ignores_wide_banners() -> None:
    assert PhotoSelector().select([image(600, 150)]) is None


def test_accepts_portrait_photo() -> None:
    photo = image(300, 353)

    assert PhotoSelector().select([photo]) is photo


def test_accepts_square_photo() -> None:
    photo = image(200, 200)

    assert PhotoSelector().select([photo]) is photo


def test_picks_photo_among_logo_and_banner() -> None:
    photo = image(300, 353)

    result = PhotoSelector().select([image(48, 48), photo, image(800, 100)])

    assert result is photo


def test_picks_the_biggest_valid_photo() -> None:
    small = image(150, 180)
    big = image(300, 353)

    assert PhotoSelector().select([small, big]) is big
