import sys
from pathlib import Path

from app.infrastructure.docx_parser import DocxParser

OUTPUT_DIR = Path("../data/extracted")


def main(path: str) -> None:
    result = DocxParser().parse(Path(path).read_bytes())
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print(result.text)
    print(f"\n--- {len(result.images)} image(s) found")
    for index, image in enumerate(result.images, start=1):
        target = OUTPUT_DIR / f"image{index}{image.extension}"
        target.write_bytes(image.data)
        print(f"{target} ({image.width}x{image.height})")


if __name__ == "__main__":
    main(sys.argv[1])
