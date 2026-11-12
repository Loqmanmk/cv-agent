import base64
import hashlib
import logging
import secrets
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlencode

import httpx
import jwt
from jwt import PyJWK, PyJWKClient
from pydantic import SecretStr

from app.domain.oauth import ExternalIdentity, OAuthError

logger = logging.getLogger(__name__)

AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
CODE_EXCHANGE_URL = "https://oauth2.googleapis.com/token"
JWKS_URL = "https://www.googleapis.com/oauth2/v3/certs"
ISSUERS = ("https://accounts.google.com", "accounts.google.com")
SCOPES = "openid email profile"
CLOCK_SKEW_SECONDS = 60
HTTP_TIMEOUT_SECONDS = 10.0
FAILED = "Signing in with Google failed. Please try again."

KeyResolver = Callable[[str], PyJWK]


def pkce_challenge(verifier: str) -> str:
    """The S256 challenge of a PKCE verifier: base64url(sha256(verifier)), without padding."""
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def google_keys() -> KeyResolver:
    """Google's public signing keys, cached between sign-ins."""
    return PyJWKClient(
        JWKS_URL, cache_keys=True, timeout=int(HTTP_TIMEOUT_SECONDS)
    ).get_signing_key_from_jwt


@dataclass(frozen=True)
class AuthorizationRequest:
    url: str = field(repr=False)
    state: str = field(repr=False)
    nonce: str = field(repr=False)
    code_verifier: str = field(repr=False)


class GoogleOidcClient:
    """Signs a user in with Google (OpenID Connect, authorization code flow with PKCE)."""

    def __init__(
        self,
        client_id: str,
        client_secret: SecretStr,
        redirect_uri: str,
        http: httpx.Client | None = None,
        keys: KeyResolver | None = None,
    ) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._redirect_uri = redirect_uri
        self._http = http or httpx.Client(timeout=HTTP_TIMEOUT_SECONDS)
        self._keys = keys or google_keys()

    def start(self) -> AuthorizationRequest:
        """Where to send the browser, and the one-time values to keep until the callback."""
        state = secrets.token_urlsafe(32)
        nonce = secrets.token_urlsafe(32)
        verifier = secrets.token_urlsafe(64)
        params = {
            "response_type": "code",
            "client_id": self._client_id,
            "redirect_uri": self._redirect_uri,
            "scope": SCOPES,
            "state": state,
            "nonce": nonce,
            "code_challenge": pkce_challenge(verifier),
            "code_challenge_method": "S256",
            "prompt": "select_account",
        }
        return AuthorizationRequest(f"{AUTHORIZE_URL}?{urlencode(params)}", state, nonce, verifier)

    def finish(self, code: str, code_verifier: str, nonce: str) -> ExternalIdentity:
        """Exchange the code for Google's signed answer and check every part of it."""
        claims = self._verify(self._exchange(code, code_verifier), nonce)
        subject = claims.get("sub")
        email = claims.get("email")
        if not isinstance(subject, str) or not subject or not isinstance(email, str) or not email:
            raise OAuthError(FAILED)
        verified = claims.get("email_verified") in (True, "true")
        return ExternalIdentity("google", subject, email, verified)

    def _exchange(self, code: str, code_verifier: str) -> str:
        form = {
            "grant_type": "authorization_code",
            "code": code,
            "code_verifier": code_verifier,
            "client_id": self._client_id,
            "client_secret": self._client_secret.get_secret_value(),
            "redirect_uri": self._redirect_uri,
        }
        try:
            response = self._http.post(CODE_EXCHANGE_URL, data=form)
        except httpx.HTTPError as exc:
            raise OAuthError(FAILED) from exc
        if response.status_code != httpx.codes.OK:
            logger.warning("Google refused the code (status %s).", response.status_code)
            raise OAuthError(FAILED)
        try:
            body = response.json()
        except ValueError as exc:
            raise OAuthError(FAILED) from exc
        token = body.get("id_token") if isinstance(body, dict) else None
        if not isinstance(token, str):
            raise OAuthError(FAILED)
        return token

    def _verify(self, id_token: str, nonce: str) -> dict[str, Any]:
        try:
            key = self._keys(id_token)
            claims: dict[str, Any] = jwt.decode(
                id_token,
                key=key.key,
                algorithms=["RS256"],
                audience=self._client_id,
                options={"require": ["exp", "iat", "iss", "aud", "sub"]},
                leeway=CLOCK_SKEW_SECONDS,
            )
        except jwt.PyJWTError as exc:
            logger.warning("Google's answer was refused: %s", type(exc).__name__)
            raise OAuthError(FAILED) from exc
        if claims.get("iss") not in ISSUERS:
            raise OAuthError(FAILED)
        token_nonce = claims.get("nonce")
        if not isinstance(token_nonce, str) or not secrets.compare_digest(token_nonce, nonce):
            raise OAuthError(FAILED)
        return claims
