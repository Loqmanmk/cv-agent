import trafilatura

from app.domain.job_source import JobTextExtractor


class TrafilaturaExtractor(JobTextExtractor):
    """Extracts the main text of a web page, without menus, footers or scripts."""

    def extract(self, html: str) -> str:
        text = trafilatura.extract(
            html,
            include_comments=False,
            include_tables=True,
            favor_recall=True,
        )
        return str(text) if text else ""
