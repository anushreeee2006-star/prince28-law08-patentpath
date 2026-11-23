import argparse
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "data" / "manifest.jsonl"
RAW = ROOT / "data" / "raw"
DATASET = ROOT / "DATASET.md"
CAPACITY = ROOT / "docs" / "CAPACITY.md"


def load_records():
    latest = {}
    if MANIFEST.exists():
        for line in MANIFEST.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                record = json.loads(line)
                if record.get("path"):
                    latest[record["path"]] = record
            except json.JSONDecodeError:
                continue
    return latest


def measure():
    records = load_records()
    files = []
    for path in sorted(RAW.rglob("*")):
        if not path.is_file() or path.suffix == ".part":
            continue

        relative = path.relative_to(ROOT).as_posix()
        record = records.get(relative, {})
        size = path.stat().st_size
        pages = 0
        words = 0
        text_chars = 0
        scanned = False

        if path.suffix.lower() == ".pdf":
            try:
                reader = PdfReader(str(path))
                pages = len(reader.pages)
                for page in reader.pages:
                    page_text = page.extract_text() or ""
                    text_chars += len(page_text)
                    words += len(page_text.split())
                scanned = pages > 0 and text_chars / pages < 50
            except Exception:
                scanned = True
        elif path.suffix.lower() in {
            ".md",
            ".mdx",
            ".txt",
            ".rst",
            ".adoc",
            ".html",
            ".htm",
            ".xml",
            ".csv",
            ".json",
            ".yaml",
            ".yml",
        }:
            try:
                content = path.read_text(encoding="utf-8", errors="replace")
                words = len(content.split())
                text_chars = len(content)
                pages = max(1, math.ceil(text_chars / 2500)) if content else 0
            except OSError:
                pass

        files.append(
            {
                "path": relative,
                "name": path.name,
                "source": record.get("source", "Unknown"),
                "url": record.get("url", ""),
                "licence": record.get("licence", "Not recorded"),
                "licence_status": record.get("licence_status", "unknown"),
                "extension": path.suffix.lower() or "[no extension]",
                "bytes": size,
                "pages": pages,
                "words": words,
                "text_chars": text_chars,
                "scanned": scanned,
            }
        )

    return files


def replace_generated(path, content, starter):
    old = path.read_text(encoding="utf-8") if path.exists() else starter

    start = "<!-- generated:start -->"
    end = "<!-- generated:end -->"
    if start not in old or end not in old:
        raise ValueError(f"Generated markers missing in {path}")

    before, remainder = old.split(start, 1)
    _, after = remainder.split(end, 1)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        before + start + "\n" + content.rstrip() + "\n" + end + after,
        encoding="utf-8",
    )


