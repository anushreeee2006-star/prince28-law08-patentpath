"""Command-line entry point for duplicate detection."""

import argparse
import json
from pathlib import Path

from patentpath.ingest.duplicates import find_duplicates


def main() -> None:
    parser = argparse.ArgumentParser(description="Find duplicate downloaded files using SHA-256.")
    parser.add_argument("--manifest", type=Path, default=Path("data/manifest.jsonl"))
    parser.add_argument("--output", type=Path, default=Path("data/duplicate_report.json"))
    args = parser.parse_args()

    duplicates = find_duplicates(args.manifest)
    report = {
        "manifest": args.manifest.as_posix(),
        "duplicate_groups": len(duplicates),
        "duplicate_files": sum(group["count"] for group in duplicates),
        "duplicates": duplicates,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"Duplicate groups: {report['duplicate_groups']}")
    print(f"Files in duplicate groups: {report['duplicate_files']}")
    print(f"Report written to: {args.output}")


if __name__ == "__main__":
    main()
