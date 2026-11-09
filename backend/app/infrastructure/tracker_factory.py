from sqlalchemy import Engine

from app.infrastructure.application_factory import build_render_service
from app.infrastructure.db.postgres_tracker import PostgresApplicationRepository
from app.infrastructure.photo_sanitizer import PillowPhotoSanitizer
from app.services.tracker_service import TrackerService


def build_tracker_service(engine: Engine) -> TrackerService:
    """Wire the tracker to the database. It needs no AI."""
    return TrackerService(
        PostgresApplicationRepository(engine),
        build_render_service(),
        PillowPhotoSanitizer(),
    )
