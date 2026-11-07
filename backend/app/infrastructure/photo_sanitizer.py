from io import BytesIO

from PIL import Image, ImageOps, UnidentifiedImageError

from app.domain.document import ExtractedImage, InvalidPhotoError, PhotoSanitizer

MAX_PHOTO_BYTES = 5_000_000
MAX_PIXELS = 30_000_000
OUTPUT_SIDE = 800
JPEG_FORMATS = {"JPEG", "MPO"}  # many phones save JPEG photos as MPO
ALLOWED_FORMATS = JPEG_FORMATS | {"PNG", "WEBP"}


class PillowPhotoSanitizer(PhotoSanitizer):
    """Checks an untrusted image, then re-encodes it small and without metadata."""

    def __init__(
        self,
        max_bytes: int = MAX_PHOTO_BYTES,
        max_pixels: int = MAX_PIXELS,
        output_side: int = OUTPUT_SIDE,
    ) -> None:
        self._max_bytes = max_bytes
        self._max_pixels = max_pixels
        self._output_side = output_side

    def sanitize(self, data: bytes) -> ExtractedImage:
        if len(data) > self._max_bytes:
            raise InvalidPhotoError("The photo is too large.")
        try:
            return self._reencode(data)
        except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
            raise InvalidPhotoError("The photo could not be read.") from exc

    def _reencode(self, data: bytes) -> ExtractedImage:
        with Image.open(BytesIO(data)) as source:
            source_format = source.format
            if source_format not in ALLOWED_FORMATS:
                raise InvalidPhotoError("The photo must be a PNG, JPEG or WebP image.")
            if source.width * source.height > self._max_pixels:
                raise InvalidPhotoError("The photo has too many pixels.")
            image = ImageOps.exif_transpose(source) or source
            image.thumbnail((self._output_side, self._output_side))
            buffer = BytesIO()
            if source_format in JPEG_FORMATS:
                image.convert("RGB").save(buffer, format="JPEG", quality=95)
                extension = ".jpg"
            else:
                image.save(buffer, format="PNG")
                extension = ".png"
            return ExtractedImage(buffer.getvalue(), extension, image.width, image.height)
