from argon2 import PasswordHasher as RawArgon2

from app.infrastructure.argon2_hasher import Argon2PasswordHasher
from tests.account_helpers import fast_hasher

PASSWORD = "correct horse battery"


def test_the_default_hasher_uses_argon2id() -> None:
    assert Argon2PasswordHasher().hash(PASSWORD).startswith("$argon2id$")


def test_a_password_matches_its_own_hash_only() -> None:
    hasher = fast_hasher()
    stored = hasher.hash(PASSWORD)

    assert hasher.verify(stored, PASSWORD) is True
    assert hasher.verify(stored, "wrong horse battery") is False


def test_the_same_password_gets_a_different_hash_each_time() -> None:
    hasher = fast_hasher()

    assert hasher.hash(PASSWORD) != hasher.hash(PASSWORD)


def test_the_hash_does_not_contain_the_password() -> None:
    assert "correct horse" not in fast_hasher().hash(PASSWORD)


def test_a_hash_that_cannot_be_read_never_matches() -> None:
    hasher = fast_hasher()

    assert hasher.verify("!", "anything") is False
    assert hasher.verify("", "anything") is False
    assert hasher.verify("not a hash at all", "anything") is False


def test_a_weaker_hash_needs_an_upgrade_and_a_current_one_does_not() -> None:
    weak = fast_hasher().hash(PASSWORD)
    strong = Argon2PasswordHasher(RawArgon2(time_cost=2, memory_cost=16, parallelism=1))

    assert strong.needs_rehash(weak) is True
    assert strong.needs_rehash(strong.hash(PASSWORD)) is False


def test_an_unreadable_hash_does_not_ask_for_an_upgrade() -> None:
    assert fast_hasher().needs_rehash("!") is False
