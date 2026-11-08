import functools
import http.client
import ipaddress
import re
import socket
import ssl
import time
from collections.abc import Callable
from dataclasses import dataclass
from urllib.parse import SplitResult, quote, urljoin, urlsplit

from app.domain.job_source import FetchedPage, JobFetchError, PageFetcher

MAX_URL_CHARS = 2000
MAX_BYTES = 2_000_000
MAX_REDIRECTS = 3
SOCKET_TIMEOUT_SECONDS = 5.0
TOTAL_TIMEOUT_SECONDS = 15.0
CHUNK_BYTES = 65_536
MAX_HOST_CHARS = 253
SNIFF_BYTES = 2048

DEFAULT_PORTS = {"http": 80, "https": 443}
REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})
READABLE_TYPES = frozenset({"text/html", "application/xhtml+xml", "text/plain"})
HOST_PATTERN = re.compile(r"[a-z0-9._-]+")
META_CHARSET = re.compile(rb"charset\s*=\s*[\"']?([A-Za-z0-9_-]+)", re.IGNORECASE)
PATH_SAFE = "/%:@!$&'()*+,;=~-._"
USER_AGENT = "Mozilla/5.0 (compatible; CVAgent/1.0; fetches one job offer for its owner)"
REQUEST_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,text/plain;q=0.8",
    "Accept-Encoding": "identity",
    "Connection": "close",
}

INVALID_URL = "This is not a valid web link."
BLOCKED = (
    "This link cannot be fetched. Use the public address of the page, "
    "or paste the text of the offer."
)
UNREACHABLE = "The page could not be downloaded. Check the link, or paste the text of the offer."
REFUSED = (
    "The site refused automated access (a login or an anti-bot check is likely). "
    "Paste the text of the offer instead."
)
NOT_FOUND = "The page was not found. Check the link."
NOT_A_PAGE = "The link does not lead to a readable web page."
TOO_LARGE = "The page is too large."
TOO_SLOW = "The site answered too slowly."
TOO_MANY_REDIRECTS = "The link redirects too many times."
INVALID_REDIRECT = "The site redirected to an invalid address."

Resolver = Callable[[str, int], list[str]]
AddressCheck = Callable[[str], bool]
PortCheck = Callable[[str, int], bool]

_EXTRA_BLOCKED = tuple(
    ipaddress.ip_network(network) for network in ("64:ff9b::/96", "2002::/16", "2001::/32")
)


def is_public_address(address: str) -> bool:
    """True only for addresses that are reachable on the public internet."""
    try:
        ip = ipaddress.ip_address(address)
    except ValueError:
        return False
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    if not ip.is_global or ip.is_multicast:
        return False
    return not any(ip in network for network in _EXTRA_BLOCKED)


def is_default_port(scheme: str, port: int) -> bool:
    return DEFAULT_PORTS.get(scheme) == port


def system_resolver(host: str, port: int) -> list[str]:
    infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    return list(dict.fromkeys(str(info[4][0]) for info in infos))


@dataclass(frozen=True)
class Target:
    scheme: str
    host: str
    port: int
    path: str


def _split(url: str) -> SplitResult:
    if not url or len(url) > MAX_URL_CHARS:
        raise JobFetchError(INVALID_URL)
    if any(char.isspace() or not char.isprintable() for char in url):
        raise JobFetchError(INVALID_URL)
    try:
        return urlsplit(url)
    except ValueError as exc:
        raise JobFetchError(INVALID_URL) from exc


def _is_ip_literal(host: str) -> bool:
    try:
        ipaddress.ip_address(host)
    except ValueError:
        return False
    return True


def _ascii_host(hostname: str | None) -> str:
    if not hostname:
        raise JobFetchError(INVALID_URL)
    try:
        host = hostname.encode("idna").decode("ascii")
    except UnicodeError as exc:
        raise JobFetchError(INVALID_URL) from exc
    if len(host) > MAX_HOST_CHARS or not HOST_PATTERN.fullmatch(host):
        raise JobFetchError(INVALID_URL)
    if _is_ip_literal(host):
        raise JobFetchError(BLOCKED)
    return host


def _port_of(parts: SplitResult, scheme: str) -> int:
    try:
        port = parts.port
    except ValueError as exc:
        raise JobFetchError(INVALID_URL) from exc
    return port if port is not None else DEFAULT_PORTS[scheme]


def _request_path(parts: SplitResult) -> str:
    path = quote(parts.path or "/", safe=PATH_SAFE)
    if not parts.query:
        return path
    return f"{path}?{quote(parts.query, safe=PATH_SAFE + '?')}"


def parse_target(url: str, is_allowed_port: PortCheck) -> Target:
    """Check a web link and break it down. Raises JobFetchError if it is not acceptable."""
    parts = _split(url)
    scheme = parts.scheme.lower()
    if scheme not in DEFAULT_PORTS or "@" in parts.netloc:
        raise JobFetchError(INVALID_URL)
    host = _ascii_host(parts.hostname)
    port = _port_of(parts, scheme)
    if not is_allowed_port(scheme, port):
        raise JobFetchError(BLOCKED)
    return Target(scheme, host, port, _request_path(parts))


@functools.cache
def _tls_context() -> ssl.SSLContext:
    return ssl.create_default_context()


