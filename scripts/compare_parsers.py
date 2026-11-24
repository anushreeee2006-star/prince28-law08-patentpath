import csv
import time
from pathlib import Path

from patentpath.ingest.parse import (
    ParseError,
    parse_pdf_pymupdf,
    parse_pdf_pypdf,
)

ROOT = Path(__file__).resolve().parents[1]
PDF_DIR = ROOT / "data" / "raw"
OUTPUT = ROOT / "data" / "parser_comparison.csv"

files = sorted(
    PDF_DIR.rglob("*.pdf"),
    key=lambda path: path.stat().st_size,
    reverse=True,
)[:10]


def parse_pymupdf_for_comparison(path: Path):
    if path.name == "epo-guidelines-2026.pdf":
        return parse_pdf_pymupdf(path, extract_tables=False)
    return parse_pdf_pymupdf(path)


results = []

for index, path in enumerate(files, 1):
    print(f"\n[{index}/10] {path.relative_to(ROOT)}")

    for parser_name, parser in [
        ("pymupdf", parse_pymupdf_for_comparison),
        ("pypdf", parse_pdf_pypdf),
    ]:
        started = time.perf_counter()

        try:
            doc = parser(path)
            elapsed = time.perf_counter() - started
            pages = len(doc.pages)
            chars = sum(len(page.text) for page in doc.pages)
            headings = sum(len(page.headings) for page in doc.pages)
            tables = sum(page.tables for page in doc.pages)

            result = {
                "file": str(path.relative_to(ROOT)),
                "parser": parser_name,
                "status": "success",
                "pages": pages,
                "characters": chars,
                "headings": headings,
                "tables": tables,
                "seconds": round(elapsed, 3),
                "error": "",
            }

        except ParseError as exc:
            elapsed = time.perf_counter() - started
            result = {
                "file": str(path.relative_to(ROOT)),
                "parser": parser_name,
                "status": "failed",
                "pages": 0,
                "characters": 0,
                "headings": 0,
                "tables": 0,
                "seconds": round(elapsed, 3),
                "error": str(exc),
            }

        except Exception as exc:
            elapsed = time.perf_counter() - started
            result = {
                "file": str(path.relative_to(ROOT)),
                "parser": parser_name,
                "status": "failed",
                "pages": 0,
                "characters": 0,
                "headings": 0,
                "tables": 0,
                "seconds": round(elapsed, 3),
                "error": str(exc),
            }

        results.append(result)
        print(
            f"  {parser_name}: {result['status']}, "
            f"pages={result['pages']}, chars={result['characters']}, "
            f"time={result['seconds']}s" + (f", error={result['error']}" if result["error"] else "")
        )

OUTPUT.parent.mkdir(parents=True, exist_ok=True)

with OUTPUT.open("w", newline="", encoding="utf-8") as file:
    writer = csv.DictWriter(file, fieldnames=results[0].keys())
    writer.writeheader()
    writer.writerows(results)

print(f"\nComparison saved to: {OUTPUT}")
print(f"Files compared: {len(files)}")
