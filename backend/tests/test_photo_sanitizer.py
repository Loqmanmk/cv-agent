from io import BytesIO

import pytest
from PIL import Image

from app.domain.document import InvalidPhotoError
from app.infrastructure.photo_sanitizer import PillowPhotoSanitizer


def image_bytes(size: tuple[int, int] = (300, 353), image_format: str = "PNG") -> bytes:
    buffer = BytesIO()
    Image.new("RGB", size, "white").save(buffer, format=image_format)
    return buffer.getvalue()


def jpeg_with_exif(size: tuple[int, int], orientation: int | None = None) -> bytes:
    exif = Image.Exif()
    exif[0x010E] = "secret description"
    if orientation is not None:
        exif[0x0112] = orientation
    buffer = BytesIO()
    Image.new("RGB", size, "white").save(buffer, format="JPEG", exif=exif)
    return buffer.getvalue()


def test_a_small_png_stays_a_png_of_the_same_size() -> None:
    result = PillowPhotoSanitizer().sanitize(image_bytes())

    assert result.extension == ".png"
    assert (result.width, result.height) == (300, 353)


def test_a_jpeg_stays_a_jpeg() -> None:
    result = PillowPhotoSanitizer().sanitize(image_bytes(image_format="JPEG"))

    assert result.extension == ".jpg"


def test_a_webp_photo_becomes_a_png() -> None:
    result = PillowPhotoSanitizer().sanitize(image_bytes(image_format="WEBP"))

    assert result.extension == ".png"


def test_a_large_photo_is_shrunk_keeping_its_proportions() -> None:
    result = PillowPhotoSanitizer(output_side=100).sanitize(image_bytes((300, 353)))

    assert max(result.width, result.height) == 100
    assert result.width < result.height


def test_a_small_photo_is_never_enlarged() -> None:
    result = PillowPhotoSanitizer(output_side=800).sanitize(image_bytes((50, 60)))

    assert (result.width, result.height) == (50, 60)


def test_metadata_is_removed() -> None:
    result = PillowPhotoSanitizer().sanitize(jpeg_with_exif((40, 20)))

    with Image.open(BytesIO(result.data)) as image:
        assert len(image.getexif()) == 0


def test_the_phone_rotation_is_applied_before_the_metadata_is_removed() -> None:
    result = PillowPhotoSanitizer().sanitize(jpeg_with_exif((40, 20), orientation=6))

    assert (result.width, result.height) == (20, 40)


def test_other_image_formats_are_refused() -> None:
    with pytest.raises(InvalidPhotoError, match="PNG, JPEG or WebP"):
        PillowPhotoSanitizer().sanitize(image_bytes(image_format="GIF"))


def test_data_that_is_not_an_image_is_refused() -> None:
    with pytest.raises(InvalidPhotoError, match="could not be read"):
        PillowPhotoSanitizer().sanitize(b"this is not an image")


def test_a_truncated_image_is_refused() -> None:
    with pytest.raises(InvalidPhotoError):
        PillowPhotoSanitizer().sanitize(image_bytes()[:60])


def test_too_many_bytes_are_refused() -> None:
    with pytest.raises(InvalidPhotoError, match="too large"):
        PillowPhotoSanitizer(max_bytes=10).sanitize(image_bytes())


def test_too_many_pixels_are_refused() -> None:
    with pytest.raises(InvalidPhotoError, match="too many pixels"):
        PillowPhotoSanitizer(max_pixels=100).sanitize(image_bytes((20, 20)))
