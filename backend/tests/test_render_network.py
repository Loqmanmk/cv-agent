from collections.abc import Iterator
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from typing import Any

import pytest
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright

from app.infrastructure.pdf_converter import PlaywrightPdfConverter
from app.infrastructure.pdf_page_counter import PyMuPdfPageCounter


@contextmanager
def local_server() -> Iterator[tuple[int, list[str]]]:
    hits: list[str] = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            hits.append(self.path)
            self.send_response(200)
            self.send_header("Content-Type", "text/css")
            self.end_headers()
            self.wfile.write(b"p { color: red }")

        def log_message(self, format: str, *args: Any) -> None:
            return None

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    Thread(target=server.serve_forever, daemon=True).start()
    try:
        yield server.server_address[1], hits
    finally:
        server.shutdown()
        server.server_close()


def page_calling(port: int) -> str:
    return (
        "<html><head>"
        f'<link rel="stylesheet" href="http://127.0.0.1:{port}/style.css">'
        f"</head><body><p>Hello</p><img src='http://127.0.0.1:{port}/pixel.png'></body></html>"
    )


def test_a_normal_browser_would_call_the_server_so_the_test_is_meaningful() -> None:
    with local_server() as (port, hits):
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch()
                page = browser.new_page()
                page.set_content(page_calling(port), wait_until="load")
                browser.close()
        except PlaywrightError:
            pytest.skip("Chromium is not installed: run 'uv run playwright install chromium'")

    assert hits != []


def test_the_render_browser_never_calls_the_network() -> None:
    with local_server() as (port, hits):
        try:
            pdf = PlaywrightPdfConverter().to_pdf(page_calling(port))
        except PlaywrightError:
            pytest.skip("Chromium is not installed: run 'uv run playwright install chromium'")

    assert hits == []
    assert PyMuPdfPageCounter().count(pdf) == 1


def test_inline_data_images_still_work() -> None:
    pixel = "data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7"
    html = f"<html><body><p>Hello</p><img src='{pixel}'></body></html>"

    try:
        pdf = PlaywrightPdfConverter().to_pdf(html)
    except PlaywrightError:
        pytest.skip("Chromium is not installed: run 'uv run playwright install chromium'")

    assert pdf.startswith(b"%PDF")
