import uuid

import pytest
from sqlalchemy import Engine

from app.domain.accounts import EmailAlreadyRegisteredError
from app.infrastructure.db.postgres_users import PostgresUserRepository


@pytest.fixture
def users(clean_engine: Engine) -> PostgresUserRepository:
    return PostgresUserRepository(clean_engine)


def test_creates_an_active_unverified_account(users: PostgresUserRepository) -> None:
    account = users.create("jane@example.com", "hash-1")

    assert isinstance(account.id, uuid.UUID)
    assert account.email == "jane@example.com"
    assert account.is_active is True
    assert account.email_verified_at is None
    assert account.created_at.tzinfo is not None


def test_an_email_can_only_be_registered_once(users: PostgresUserRepository) -> None:
    users.create("jane@example.com", "hash-1")

    with pytest.raises(EmailAlreadyRegisteredError):
        users.create("jane@example.com", "hash-2")


def test_the_first_account_keeps_its_hash_when_a_second_attempt_fails(
    users: PostgresUserRepository,
) -> None:
    users.create("jane@example.com", "hash-1")
    with pytest.raises(EmailAlreadyRegisteredError):
        users.create("jane@example.com", "hash-2")

    stored = users.find_by_email("jane@example.com")

    assert stored is not None
    assert stored.password_hash == "hash-1"


def test_finds_an_account_with_its_hash(users: PostgresUserRepository) -> None:
    created = users.create("jane@example.com", "hash-1")

    stored = users.find_by_email("jane@example.com")

    assert stored is not None
    assert stored.account == created
    assert stored.password_hash == "hash-1"


def test_an_unknown_email_is_not_found(users: PostgresUserRepository) -> None:
    assert users.find_by_email("nobody@example.com") is None


def test_the_hash_never_appears_in_a_printed_account(users: PostgresUserRepository) -> None:
    users.create("jane@example.com", "secret-hash-value")

    stored = users.find_by_email("jane@example.com")

    assert stored is not None
    assert "secret-hash-value" not in repr(stored)


def test_updates_the_hash_of_one_account_only(users: PostgresUserRepository) -> None:
    first = users.create("first@example.com", "hash-1")
    users.create("second@example.com", "hash-2")

    users.update_password_hash(first.id, "hash-new")

    updated = users.find_by_email("first@example.com")
    untouched = users.find_by_email("second@example.com")
    assert updated is not None
    assert untouched is not None
    assert (updated.password_hash, untouched.password_hash) == ("hash-new", "hash-2")
