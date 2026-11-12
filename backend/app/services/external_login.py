from app.domain.accounts import (
    NO_LOGIN_HASH,
    Account,
    EmailAlreadyRegisteredError,
    InvalidEmailError,
    UserRepository,
)
from app.domain.oauth import ExternalIdentity, OAuthError, OAuthIdentityRepository
from app.services.email_address import normalize_email
from app.services.session_service import SessionService

FAILED = "Signing in with Google failed. Please try again."
UNVERIFIED_EMAIL = "Your Google email address is not verified, so it cannot be used here."
UNAVAILABLE = "This account cannot be used."


def _active(account: Account | None) -> Account:
    if account is None or not account.is_active:
        raise OAuthError(UNAVAILABLE)
    return account


class ExternalLoginService:
    """Finds, links or creates the account of someone who signed in with a provider."""

    def __init__(
        self,
        users: UserRepository,
        identities: OAuthIdentityRepository,
        sessions: SessionService,
    ) -> None:
        self._users = users
        self._identities = identities
        self._sessions = sessions

    def sign_in(self, identity: ExternalIdentity) -> Account:
        if not identity.email_verified:
            raise OAuthError(UNVERIFIED_EMAIL)
        known = self._identities.find_user(identity.provider, identity.subject)
        if known is not None:
            return _active(self._users.find_by_id(known))
        address = self._address(identity.email)
        account = self._existing_or_new(address)
        self._identities.link(account.id, identity.provider, identity.subject, address)
        return _active(self._users.find_by_id(account.id))

    @staticmethod
    def _address(email: str) -> str:
        try:
            return normalize_email(email)
        except InvalidEmailError as exc:
            raise OAuthError(FAILED) from exc

    def _existing_or_new(self, address: str) -> Account:
        stored = self._users.find_by_email(address)
        if stored is None:
            try:
                return self._users.create_external(address)
            except EmailAlreadyRegisteredError:
                stored = self._users.find_by_email(address)  # created at the same moment
                if stored is None:
                    raise OAuthError(FAILED) from None
        account = _active(stored.account)
        if account.email_verified_at is None:
            self._take_over(account)
        return account

    def _take_over(self, account: Account) -> None:
        """Someone may have registered this address without owning it: their access goes."""
        self._users.update_password_hash(account.id, NO_LOGIN_HASH)
        self._sessions.end_all(account.id)
        self._users.mark_email_verified(account.id)
