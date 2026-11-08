from functools import lru_cache

from app.core.config import get_settings
from app.infrastructure.tracker_factory import build_tracker_service
from app.services.tracker_service import TrackerService


@lru_cache
def get_tracker_service() -> TrackerService:
    return build_tracker_service(get_settings())