class _PinnedHTTPConnection(http.client.HTTPConnection):
    """Connects to an address that was already checked, whatever the name resolves to now."""

    def __init__(self, host: str, address: str, port: int, timeout: float) -> None:
        super().__init__(host, port, timeout=timeout)
        self._address = address

    def connect(self) -> None:
        self.sock = socket.create_connection((self._address, self.port), self.timeout)


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    """Like the plain version, with TLS checked against the real host name."""

    def __init__(
        self, host: str, address: str, port: int, timeout: float, context: ssl.SSLContext
    ) -> None:
        super().__init__(host, port, timeout=timeout, context=context)
        self._address = address
        self._tls = context

    def connect(self) -> None:
        raw = socket.create_connection((self._address, self.port), self.timeout)
        try:
            self.sock = self._tls.wrap_socket(raw, server_hostname=self.host)
        except OSError:
            raw.close()
            raise


Connector = Callable[[Target, str, float], http.client.HTTPConnection]


def pinned_connector(target: Target, address: str, timeout: float) -> http.client.HTTPConnection:
    if target.scheme == "https":
        return _PinnedHTTPSConnection(target.host, address, target.port, timeout, _tls_context())
    return _PinnedHTTPConnection(target.host, address, target.port, timeout)


@dataclass(frozen=True)
class _Reply:
    status: int
    location: str
    charset: str | None
    body: bytes


def _check_status(status: int) -> None:
    if status in (401, 403, 429):
        raise JobFetchError(REFUSED)
    if status in (404, 410):
        raise JobFetchError(NOT_FOUND)
    if status != 200:
        raise JobFetchError(f"The site answered with an error (code {status}).")


def _read_body(
    response: http.client.HTTPResponse,
    deadline: float,
    max_bytes: int,
    clock: Callable[[], float],
) -> bytes:
    chunks: list[bytes] = []
    total = 0
    while True:
        if clock() > deadline:
            raise JobFetchError(TOO_SLOW)
        chunk = response.read(CHUNK_BYTES)
        if not chunk:
            return b"".join(chunks)
        total += len(chunk)
        if total > max_bytes:
            raise JobFetchError(TOO_LARGE)
        chunks.append(chunk)


def _sniff_charset(body: bytes) -> str | None:
    match = META_CHARSET.search(body[:SNIFF_BYTES])
    return match.group(1).decode("ascii") if match else None


def _decode(reply: _Reply) -> str:
    charset = reply.charset or _sniff_charset(reply.body) or "utf-8"
    try:
        return reply.body.decode(charset, errors="replace")
    except LookupError:
        return reply.body.decode("utf-8", errors="replace")


def _next_url(current: str, location: str) -> str:
    if not location.strip():
        raise JobFetchError(INVALID_REDIRECT)
    return urljoin(current, location.strip())


class SafePageFetcher(PageFetcher):
    """Downloads one public web page, refusing anything that could reach an internal address."""

    def __init__(
        self,
        resolver: Resolver = system_resolver,
        is_allowed_address: AddressCheck = is_public_address,
        is_allowed_port: PortCheck = is_default_port,
        connector: Connector = pinned_connector,
        max_bytes: int = MAX_BYTES,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._resolver = resolver
        self._is_allowed_address = is_allowed_address
        self._is_allowed_port = is_allowed_port
        self._connector = connector
        self._max_bytes = max_bytes
        self._clock = clock

    def fetch(self, url: str) -> FetchedPage:
        deadline = self._clock() + TOTAL_TIMEOUT_SECONDS
        current = url
        for _ in range(MAX_REDIRECTS + 1):
            target = parse_target(current, self._is_allowed_port)
            reply = self._get(target, self._resolve_public(target), deadline)
            if reply.status not in REDIRECT_STATUSES:
                return FetchedPage(_decode(reply), current)
            current = _next_url(current, reply.location)
        raise JobFetchError(TOO_MANY_REDIRECTS)

    def _resolve_public(self, target: Target) -> list[str]:
        try:
            addresses = self._resolver(target.host, target.port)
        except (OSError, UnicodeError) as exc:
            raise JobFetchError(UNREACHABLE) from exc
        if not addresses or not all(self._is_allowed_address(a) for a in addresses):
            raise JobFetchError(BLOCKED)
        return addresses

    def _connect(self, target: Target, addresses: list[str]) -> http.client.HTTPConnection:
        for address in addresses:
            connection = self._connector(target, address, SOCKET_TIMEOUT_SECONDS)
            try:
                connection.connect()
            except OSError:
                connection.close()
                continue
            return connection
        raise JobFetchError(UNREACHABLE)

    def _get(self, target: Target, addresses: list[str], deadline: float) -> _Reply:
        connection = self._connect(target, addresses)
        try:
            connection.request("GET", target.path, headers=REQUEST_HEADERS)
            response = connection.getresponse()
            if response.status in REDIRECT_STATUSES:
                location = str(response.headers.get("Location") or "")
                return _Reply(response.status, location, None, b"")
            _check_status(response.status)
            self._check_content(response)
            body = _read_body(response, deadline, self._max_bytes, self._clock)
            return _Reply(response.status, "", response.headers.get_content_charset(), body)
        except (OSError, http.client.HTTPException) as exc:
            raise JobFetchError(UNREACHABLE) from exc
        finally:
            connection.close()

    @staticmethod
    def _check_content(response: http.client.HTTPResponse) -> None:
        if response.headers.get_content_type() not in READABLE_TYPES:
            raise JobFetchError(NOT_A_PAGE)
        encoding = str(response.headers.get("Content-Encoding") or "identity").strip().lower()
        if encoding not in ("", "identity"):
            raise JobFetchError(NOT_A_PAGE)
