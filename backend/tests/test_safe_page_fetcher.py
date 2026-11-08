import socket
import threading
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

import pytest

from app.domain.job_source import JobFetchError
from app.infrastructure.safe_page_fetcher import (
    BLOCKED,
    INVALID_URL,
    NOT_A_PAGE,
    NOT_FOUND,
    REFUSED,
    TOO_LARGE,
    TOO_MANY_REDIRECTS,
    TOO_SLOW,
    UNREACHABLE,
    SafePageFetcher,
)

Route = tuple[int, dict[str, str], bytes]
HTML = {"Content-Type": "text/html; charset=utf-8"}
DEFAULT_TABLE = {
    "good.test": ["127.0.0.1"],
    "evil.test": ["10.0.0.1"],
    "mixed.test": ["127.0.0.1", "10.0.0.1"],
}


@dataclass
class LocalSite:
    port: int
    requests: list[dict[str, str]] = field(default_factory=list)

    def url(self, path: str = "/", host: str = "good.test") -> str:
        return f"http://{host}:{self.port}{path}"


class Resolutions:
    def __init__(self, table: dict[str, list[str]] | None = None) -> None:
        self.table = DEFAULT_TABLE if table is None else table
        self.calls: list[str] = []

    def __call__(self, host: str, port: int) -> list[str]:
        self.calls.append(host)
        if host not in self.table:
            raise socket.gaierror("unknown host")
        return self.table[host]


def start_site(routes: dict[str, Route]) -> tuple[ThreadingHTTPServer, LocalSite]:
    seen: list[dict[str, str]] = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            seen.append(
                {
                    "host": self.headers.get("Host", ""),
                    "agent": self.headers.get("User-Agent", ""),
                    "path": self.path,
                }
            )
            status, headers, body = routes.get(self.path, (404, {}, b"missing"))
            self.send_response(status)
            for key, value in headers.items():
                self.send_header(key, value)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: Any) -> None:
            return None

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, LocalSite(server.server_address[1], seen)


@pytest.fixture
def serve() -> Iterator[Callable[[dict[str, Route]], LocalSite]]:
    servers: list[ThreadingHTTPServer] = []

    def start(routes: dict[str, Route]) -> LocalSite:
        server, site = start_site(routes)
        servers.append(server)
        return site

    yield start
    for server in servers:
        server.shutdown()
        server.server_close()


def make_fetcher(
    resolver: Callable[[str, int], list[str]] | None = None,
    max_bytes: int = 1_000_000,
) -> SafePageFetcher:
    return SafePageFetcher(
        resolver=resolver or Resolutions(),
        is_allowed_address=lambda address: address == "127.0.0.1",
        is_allowed_port=lambda scheme, port: True,
        max_bytes=max_bytes,
    )


def error_of(fetcher: SafePageFetcher, url: str) -> str:
    with pytest.raises(JobFetchError) as raised:
        fetcher.fetch(url)
    return str(raised.value)


def test_returns_the_page_and_its_address(serve: Callable[[dict[str, Route]], LocalSite]) -> None:
    site = serve({"/job": (200, HTML, b"<html>Hello</html>")})

    page = make_fetcher().fetch(site.url("/job"))

    assert page.html == "<html>Hello</html>"
    assert page.final_url == site.url("/job")


def test_the_request_keeps_the_real_host_name_and_an_honest_agent(
    serve: Callable[[dict[str, Route]], LocalSite],
) -> None:
    site = serve({"/": (200, HTML, b"ok")})

    make_fetcher().fetch(site.url())

    assert site.requests[0]["host"] == f"good.test:{site.port}"
    assert "CVAgent" in site.requests[0]["agent"]


def test_the_name_is_resolved_once_and_the_checked_address_is_used(
    serve: Callable[[dict[str, Route]], LocalSite],
) -> None:
    site = serve({"/": (200, HTML, b"ok")})
    answers = iter([["127.0.0.1"], ["10.0.0.1"]])
    calls: list[str] = []

    def rebinding(host: str, port: int) -> list[str]:
        calls.append(host)
        return next(answers)

    page = make_fetcher(rebinding).fetch(site.url())

    assert page.html == "ok"
    assert calls == ["good.test"]


def test_a_redirect_is_followed(serve: Callable[[dict[str, Route]], LocalSite]) -> None:
    site = serve(
        {
            "/old": (301, {"Location": "/new"}, b""),
            "/new": (200, HTML, b"new page"),
        }
    )

    page = make_fetcher().fetch(site.url("/old"))

    assert page.html == "new page"
    assert page.final_url == site.url("/new")


def test_a_redirect_to_an_internal_host_is_blocked_before_connecting(
    serve: Callable[[dict[str, Route]], LocalSite],
) -> None:
    routes: dict[str, Route] = {}
    site = serve(routes)
    routes["/go"] = (302, {"Location": site.url("/secret", "evil.test")}, b"")
    routes["/secret"] = (200, HTML, b"secret")

    message = error_of(make_fetcher(), site.url("/go"))

    assert message == BLOCKED
    assert [request["path"] for request in site.requests] == ["/go"]


def test_a_redirect_to_a_forbidden_scheme_is_refused(
    serve: Callable[[dict[str, Route]], LocalSite],
) -> None:
    site = serve({"/go": (302, {"Location": "ftp://good.test/file"}, b"")})

    assert error_of(make_fetcher(), site.url("/go")) == INVALID_URL


def test_a_redirect_without_a_destination_is_refused(
    serve: Callable[[dict[str, Route]], LocalSite],
) -> None:
    site = serve({"/go": (302, {}, b"")})

    assert "invalid address" in error_of(make_fetcher(), site.url("/go"))


