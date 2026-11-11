import uuid

import pytest
from sqlalchemy import Engine

from app.infrastructure.db.postgres_users import PostgresUserRepository
from app.services.account_service import AccountService
from tests.account_helpers import fast_hasher

EMAIL = "jane.doe@example.com"
PASSWORD = "correct horse battery staple"


@pytest.fixture
def users(clean_engine: Engine) -> PostgresUserRepository:
    return PostgresUserRepository(clean_engine)


def test_the_repository_finds_an_account_by_its_id(users: PostgresUserRepository) -> None:
    created = users.create(EMAIL, "hash-1")

    assert users.find_by_id(created.id) == created


def test_an_unknown_id_is_not_found(users: PostgresUserRepository) -> None:
    assert users.find_by_id(uuid.uuid4()) is None


def test_the_service_finds_an_account_by_its_id(users: PostgresUserRepository) -> None:
    service = AccountService(users, fast_hasher())
    registered = service.register(EMAIL, PASSWORD)

    assert service.get_account(registered.id) == registered
    assert service.get_account(uuid.uuid4()) is None
