from playwright.sync_api import sync_playwright

from app.domain.pdf import PdfConverter


class PlaywrightPdfConverter(PdfConverter):
    """Converts HTML to PDF with headless Chromium (JavaScript disabled)."""

    def to_pdf(self, html: str) -> bytes:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            try:
                context = browser.new_context(java_script_enabled=False)
                page = context.new_page()
                page.set_content(html, wait_until="load")
                return page.pdf(prefer_css_page_size=True, print_background=True)
            finally:
                browser.close()
