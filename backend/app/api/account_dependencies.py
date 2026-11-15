from functools import lru_cache

from app.api.database import get_engine
from app.infrastructure.db.postgres_profiles import PostgresProfileRepository
from app.infrastructure.db.postgres_saved_cvs import PostgresSavedCvRepository
from app.infrastructure.db.postgres_usage import PostgresUsageRepository
from app.services.profile_service import ProfileService
from app.services.quota_service import QuotaService
from app.services.saved_cv_service import SavedCvService


@lru_cache
def get_profile_service() -> ProfileService:
    return ProfileService(PostgresProfileRepository(get_engine()))


@lru_cache
def get_quota_service() -> QuotaService:
    return QuotaService(PostgresUsageRepository(get_engine()))


@lru_cache
def get_saved_cv_service() -> SavedCvService:
    return SavedCvService(PostgresSavedCvRepository(get_engine()))