def main():
    parser = argparse.ArgumentParser(description="Measure PatentPath corpus and estimate capacity.")
    target = parser.add_mutually_exclusive_group()
    target.add_argument("--full-pages", type=int, default=5000)
    target.add_argument("--full-files", type=int)
    parser.add_argument("--embed-usd", type=float, default=0.20)
    parser.add_argument("--dims", type=int, default=1024)
    parser.add_argument("--chunk-tokens", type=int, default=500)
    parser.add_argument("--usd-inr", type=float, default=95)
    args = parser.parse_args()

    if min(args.embed_usd, args.usd_inr) < 0:
        parser.error("Prices and exchange rate cannot be negative.")
    if args.dims < 1 or args.chunk_tokens < 1:
        parser.error("--dims and --chunk-tokens must be positive.")
    if args.full_pages is not None and args.full_pages < 1:
        parser.error("--full-pages must be positive.")
    if args.full_files is not None and args.full_files < 1:
        parser.error("--full-files must be positive.")

    files = measure()
    if not files:
        parser.error("No files found under data/raw.")

    by_source = defaultdict(list)
    extensions = Counter()
    total_bytes = 0
    total_pages = 0
    total_words = 0
    scanned_count = 0

    for item in files:
        by_source[item["source"]].append(item)
        extensions[item["extension"]] += 1
        total_bytes += item["bytes"]
        total_pages += item["pages"]
        total_words += item["words"]
        scanned_count += int(item["scanned"])

    pdf_pages = sum(item["pages"] for item in files if item["extension"] == ".pdf")
    pdf_words = sum(item["words"] for item in files if item["extension"] == ".pdf")

    # Approximate tokens from extracted words; this is not a tokenizer measurement.
    tokens_per_page = round((pdf_words * 1.3) / pdf_pages) if pdf_pages else 0
    if not tokens_per_page:
        tokens_per_page = round((total_words * 1.3) / max(total_pages, 1))

    if args.full_files is not None:
        full_files = args.full_files
        scale = full_files / len(files)
        full_pages = round(total_pages * scale)
    else:
        full_pages = args.full_pages
        full_files = round(len(files) * full_pages / max(total_pages, 1))

    full_tokens = full_pages * tokens_per_page
    chunks = math.ceil(full_tokens / args.chunk_tokens) if full_tokens else 0
    embedding_usd = full_tokens / 1_000_000 * args.embed_usd
    embedding_inr = embedding_usd * args.usd_inr
    vector_bytes = chunks * args.dims * 4

    dataset_rows = [
        "| Source | Files | Size (MB) | Licence status |",
        "|---|---:|---:|---|",
    ]
    for source, items in sorted(by_source.items()):
        mb = sum(x["bytes"] for x in items) / (1024 * 1024)
        statuses = ", ".join(sorted({x["licence_status"] for x in items}))
        dataset_rows.append(f"| {source} | {len(items)} | {mb:.2f} | {statuses} |")

    extension_rows = [
        "| File type | Count |",
        "|---|---:|",
    ]
    extension_rows.extend(f"| {ext} | {count} |" for ext, count in sorted(extensions.items()))

    dataset_content = "\n".join(
        [
            "## Measured corpus",
            "",
            f"- **Files on disk:** {len(files)}",
            f"- **Measured pages / page equivalents:** {total_pages}",
            f"- **PDF pages:** {pdf_pages}",
            f"- **Total size:** {total_bytes / (1024 * 1024):.2f} MB",
            f"- **Scanned or almost-textless PDFs:** {scanned_count}",
            "",
            "### By source",
            "",
            *dataset_rows,
            "",
            "### By file type",
            "",
            *extension_rows,
            "",
            "### File inventory and licence",
            "",
            "| File | Source | Size (KB) | Licence / terms |",
            "|---|---|---:|---|",
            *[
                f"| `{x['path']}` | {x['source']} | {x['bytes'] / 1024:.1f} | {x['licence']} |"
                for x in files
            ],
        ]
    )

    capacity_content = "\n".join(
        [
            "## Measured corpus",
            "",
            f"- Files: {len(files)}",
            f"- Measured pages / page equivalents: {total_pages}",
            f"- PDF pages: {pdf_pages}",
            f"- Estimated tokens per page: {tokens_per_page:,}",
            "",
            "## Full corpus estimate",
            "",
            f"- Target: {full_pages:,} pages",
            f"- Estimated files: {full_files:,}",
            f"- Estimated tokens: {full_tokens / 1_000_000:.2f} million",
            f"- Estimated chunks: {chunks:,} at {args.chunk_tokens} tokens each",
            f"- Embedding cost: ${embedding_usd:.2f} (about Rs {embedding_inr:,.2f})",
            f"- Vector storage: {vector_bytes / (1024**2):.2f} MiB "
            f"({args.dims} dimensions, float32)",
            f"- Approximate raw text storage: "
            f"{(total_bytes / max(total_pages, 1) * full_pages) / (1024**2):.2f} MiB "
            "(scaled from current corpus)",
            "",
            "## Estimation assumptions",
            "",
            "- Tokens are estimated from extracted words (1.3 tokens per word), not a tokenizer.",
            "- Chunk count assumes non-overlapping chunks.",
            "- Vector storage excludes PostgreSQL indexes and metadata.",
            "- Embedding price and USD/INR rate are configurable estimates.",
        ]
    )

    dataset_starter = """# Dataset: PatentPath

Guides student inventors through Indian patent basics: patentability, procedure and fees.

- **Start target:** Act + Rules + Office Manual
- **Full target:** + CRI guidelines, fee schedules and 200 sample specifications (5,000+ pages)
- **Collected by:** `scripts/fetch.py`

## Where the documents come from

- https://ipindia.gov.in/
- https://iprsearch.ipindia.gov.in/
- https://github.com/fastapi/fastapi (tooling/reference corpus; licence verification pending)

## Terms I follow

Public law and office manuals, subject to the source's reuse conditions.

- Every answer links to the original document.
- No personal data is collected.

<!-- generated:start -->
<!-- generated:end -->

## Known gaps

- IPRSearch access and reuse terms remain unverified; automated collection is excluded.
- FastAPI repository licence must be checked before reuse in PatentPath answers.
- Confirm the full target's sample specifications are collected before claiming it is complete.
"""

    capacity_starter = """# Capacity plan: PatentPath

Full corpus target: + CRI guidelines, fee schedules and 200 sample specifications (5,000+ pages).

<!-- generated:start -->
<!-- generated:end -->

## What I conclude

1. Is embedding cost a problem? Consider the estimated INR cost and expected budget.
2. Do vectors and text fit in my free Postgres? Compare estimates with its storage allowance.
3. Which number above am I least sure about, and how will I measure it better?
4. What changes if the corpus grows 10 times? Consider chunks, cost, storage and retrieval speed.
"""

    replace_generated(DATASET, dataset_content, dataset_starter)
    replace_generated(CAPACITY, capacity_content, capacity_starter)

    print(f"files={len(files)} pages={total_pages} -> wrote DATASET.md and docs/CAPACITY.md")


if __name__ == "__main__":
    main()
