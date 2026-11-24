"""Parse downloaded corpus files and store pages or parse failures."""

import argparse
import asyncio
import json
from pathlib import Path

from patentpath.db.session import AsyncSessionLocal, engine
from patentpath.ingest.parse import ParseError, parse_file, parse_pdf_ocr
from patentpath.ingest.store import (
    document_id,
    failed_paths,
    parsed_ids,
    save_document,
    save_failure,
)

MANIFEST = Path("data/manifest.jsonl")


async def main(
    limit: int | None = None,
    retry_failed: bool = False,
) -> None:
    if not MANIFEST.exists():
        raise SystemExit(f"Manifest not found: {MANIFEST}")

    records = [
        json.loads(line)
        for line in MANIFEST.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    records = [r for r in records if r.get("status") == "downloaded"]

    parsed_count = failed_count = skipped_count = page_count = 0

    try:
        async with AsyncSessionLocal() as session:
            existing_ids = await parsed_ids(session)

            if retry_failed:
                failures = await failed_paths(session)
                records = [r for r in records if r["path"] in failures]

            if limit is not None:
                records = records[:limit]

            total = len(records)
            print(f"Files to process: {total}")
            if retry_failed:
                print("Mode: retry failed files only")

            for index, record in enumerate(records, start=1):
                path = Path(record["path"])

                try:
                    if document_id(record["sha256"]) in existing_ids:
                        skipped_count += 1
                        print(f"[{index}/{total}] SKIPPED {path}")
                        continue

                    if not path.is_file():
                        error = ParseError("missing_file", f"File not found: {path}")
                        await save_failure(session, record, error)
                        failed_count += 1
                        print(f"[{index}/{total}] FAILED {path}: {error.reason}")
                        continue

                    try:
                        parsed = parse_file(path)
                    except ParseError as error:
                        if error.reason != "no_text_layer" or path.suffix.lower() != ".pdf":
                            raise

                        print(f"[{index}/{total}] Trying OCR: {path}")
                        parsed = parse_pdf_ocr(path)

                    if not parsed.pages:
                        raise ParseError("empty", "Parser returned no pages")

                    await save_document(session, record, parsed)
                    parsed_count += 1
                    page_count += len(parsed.pages)
                    existing_ids.add(document_id(record["sha256"]))

                    print(
                        f"[{index}/{total}] OK {path} ({len(parsed.pages)} pages, {parsed.parser})"
                    )

                except ParseError as error:
                    await save_failure(session, record, error)
                    failed_count += 1
                    print(f"[{index}/{total}] FAILED {path}: {error.reason}")

                except Exception as error:
                    failure = ParseError(
                        "parse_error",
                        f"{type(error).__name__}: {error}",
                    )
                    await save_failure(session, record, failure)
                    failed_count += 1
                    print(f"[{index}/{total}] FAILED {path}: {failure.detail}")

                finally:
                    if index % 50 == 0 or index == total:
                        print(
                            f"PROGRESS {index}/{total} | "
                            f"parsed={parsed_count} "
                            f"failed={failed_count} "
                            f"skipped={skipped_count} "
                            f"pages={page_count}"
                        )

        print("\n--- Parsing summary ---")
        print(f"Total processed: {len(records)}")
        print(f"Parsed: {parsed_count}")
        print(f"Failed: {failed_count}")
        print(f"Pages created: {page_count}")
        print(f"Skipped: {skipped_count}")

    finally:
        await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Parse the downloaded corpus.")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument(
        "--retry-failed",
        action="store_true",
        help="Retry only files currently recorded in parse_failures.",
    )
    args = parser.parse_args()
    asyncio.run(main(args.limit, args.retry_failed))
