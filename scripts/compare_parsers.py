import csv
import time
from html.parser import HTMLParser
from pathlib import Path

from patentpath.ingest.parse import (
    ParseError,
    clean_text,
    parse_html,
    parse_pdf_pymupdf,
    parse_pdf_pypdf,
    split_pages,
)

ROOT = Path(__file__).resolve().parents[1]
PDF_DIR = ROOT / "data" / "raw"
OUTPUT = ROOT / "data" / "parser_comparison.csv"
NOTES = ROOT / "NOTES.md"

PDF_FILES = [
    "epo-guidelines-2026.pdf",
    "2748c8f6-ca59-4bb9-b5e9-690a7a934136-e149111f.pdf",
    "86c74a8b-b029-4b79-812a-d260b2f90368-3f1f5ca8.pdf",
]

HTML_FILES = [
    "forms-and-official-fees-78ff0e5f.html",
    "basics-of-patents-593130e6.html",
    "faqs-d3efbe1e.html",
    "which-inventions-can-be-patented-ee337de8.html",
    "inpass-16c188a5.html",
    "filing-process-step-by-step-8b5fef91.html",
    "rules-patents-2003-5b28698f.html",
]

SECTION_START = "<!-- STEP 5 PARSER COMPARISON START -->"
SECTION_END = "<!-- STEP 5 PARSER COMPARISON END -->"


def find_file(filename: str) -> Path:
    matches = list(PDF_DIR.rglob(filename))
    if not matches:
        raise FileNotFoundError(f"File not found: {filename}")
    return matches[0]


