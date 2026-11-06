from pathlib import Path

from app.domain.cv import CV

DATA = Path("../data/extracted")


def show(title: str, before: list[str], after: list[str]) -> None:
    print(f"\n=== {title}")
    for line in before:
        print(f"  - {line}")
    print("  --->")
    for line in after:
        print(f"  + {line}")


def load(name: str) -> CV:
    return CV.model_validate_json((DATA / name).read_text(encoding="utf-8"))


def main() -> None:
    original = load("cv.json")
    tailored = load("tailored_cv.json")
    pairs = zip(original.experiences, tailored.experiences, strict=True)
    for before, after in pairs:
        show(f"{before.title} ({before.company})", before.bullets, after.bullets)
    kept = {project.title: project for project in tailored.projects}
    for project in original.projects:
        new = kept.get(project.title)
        show(project.title, project.bullets, new.bullets if new else ["(dropped)"])


if __name__ == "__main__":
    main()
