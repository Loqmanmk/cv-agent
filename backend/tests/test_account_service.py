import pytest
from argon2 import PasswordHasher as RawArgon2
from sqlalchemy import Engine, text

from app.domain.accounts import (
    EmailAlreadyRegisteredError,
    InvalidCredentialsError,
    InvalidEmailError,
    WeakPasswordError,
)
from app.infrastructure.argon2_hasher import Argon2PasswordHasher
from app.infrastructure.db.postgres_users import PostgresUserRepository
from app.services.account_service import AccountService
from app.services.password_policy import MAX_LENGTH
from tests.account_helpers import CountingHasher, fast_hasher

EMAIL = "jane.doe@example.com"
PASSWORD = "correct horse battery staple"
WRONG_PASSWORD = "wrong horse battery staple"


@pytest.fixture
def hasher() -> CountingHasher:
    return CountingHasher(fast_hasher())


@pytest.fixture
def service(clean_engine: Engine, hasher: CountingHasher) -> AccountService:
    return AccountService(PostgresUserRepository(clean_engine), hasher)


def stored_hash(engine: Engine) -> str:
    with engine.connect() as connection:
        return str(connection.execute(text("SELECT password_hash FROM users")).scalar_one())


def user_count(engine: Engine) -> int:
    with engine.connect() as connection:
        return int(connection.execute(text("SELECT count(*) FROM users")).scalar_one())


def test_registers_an_account_with_a_lowercase_email(service: AccountService) -> None:
    account = service.register("  Jane.Doe@Example.COM ", PASSWORD)

    assert account.email == EMAIL
    assert account.is_active is True
    assert account.email_verified_at is None


def test_the_password_is_stored_only_as_an_argon2_hash(
    service: AccountService, clean_engine: Engine
) -> None:
    service.register(EMAIL, PASSWORD)

    stored = stored_hash(clean_engine)

    assert stored.startswith("$argon2id$")
    assert "horse" not in stored


def test_the_same_email_cannot_register_twice_whatever_its_case(
    service: AccountService,
) -> None:
    service.register(EMAIL, PASSWORD)

    with pytest.raises(EmailAlreadyRegisteredError):
        service.register("JANE.DOE@example.com", "another long passphrase")


def test_an_invalid_email_creates_nothing(service: AccountService, clean_engine: Engine) -> None:
    with pytest.raises(InvalidEmailError):
        service.register("not an email", PASSWORD)

    assert user_count(clean_engine) == 0


def test_a_weak_password_creates_nothing_and_lists_the_problems(
    service: AccountService, clean_engine: Engine
) -> None:
    with pytest.raises(WeakPasswordError) as raised:
        service.register(EMAIL, "aaaa")

    assert raised.value.problems == [
        "Use at least 12 characters.",
        "Use more different characters.",
    ]
    assert user_count(clean_engine) == 0


def test_the_placeholder_email_cannot_be_registered(service: AccountService) -> None:
    with pytest.raises(InvalidEmailError):
        service.register("local@cvagent.invalid", PASSWORD)


def test_a_correct_login_returns_the_account(service: AccountService) -> None:
    registered = service.register(EMAIL, PASSWORD)

    assert service.authenticate(EMAIL, PASSWORD) == registered


def test_the_email_of_a_login_is_not_case_sensitive(service: AccountService) -> None:
    registered = service.register(EMAIL, PASSWORD)

    assert service.authenticate(" Jane.DOE@example.com ", PASSWORD) == registered


def test_a_wrong_password_fails(service: AccountService) -> None:
    service.register(EMAIL, PASSWORD)

    with pytest.raises(InvalidCredentialsError):
        service.authenticate(EMAIL, WRONG_PASSWORD)


def test_an_unknown_email_fails_the_same_way_and_still_costs_a_hash_check(
    service: AccountService, hasher: CountingHasher
) -> None:
    with pytest.raises(InvalidCredentialsError):
        service.authenticate("nobody@example.com", PASSWORD)

    assert hasher.verify_calls == 1


def test_an_invalid_email_fails_the_same_way_and_still_costs_a_hash_check(
    service: AccountService, hasher: CountingHasher
) -> None:
    with pytest.raises(InvalidCredentialsError):
        service.authenticate("not an email", PASSWORD)

    assert hasher.verify_calls == 1


def test_a_wrong_password_costs_exactly_one_hash_check(
    service: AccountService, hasher: CountingHasher
) -> None:
    service.register(EMAIL, PASSWORD)

    with pytest.raises(InvalidCredentialsError):
        service.authenticate(EMAIL, WRONG_PASSWORD)

    assert hasher.verify_calls == 1


def test_a_disabled_account_cannot_log_in_even_with_the_right_password(
    service: AccountService, clean_engine: Engine, hasher: CountingHasher
) -> None:
    service.register(EMAIL, PASSWORD)
    with clean_engine.begin() as connection:
        connection.execute(text("UPDATE users SET is_active = false"))

    with pytest.raises(InvalidCredentialsError):
        service.authenticate(EMAIL, PASSWORD)

    assert hasher.verify_calls == 1


def test_an_enormous_password_is_refused_without_hashing_it(
    service: AccountService, hasher: CountingHasher
) -> None:
    service.register(EMAIL, PASSWORD)

    with pytest.raises(InvalidCredentialsError):
        service.authenticate(EMAIL, "x" * (MAX_LENGTH + 1))

    assert hasher.verify_calls == 0


def test_the_same_password_typed_on_another_keyboard_still_works(
    service: AccountService,
) -> None:
    service.register(EMAIL, "caf\u00e9 horse battery staple")

    assert service.authenticate(EMAIL, "cafe\u0301 horse battery staple").email == EMAIL


def test_the_placeholder_user_of_the_tracker_can_never_log_in(
    service: AccountService, clean_engine: Engine
) -> None:
    with clean_engine.begin() as connection:
        connection.execute(
            text("INSERT INTO users (email, password_hash) VALUES (:email, '!')"),
            {"email": "local@cvagent.invalid"},
        )

    with pytest.raises(InvalidCredentialsError):
        service.authenticate("local@cvagent.invalid", "!")
    with pytest.raises(InvalidCredentialsError):
        service.authenticate("local@cvagent.invalid", PASSWORD)


def test_a_login_upgrades_a_hash_made_with_weaker_settings(clean_engine: Engine) -> None:
    users = PostgresUserRepository(clean_engine)
    AccountService(users, fast_hasher()).register(EMAIL, PASSWORD)
    stronger = Argon2PasswordHasher(RawArgon2(time_cost=2, memory_cost=16, parallelism=1))

    AccountService(users, stronger).authenticate(EMAIL, PASSWORD)

    assert "m=16,t=2" in stored_hash(clean_engine)
    assert AccountService(users, stronger).authenticate(EMAIL, PASSWORD).email == EMAIL