def test_endless_redirects_are_stopped(serve: Callable[[dict[str, Route]], LocalSite]) -> None:
    site = serve({"/loop": (302, {"Location": "/loop"}, b"")})

    assert error_of(make_fetcher(), site.url("/loop")) == TOO_MANY_REDIRECTS


def test_a_host_that_resolves_to_an_internal_address_is_never_contacted(
    serve: Callable[[dict[str, Route]], LocalSite],
) -> None:
    site = serve({"/": (200, HTML, b"internal")})

    message = error_of(make_fetcher(), site.url(host="evil.test"))

    assert message == BLOCKED
    assert site.requests == []


def test_one_internal_address_among_public_ones_blocks_the_host(
    serve: Callable[[dict[str, Route]], LocalSite],
) -> None:
    site = serve({"/": (200, HTML, b"mixed")})

    assert error_of(make_fetcher(), site.url(host="mixed.test")) == BLOCKED
    assert site.requests == []


def test_an_unknown_host_is_unreachable(serve: Callable[[dict[str, Route]], LocalSite]) -> None:
    site = serve({})

    assert error_of(make_fetcher(), site.url(host="nowhere.test")) == UNREACHABLE


def test_a_closed_port_is_unreachable() -> None:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]

    assert error_of(make_fetcher(), f"http://good.test:{port}/") == UNREACHABLE


@pytest.mark.parametrize(
    ("status", "expected"),
    [(401, REFUSED), (403, REFUSED), (429, REFUSED), (404, NOT_FOUND), (410, NOT_FOUND)],
)
def test_http_errors_become_clear_messages(
    serve: Callable[[dict[str, Route]], LocalSite], status: int, expected: str
) -> None:
    site = serve({"/": (status, HTML, b"no")})

    assert error_of(make_fetcher(), site.url()) == expected


def test_other_errors_report_the_status_code(
    serve: Callable[[dict[str, Route]], LocalSite],
) -> None:
    site = serve({"/": (500, HTML, b"boom")})

    assert "code 500" in error_of(make_fetcher(), site.url())


def test_a_page_that_is_not_html_is_refused(
    serve: Callable[[dict[str, Route]], LocalSite],
) -> None:
    site = serve({"/": (200, {"Content-Type": "application/pdf"}, b"%PDF-1.4")})

    assert error_of(make_fetcher(), site.url()) == NOT_A_PAGE


def test_a_compressed_answer_is_refused(serve: Callable[[dict[str, Route]], LocalSite]) -> None:
    headers = {"Content-Type": "text/html", "Content-Encoding": "gzip"}
    site = serve({"/": (200, headers, b"\x1f\x8b not really gzip")})

    assert error_of(make_fetcher(), site.url()) == NOT_A_PAGE


def test_a_page_over_the_size_limit_is_refused(
    serve: Callable[[dict[str, Route]], LocalSite],
) -> None:
    site = serve({"/": (200, HTML, b"x" * 1000)})

    assert error_of(make_fetcher(max_bytes=100), site.url()) == TOO_LARGE


def test_a_download_that_takes_too_long_is_stopped(
    serve: Callable[[dict[str, Route]], LocalSite],
) -> None:
    site = serve({"/": (200, HTML, b"<html>" + b"x" * 1000)})
    ticks = iter([0.0])
    fetcher = SafePageFetcher(
        resolver=Resolutions(),
        is_allowed_address=lambda address: address == "127.0.0.1",
        is_allowed_port=lambda scheme, port: True,
        clock=lambda: next(ticks, 1000.0),
    )

    assert error_of(fetcher, site.url()) == TOO_SLOW


def test_the_charset_of_the_header_is_used(
    serve: Callable[[dict[str, Route]], LocalSite],
) -> None:
    headers = {"Content-Type": "text/html; charset=iso-8859-1"}
    site = serve({"/": (200, headers, "Café".encode("latin-1"))})

    assert make_fetcher().fetch(site.url()).html == "Café"


def test_the_charset_is_read_from_the_page_when_the_header_has_none(
    serve: Callable[[dict[str, Route]], LocalSite],
) -> None:
    body = b'<meta charset="iso-8859-1">' + "Café".encode("latin-1")
    site = serve({"/": (200, {"Content-Type": "text/html"}, body)})

    assert make_fetcher().fetch(site.url()).html.endswith("Café")


def test_an_unknown_charset_falls_back_to_utf8(
    serve: Callable[[dict[str, Route]], LocalSite],
) -> None:
    headers = {"Content-Type": "text/html; charset=nonsense"}
    site = serve({"/": (200, headers, "Café".encode())})

    assert make_fetcher().fetch(site.url()).html == "Café"


def test_a_link_that_is_not_acceptable_is_refused_without_a_lookup() -> None:
    resolutions = Resolutions()

    assert error_of(make_fetcher(resolutions), "ftp://good.test/") == INVALID_URL
    assert resolutions.calls == []


def test_the_default_policy_blocks_the_local_machine() -> None:
    assert error_of(SafePageFetcher(), "http://localhost/") == BLOCKED
    assert error_of(SafePageFetcher(), "http://127.0.0.1/") == BLOCKED


def test_the_default_policy_blocks_other_ports_without_a_lookup() -> None:
    assert error_of(SafePageFetcher(), "http://example.com:6379/") == BLOCKED


@pytest.mark.parametrize(
    "url",
    ["http://2130706433/", "http://0x7f.0.0.1/", "http://017700000001/"],
)
def test_numeric_tricks_for_the_local_machine_never_succeed(url: str) -> None:
    with pytest.raises(JobFetchError):
        SafePageFetcher().fetch(url)
