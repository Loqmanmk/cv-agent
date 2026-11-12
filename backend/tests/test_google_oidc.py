import time
from typing import Any
from urllib.parse import parse_qs, urlsplit

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey
from jwt import PyJWK
from jwt.algorithms import RSAAlgorithm
from pydantic import SecretStr

from app.domain.oauth import ExternalIdentity, OAuthError
from app.infrastructure.google_oidc import (
    AUTHORIZE_URL,
    CODE_EXCHANGE_URL,
    GoogleOidcClient,
    pkce_challenge,
)

CLIENT_ID = "client-123.apps.googleusercontent.com"
SECRET = "client-secret-value"
REDIRECT = "http://localhost:8000/auth/google/callback"
NONCE = "nonce-value"
GOOGLE_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
OTHER_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)


def public_jwk(private: RSAPrivateKey) -> PyJWK:
    data = RSAAlgorithm.to_jwk(private.public_key(), as_dict=True)
    data.update({"kid": "k1", "alg": "RS256", "use": "sig"})
    return PyJWK.from_dict(data)


def claims(**changes: Any) -> dict[str, Any]:
    now = int(time.time())
    base: dict[str, Any] = {
        "iss": "https://accounts.google.com",
        "aud": CLIENT_ID,
        "sub": "google-user-1",
        "email": "Jane.Doe@gmail.com",
        "email_verified": True,
        "nonce": NONCE,
        "iat": now,
        "exp": now + 3600,
    }
    base.update(changes)
    return {key: value for key, value in base.items() if value is not None}


def sign(payload: dict[str, Any], key: RSAPrivateKey = GOOGLE_KEY) -> str:
    return jwt.encode(payload, key, algorithm="RS256", headers={"kid": "k1"})


class FakeGoogle:
    """A token endpoint that answers with a preset body and records what it received."""

    def __init__(self, body: object, status: int = 200) -> None:
        self.body = body
        self.status = status
        self.forms: list[dict[str, list[str]]] = []

    def handle(self, request: httpx.Request) -> httpx.Response:
        assert str(request.url) == CODE_EXCHANGE_URL
        self.forms.append(parse_qs(request.content.decode("ascii")))
        return httpx.Response(self.status, json=self.body)


def make_client(google: FakeGoogle) -> GoogleOidcClient:
    http = httpx.Client(transport=httpx.MockTransport(google.handle))
    key = public_jwk(GOOGLE_KEY)
    return GoogleOidcClient(CLIENT_ID, SecretStr(SECRET), REDIRECT, http, lambda _token: key)


def finish_with(token: str) -> ExternalIdentity:
    return make_client(FakeGoogle({"id_token": token})).finish("code-1", "verifier-1", NONCE)


def test_the_authorization_address_carries_every_protection() -> None:
    request = make_client(FakeGoogle({})).start()

    parts = urlsplit(request.url)
    params = {key: values[0] for key, values in parse_qs(parts.query).items()}
    assert f"{parts.scheme}://{parts.netloc}{parts.path}" == AUTHORIZE_URL
    assert params["response_type"] == "code"
    assert params["client_id"] == CLIENT_ID
    assert params["redirect_uri"] == REDIRECT
    assert params["scope"] == "openid email profile"
    assert params["state"] == request.state
    assert params["nonce"] == request.nonce
    assert params["code_challenge"] == pkce_challenge(request.code_verifier)
    assert params["code_challenge_method"] == "S256"
    assert request.code_verifier not in request.url
    assert SECRET not in request.url


def test_every_start_uses_new_random_values() -> None:
    client = make_client(FakeGoogle({}))
    first, second = client.start(), client.start()

    assert len({first.state, first.nonce, first.code_verifier}) == 3
    assert (first.state, first.nonce) != (second.state, second.nonce)
    assert 43 <= len(first.code_verifier) <= 128


def test_the_values_never_appear_in_a_printed_request() -> None:
    request = make_client(FakeGoogle({})).start()

    assert request.state not in repr(request)
    assert request.code_verifier not in repr(request)


def test_the_pkce_challenge_is_the_base64url_sha256_of_the_verifier() -> None:
    verifier = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r7wW1gFWFOEjXk"

    assert pkce_challenge(verifier) == "bwWFMyPfdG9qreDhH2lmftFx_dFeLDalzcT1gb_j68g"


def test_a_valid_answer_gives_the_identity() -> None:
    google = FakeGoogle({"id_token": sign(claims())})

    identity = make_client(google).finish("code-1", "verifier-1", NONCE)

    assert (identity.provider, identity.subject) == ("google", "google-user-1")
    assert identity.email == "Jane.Doe@gmail.com"
    assert identity.email_verified is True
    form = google.forms[0]
    assert form["grant_type"] == ["authorization_code"]
    assert form["code"] == ["code-1"]
    assert form["code_verifier"] == ["verifier-1"]
    assert form["redirect_uri"] == [REDIRECT]
    assert form["client_secret"] == [SECRET]


def test_an_email_marked_verified_as_text_is_accepted() -> None:
    identity = finish_with(sign(claims(email_verified="true")))

    assert identity.email_verified is True


def test_an_unverified_email_is_reported_as_such() -> None:
    identity = finish_with(sign(claims(email_verified=False)))

    assert identity.email_verified is False


def test_the_short_issuer_form_is_accepted() -> None:
    assert finish_with(sign(claims(iss="accounts.google.com"))) is not None


@pytest.mark.parametrize(
    "token",
    [
        pytest.param(sign(claims(aud="another-app")), id="wrong-audience"),
        pytest.param(sign(claims(iss="https://evil.example")), id="wrong-issuer"),
        pytest.param(sign(claims(exp=int(time.time()) - 3600)), id="expired"),
        pytest.param(sign(claims(nonce="replayed")), id="wrong-nonce"),
        pytest.param(sign(claims(nonce=None)), id="no-nonce"),
        pytest.param(sign(claims(sub=None)), id="no-subject"),
        pytest.param(sign(claims(email=None)), id="no-email"),
        pytest.param(sign(claims(), OTHER_KEY), id="forged-signature"),
        pytest.param(jwt.encode(claims(), key="", algorithm="none"), id="unsigned"),
        pytest.param(
            jwt.encode(claims(), "a-test-hmac-key-that-is-32-bytes-long", algorithm="HS256"),
            id="wrong-algorithm",
        ),
        pytest.param("not-a-token", id="garbage"),
    ],
)
def test_an_answer_that_fails_a_check_is_refused(token: str) -> None:
    with pytest.raises(OAuthError, match="Signing in with Google failed"):
        finish_with(token)


@pytest.mark.parametrize(
    ("body", "status"),
    [({"error": "invalid_grant"}, 400), ({}, 200), (["unexpected"], 200), ({"id_token": 5}, 200)],
)
def test_a_bad_answer_of_the_token_endpoint_is_refused(body: object, status: int) -> None:
    with pytest.raises(OAuthError):
        make_client(FakeGoogle(body, status)).finish("code-1", "verifier-1", NONCE)


def test_a_network_failure_is_refused_without_details() -> None:
    def unreachable(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no route", request=request)

    key = public_jwk(GOOGLE_KEY)
    http = httpx.Client(transport=httpx.MockTransport(unreachable))
    client = GoogleOidcClient(CLIENT_ID, SecretStr(SECRET), REDIRECT, http, lambda _token: key)

    with pytest.raises(OAuthError) as raised:
        client.finish("code-1", "verifier-1", NONCE)

    assert SECRET not in str(raised.value)
