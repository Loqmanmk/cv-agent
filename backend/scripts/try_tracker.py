import base64
import json
from pathlib import Path

import httpx

DATA = Path("../data")
BASE_URL = "http://127.0.0.1:8000"


def load(name: str) -> object:
    return json.loads((DATA / "extracted" / name).read_text(encoding="utf-8"))


def main() -> None:
    photo = base64.b64encode((DATA / "extracted" / "image1.png").read_bytes()).decode("ascii")
    payload = {
        "job_title": "Stagiaire DataLab",
        "company": "Coface",
        "language": "fr",
        "source_url": "",
        "status": "saved",
        "cv": load("tailored_cv.json"),
        "letter": load("letter.json"),
        "photo_base64": photo,
    }
    with httpx.Client(base_url=BASE_URL, timeout=120) as client:
        saved = client.post("/tracker/applications", json=payload)
        saved.raise_for_status()
        application_id = saved.json()["id"]
        print(f"Saved as #{application_id}")

        client.patch(
            f"/tracker/applications/{application_id}",
            json={"status": "applied", "notes": "Sent through the website."},
        ).raise_for_status()

        for item in client.get("/tracker/applications").json():
            print(f"#{item['id']} {item['company']}: {item['job_title']} [{item['status']}]")

        pdf = client.get(f"/tracker/applications/{application_id}/cv.pdf")
        target = DATA / "output" / "tracker_cv.pdf"
        target.write_bytes(pdf.content)
        print(f"Downloaded {target}")


if __name__ == "__main__":
    main()