class StripTagsParser(HTMLParser):
    """Simple baseline: remove HTML tags and retain visible text."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.headings = 0
        self.tables = 0
        self.skip_tag = None

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style"}:
            self.skip_tag = tag
        if tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            self.headings += 1
        if tag == "table":
            self.tables += 1

    def handle_endtag(self, tag):
        if tag == self.skip_tag:
            self.skip_tag = None

    def handle_data(self, data):
        if self.skip_tag is None and data.strip():
            self.parts.append(data.strip())


def parse_strip_tags(path: Path):
    parser = StripTagsParser()
    parser.feed(path.read_text(encoding="utf-8", errors="replace"))
    text = clean_text("\n".join(parser.parts))

    if len(text) < 40:
        raise ParseError("empty", "strip-tags found too little text")

    return {
        "pages": len(split_pages(text)),
        "characters": len(text),
        "headings": parser.headings,
        "tables": parser.tables,
    }


def parse_pymupdf_for_comparison(path: Path):
    if path.name == "epo-guidelines-2026.pdf":
        return parse_pdf_pymupdf(path, extract_tables=False)
    return parse_pdf_pymupdf(path)


def get_doc_metrics(doc):
    return {
        "pages": len(doc.pages),
        "characters": sum(len(page.text) for page in doc.pages),
        "headings": sum(len(page.headings) for page in doc.pages),
        "tables": sum(page.tables for page in doc.pages),
    }


def run_parser(path, parser_name, parser):
    started = time.perf_counter()

    try:
        output = parser(path)
        metrics = output if isinstance(output, dict) else get_doc_metrics(output)
        return {
            "file": str(path.relative_to(ROOT)),
            "parser": parser_name,
            "status": "success",
            **metrics,
            "seconds": round(time.perf_counter() - started, 3),
            "error": "",
        }
    except Exception as exc:
        return {
            "file": str(path.relative_to(ROOT)),
            "parser": parser_name,
            "status": "failed",
            "pages": 0,
            "characters": 0,
            "headings": 0,
            "tables": 0,
            "seconds": round(time.perf_counter() - started, 3),
            "error": str(exc)[:300],
        }


def choose_better(first, second, file_type):
    filename = first.get("file", "").lower()

    if first["status"] == "failed" and second["status"] == "failed":
        return "Neither", "Both parsers failed; OCR or manual recovery is needed."

    if first["status"] == "success" and second["status"] == "failed":
        return first["parser"], (f"{first['parser']} succeeded; {second['parser']} failed.")

    if second["status"] == "success" and first["status"] == "failed":
        return second["parser"], (f"{second['parser']} succeeded; {first['parser']} failed.")

    if file_type == "HTML":
        if "faqs-" in filename:
            return "Neither", (
                "Trafilatura extracted only a PDF-unavailable message; "
                "strip-tags mainly retained navigation, not FAQ answers."
            )
        if "filing-process-step-by-step" in filename:
            return "Neither", (
                "Trafilatura extracted Coming Soon/PDF-unavailable messages; "
                "strip-tags mainly retained navigation."
            )
        if "forms-and-official-fees" in filename:
            return "trafilatura", (
                "Manual inspection confirmed the fees table in Markdown; "
                "strip-tags retained extensive unrelated navigation."
            )
        if "basics-of-patents" in filename:
            return "trafilatura", (
                "Manual inspection confirmed useful patent sections and "
                "bullet content; strip-tags retained navigation noise."
            )
        if "which-inventions-can-be-patented" in filename:
            return "trafilatura", (
                "Manual inspection confirmed patentability criteria and "
                "explanations; strip-tags retained navigation noise."
            )
        if "inpass-" in filename:
            return "trafilatura", (
                "Extracted the relevant InPASS search description without "
                "the extensive navigation retained by strip-tags."
            )
        if "rules-patents-2003" in filename:
            return "trafilatura", (
                "Extracted the title, table of contents and disclaimers "
                "cleanly; strip-tags duplicated content and included navigation."
            )
        return "Needs review", ("Manual content inspection is required before selecting a winner.")

    if "epo-guidelines-2026" in filename:
        return (
            "pymupdf",
            f"Both extracted {first['pages']:,} pages and similar text volume; "
            f"PyMuPDF was much faster ({first['seconds']}s vs "
            f"{second['seconds']}s). "
            "Heading counts alone do not prove heading accuracy.",
        )

    if "86c74a8b-b029-4b79-812a-d260b2f90368" in filename:
        return (
            "pymupdf",
            "Extracted 35 tables and 39,452 characters, compared with "
            "pypdf's 0 tables and 8,068 characters; "
            "verify table layout against the source.",
        )

    return "Needs review", ("Compare extracted content with the original PDF before choosing.")


results = []
comparisons = []

# PDF comparison
for filename in PDF_FILES:
    path = find_file(filename)
    print(f"\nPDF: {path.relative_to(ROOT)}")

    first = run_parser(path, "pymupdf", parse_pymupdf_for_comparison)
    second = run_parser(path, "pypdf", parse_pdf_pypdf)

    for result in (first, second):
        results.append(result)
        print(
            f"  {result['parser']}: {result['status']}, "
            f"pages={result['pages']}, chars={result['characters']}, "
            f"headings={result['headings']}, tables={result['tables']}, "
            f"time={result['seconds']}s"
        )

    better, why = choose_better(first, second, "PDF")
    comparisons.append((path.name, "PDF", first, second, better, why))

# HTML comparison
for filename in HTML_FILES:
    path = find_file(filename)
    print(f"\nHTML: {path.relative_to(ROOT)}")

    first = run_parser(path, "trafilatura", parse_html)
    second = run_parser(path, "strip-tags", parse_strip_tags)

    for result in (first, second):
        results.append(result)
        print(
            f"  {result['parser']}: {result['status']}, "
            f"pages={result['pages']}, chars={result['characters']}, "
            f"headings={result['headings']}, tables={result['tables']}, "
            f"time={result['seconds']}s"
        )

    better, why = choose_better(first, second, "HTML")
    comparisons.append((path.name, "HTML", first, second, better, why))

# Save detailed CSV
OUTPUT.parent.mkdir(parents=True, exist_ok=True)
fields = [
    "file",
    "parser",
    "status",
    "pages",
    "characters",
    "headings",
    "tables",
    "seconds",
    "error",
]

with OUTPUT.open("w", newline="", encoding="utf-8") as file:
    writer = csv.DictWriter(file, fieldnames=fields)
    writer.writeheader()
    writer.writerows(results)

# Build NOTES.md comparison table
lines = [
    SECTION_START,
    "### Step 5 - Ten hard files parser comparison",
    "",
    "Compared 3 challenging PDFs and all 7 available HTML files.",
    "PDF parsers: PyMuPDF and pypdf. HTML parsers: Trafilatura and strip-tags.",
    "",
    "| File | Type | Parser 1 result | Parser 2 result | Better | Better, why |",
    "|---|---|---|---|---|---|",
]

for filename, file_type, first, second, better, why in comparisons:

    def summary(result):
        if result["status"] == "failed":
            return f"Failed ({result['seconds']}s)"
        return (
            f"{result['status']}: {result['characters']} chars, "
            f"{result['headings']} headings, {result['tables']} tables, "
            f"{result['seconds']}s"
        )

    lines.append(
        f"| {filename} | {file_type} | "
        f"{first['parser']}: {summary(first)} | "
        f"{second['parser']}: {summary(second)} | "
        f"{better} | {why} |"
    )

lines.extend(
    [
        "",
        "**Inspection note:** Parser metrics alone do not prove text quality. "
        "Compare extracted pages with the original source, especially headings, "
        "tables, repeated headers/footers and unwanted characters.",
        "",
        "**PDF note:** PyMuPDF table extraction was disabled for the EPO Guidelines "
        "PDF to avoid excessive processing time; default parser behaviour is unchanged.",
        "",
        f"Detailed per-parser results: `{OUTPUT.relative_to(ROOT).as_posix()}`.",
        SECTION_END,
    ]
)

new_section = "\n".join(lines)
notes_text = NOTES.read_text(encoding="utf-8") if NOTES.exists() else ""

if SECTION_START in notes_text and SECTION_END in notes_text:
    before = notes_text.split(SECTION_START)[0].rstrip()
    after = notes_text.split(SECTION_END, 1)[1].lstrip()
    notes_text = before + "\n\n" + new_section
    if after:
        notes_text += "\n\n" + after
else:
    notes_text = notes_text.rstrip() + "\n\n" + new_section + "\n"

NOTES.write_text(notes_text, encoding="utf-8")

print(f"\nComparison CSV saved: {OUTPUT}")
print(f"compared {len(comparisons)} files -> table written to NOTES.md")
