import base64
import sys
import time
from pathlib import Path

import httpx

OUTPUT = Path("../data/output")
BASE_URL = "http://127.0.0.1:8000"


def main(cv_path: str, job_path: str) -> None:
    cv_file = Path(cv_path)
    created = httpx.post(
        f"{BASE_URL}/applications",
        files={"cv_file": (cv_file.name, cv_file.read_bytes())},
        data={"job_text": Path(job_path).read_text(encoding="utf-8")},
        timeout=420,
    )
    if created.status_code != 200:
        sys.exit(f"HTTP {created.status_code}: {created.text}")
    body = created.json()
    print(f"Created: {body['job_title']} at {body['company']}, photo used: {body['photo_used']}")

    edited_cv = body["cv"]
    edited_cv["profile"] = "PROFIL MODIFIÉ À LA MAIN (test du rendu)."
    started = time.perf_counter()
    rendered = httpx.post(
        f"{BASE_URL}/render",
        json={
            "cv": edited_cv,
            "letter": body["letter"],
            "language": body["language"],
            "photo_base64": body["photo_base64"],
        },
        timeout=120,
    )
    if rendered.status_code != 200:
        sys.exit(f"HTTP {rendered.status_code}: {rendered.text}")
    elapsed = time.perf_counter() - started

    result = rendered.json()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "rendered_cv.pdf").write_bytes(base64.b64decode(result["cv_pdf_base64"]))
    (OUTPUT / "rendered_letter.pdf").write_bytes(base64.b64decode(result["letter_pdf_base64"]))
    print(f"Rendered again in {elapsed:.1f} s with no AI call.")
    print(f"Saved to {OUTPUT / 'rendered_cv.pdf'} and {OUTPUT / 'rendered_letter.pdf'}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
