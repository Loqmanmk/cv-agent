import logging

from app.domain.accounts import Account, EmailAlreadyRegisteredError
from app.domain.mail import EmailMessage, EmailSender
from app.services.account_service import AccountService
from app.services.email_address import normalize_email
from app.services.email_templates import account_exists_email, verification_email
from app.services.email_token_service import EmailTokenService

logger = logging.getLogger(__name__)

VERIFY_PATH = "/verify-email"
LOGIN_PATH = "/login"


class VerificationService:
    """Registers accounts and confirms that their owners control the email address."""

    def __init__(
        self,
        accounts: AccountService,
        tokens: EmailTokenService,
        sender: EmailSender,
        app_base_url: str,
    ) -> None:
        base = app_base_url.strip().rstrip("/")
        if not base.startswith(("http://", "https://")):
            raise ValueError("APP_BASE_URL must start with http:// or https://")
        self._accounts = accounts
        self._tokens = tokens
        self._sender = sender
        self._base = base

    def register(self, email: str, password: str) -> None:
        """Create the account and send the link. An existing address gets a notice instead."""
        try:
            account = self._accounts.register(email, password)
        except EmailAlreadyRegisteredError:
            address = normalize_email(email)
            self._send(account_exists_email(address, self._base + LOGIN_PATH))
            return
        self.send_link(account)

    def send_link(self, account: Account) -> None:
        if account.email_verified_at is not None or not account.is_active:
            return
        token = self._tokens.issue(account.id, "verify_email")
        # The token travels after "#": browsers never send that part to a server or a Referer.
        link = f"{self._base}{VERIFY_PATH}#token={token}"
        self._send(verification_email(account.email, link))

    def resend(self, email: str) -> None:
        account = self._accounts.find_account(email)
        if account is not None:
            self.send_link(account)

    def verify(self, token: str | None) -> bool:
        user_id = self._tokens.consume(token, "verify_email")
        if user_id is None:
            return False
        self._accounts.mark_email_verified(user_id)
        return True

    def _send(self, message: EmailMessage) -> None:
        try:
            self._sender.send(message)
        except Exception:
            # The reply must not depend on delivery, or it would reveal which addresses exist.
            logger.exception("An email could not be sent.")
