import secrets
import uuid

from app.domain.accounts import (
    Account,
    InvalidCredentialsError,
    InvalidEmailError,
    PasswordHasher,
    UserRepository,
    WeakPasswordError,
)
from app.services.email_address import normalize_email
from app.services.password_policy import MAX_LENGTH, normalize_password, password_problems

DUMMY_SECRET_BYTES = 32


class AccountService:
    """Creates accounts and checks logins."""

    def __init__(self, users: UserRepository, hasher: PasswordHasher) -> None:
        self._users = users
        self._hasher = hasher
        self._dummy_hash: str | None = None

    def register(self, email: str, password: str) -> Account:
        address = normalize_email(email)
        secret = normalize_password(password)
        problems = password_problems(secret, address)
        if problems:
            raise WeakPasswordError(problems)
        return self._users.create(address, self._hasher.hash(secret))

    def authenticate(self, email: str, password: str) -> Account:
        """The account of a correct login. Every failure looks the same, in text and in timing."""
        secret = normalize_password(password)
        try:
            address = normalize_email(email)
        except InvalidEmailError:
            self._spend_the_time_of_a_check(secret)
            raise InvalidCredentialsError from None
        stored = self._users.find_by_email(address)
        if stored is None or not stored.account.is_active:
            self._spend_the_time_of_a_check(secret)
            raise InvalidCredentialsError
        if len(secret) > MAX_LENGTH or not self._hasher.verify(stored.password_hash, secret):
            raise InvalidCredentialsError
        if self._hasher.needs_rehash(stored.password_hash):
            self._users.update_password_hash(stored.account.id, self._hasher.hash(secret))
        return stored.account

    def find_account(self, email: str) -> Account | None:
        """The account of an address, or None. Never put the answer in a public reply."""
        try:
            address = normalize_email(email)
        except InvalidEmailError:
            return None
        stored = self._users.find_by_email(address)
        return None if stored is None else stored.account

    def mark_email_verified(self, user_id: uuid.UUID) -> None:
        self._users.mark_email_verified(user_id)

    def validate_new_password(self, email: str, password: str) -> None:
        """Raise WeakPasswordError when the password breaks the rules for this address."""
        problems = password_problems(normalize_password(password), email)
        if problems:
            raise WeakPasswordError(problems)

    def set_password(self, user_id: uuid.UUID, password: str) -> None:
        """Store a new password. Call validate_new_password first."""
        self._users.update_password_hash(user_id, self._hasher.hash(normalize_password(password)))

    def get_account(self, user_id: uuid.UUID) -> Account | None:
        return self._users.find_by_id(user_id)

    def _spend_the_time_of_a_check(self, secret: str) -> None:
        """Without this, an unknown email would answer faster than a wrong password."""
        if self._dummy_hash is None:
            self._dummy_hash = self._hasher.hash(secrets.token_urlsafe(DUMMY_SECRET_BYTES))
        self._hasher.verify(self._dummy_hash, secret if len(secret) <= MAX_LENGTH else "")
