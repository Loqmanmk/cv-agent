import pytest

from app.domain.job_source import JobFetchError
from app.infrastructure.safe_page_fetcher import (
    BLOCKED,
    INVALID_URL,
    MAX_URL_CHARS,
    Target,
    is_default_port,
    parse_target,
)


def parse(url: str) -> Target:
    return parse_target(url, is_default_port)


def test_a_normal_link_is_broken_down_and_the_fragment_is_dropped() -> None:
    assert parse("https://example.com/jobs/1?id=2#top") == Target(
        "https", "example.com", 443, "/jobs/1?id=2"
    )


def test_scheme_and_host_are_lowercased_and_the_path_defaults_to_a_slash() -> None:
    assert parse("HTTP://Example.COM") == Target("http", "example.com", 80, "/")


def test_non_ascii_path_characters_are_escaped() -> None:
    assert parse("https://example.com/é").path == "/%C3%A9"


def test_an_international_host_name_becomes_ascii() -> None:
    assert parse("https://bücher.example/").host == "xn--bcher-kva.example"


def test_an_existing_percent_escape_is_kept() -> None:
    assert parse("https://example.com/a%20b").path == "/a%20b"


@pytest.mark.parametrize(
    "url",
    [
        "",
        "example.com",
        "ftp://example.com/",
        "file:///etc/passwd",
        "javascript:alert(1)",
        "https://user:secret@example.com/",
        "https://@example.com/",
        "https://example.com:99999/",
        "https:///path",
        "https://exa mple.com/",
        "https://example.com/\n",
        "https://example.com/\x00",
        "https://exa%6Dple.com/",
        "https://exa..mple.com/",
        "http://[::1]/",
        "https://example.com/" + "a" * MAX_URL_CHARS,
    ],
)
def test_links_that_are_not_acceptable_are_refused(url: str) -> None:
    with pytest.raises(JobFetchError) as raised:
        parse(url)

    assert str(raised.value) == INVALID_URL or str(raised.value) == BLOCKED


@pytest.mark.parametrize(
    "url",
    ["http://127.0.0.1/", "http://10.0.0.1/", "https://169.254.169.254/latest/meta-data/"],
)
def test_links_made_of_an_ip_address_are_refused(url: str) -> None:
    with pytest.raises(JobFetchError) as raised:
        parse(url)

    assert str(raised.value) == BLOCKED


@pytest.mark.parametrize(
    "url",
    ["http://example.com:6379/", "https://example.com:8443/", "http://example.com:0/"],
)
def test_ports_other_than_the_default_are_refused(url: str) -> None:
    with pytest.raises(JobFetchError) as raised:
        parse(url)

    assert str(raised.value) == BLOCKED


def test_the_port_rule_can_be_replaced() -> None:
    target = parse_target("http://example.com:8080/", lambda scheme, port: True)

    assert target.port == 8080
