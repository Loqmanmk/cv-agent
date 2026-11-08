from playwright.sync_api import Route, sync_playwright

from app.domain.pdf import PdfConverter

LOCAL_PREFIXES = ("data:", "about:")


def _allow_only_local(route: Route) -> None:
    """Our pages are fully self-contained, so any other request is an attack or a mistake."""
    if route.request.url.startswith(LOCAL_PREFIXES):
        route.continue_()
    else:
        route.abort()


class PlaywrightPdfConverter(PdfConverter):
    """Converts HTML to PDF with headless Chromium: no JavaScript and no network."""

    def to_pdf(self, html: str) -> bytes:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            try:
                context = browser.new_context(java_script_enabled=False, service_workers="block")
                context.route("**/*", _allow_only_local)
                page = context.new_page()
                page.set_content(html, wait_until="load")
                return page.pdf(prefer_css_page_size=True, print_background=True)
            finally:
                browser.close()
