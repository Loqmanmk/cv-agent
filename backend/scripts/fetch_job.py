import sys
from pathlib import Path

from app.domain.job_source import JobFetchError
from app.infrastructure.application_factory import build_job_fetch_service

OUTPUT = Path("../data/job_from_url.txt")
PREVIEW_CHARS = 600


def main(url: str) -> None:
    try:
        result = build_job_fetch_service().fetch_text(url)
    except JobFetchError as error:
        sys.exit(f"Failed: {error}")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(result.text, encoding="utf-8")
    print(f"Saved {len(result.text)} characters to {OUTPUT} (truncated: {result.truncated})")
    print(f"Source: {result.source_url}\n")
    print(result.text[:PREVIEW_CHARS])


if __name__ == "__main__":
    main(sys.argv[1])
