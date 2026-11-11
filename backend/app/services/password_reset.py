from app.domain.mail import EmailSender
from app.services.account_service import AccountService
from app.services.email_templates import password_changed_email, reset_password_email
from app.services.email_token_service import EmailTokenService
from app.services.mailing import clean_base_url, send_quietly
from app.services.session_service import SessionService

RESET_PATH = "/reset-password"
FORGOT_PATH = "/forgot-password"


class InvalidResetLinkError(Exception):
    """Raised when a reset link is unknown, used, expired or belongs to a disabled account."""


class PasswordResetService:
    """Lets the owner of an email address choose a new password."""

    def __init__(
        self,
        accounts: AccountService,
        tokens: EmailTokenService,
        sessions: SessionService,
        sender: EmailSender,
        app_base_url: str,
    ) -> None:
        self._accounts = accounts
        self._tokens = tokens
        self._sessions = sessions
        self._sender = sender
        self._base = clean_base_url(app_base_url)

    def request(self, email: str) -> None:
        """Send a reset link if an active account exists. Callers must reply the same anyway."""
        account = self._accounts.find_account(email)
        if account is None or not account.is_active:
            return
        token = self._tokens.issue(account.id, "reset_password")
        link = f"{self._base}{RESET_PATH}#token={token}"
        send_quietly(self._sender, reset_password_email(account.email, link))

    def reset(self, token: str | None, password: str) -> None:
        user_id = self._tokens.peek(token, "reset_password")
        account = None if user_id is None else self._accounts.get_account(user_id)
        if account is None or not account.is_active:
            raise InvalidResetLinkError
        # The password is checked before the link is used up, so a typo does not cost an email.
        self._accounts.validate_new_password(account.email, password)
        if self._tokens.consume(token, "reset_password") != account.id:
            raise InvalidResetLinkError
        self._accounts.set_password(account.id, password)
        # Opening the link proves that the user controls the address.
        self._accounts.mark_email_verified(account.id)
        self._sessions.end_all(account.id)
        send_quietly(self._sender, password_changed_email(account.email, self._base + FORGOT_PATH))
