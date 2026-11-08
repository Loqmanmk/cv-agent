from app.core.config import Settings
from app.infrastructure.application_factory import build_render_service
from app.infrastructure.photo_sanitizer import PillowPhotoSanitizer
from app.infrastructure.sqlite_tracker import SqliteApplicationRepository
from app.services.tracker_service import TrackerService


def build_tracker_service(settings: Settings) -> TrackerService:
    """Wire the tracker to its SQLite file. It needs no AI."""
    return TrackerService(
        SqliteApplicationRepository(settings.tracker_db_path),
        build_render_service(),
        PillowPhotoSanitizer(),
    )
