from app.domain.document import ExtractedImage


class PhotoSelector:
    """Picks the most likely profile photo among the images of a CV."""

    def __init__(
        self,
        min_side: int = 100,
        min_ratio: float = 0.8,
        max_ratio: float = 1.6,
    ) -> None:
        self._min_side = min_side
        self._min_ratio = min_ratio
        self._max_ratio = max_ratio

    def select(self, images: list[ExtractedImage]) -> ExtractedImage | None:
        candidates = [image for image in images if self._is_photo_like(image)]
        if not candidates:
            return None
        return max(candidates, key=lambda image: image.width * image.height)

    def _is_photo_like(self, image: ExtractedImage) -> bool:
        if min(image.width, image.height) < self._min_side:
            return False
        ratio = image.height / image.width
        return self._min_ratio <= ratio <= self._max_ratio
