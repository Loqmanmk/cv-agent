import base64
import sys
from pathlib import Path

import httpx

OUTPUT = Path("../data/output")
BASE_URL = "http://127.0.0.1:8000"


def main(cv_path: str, job_path: str) -> None:
    cv_file = Path(cv_path)
    response = httpx.post(
        f"{BASE_URL}/applications",
        files={"cv_file": (cv_file.name, cv_file.read_bytes())},
        data={"job_text": Path(job_path).read_text(encoding="utf-8")},
        timeout=420,
    )
    if response.status_code != 200:
        sys.exit(f"HTTP {response.status_code}: {response.text}")

    body = response.json()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "api_cv.pdf").write_bytes(base64.b64decode(body["cv_pdf_base64"]))
    (OUTPUT / "api_letter.pdf").write_bytes(base64.b64decode(body["letter_pdf_base64"]))
    print(f"{body['job_title']} at {body['company']} ({body['language']})")
    print(f"Photo used: {body['photo_used']}")
    print(f"Saved to {OUTPUT / 'api_cv.pdf'} and {OUTPUT / 'api_letter.pdf'}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
