"""Find duplicate downloaded files using SHA-256 hashes."""

import json
from collections import defaultdict
from pathlib import Path


def find_duplicates(manifest_path: Path) -> list[dict]:
    """Return distinct downloaded files grouped by matching SHA-256 hashes."""
    groups: dict[str, dict[str, dict]] = defaultdict(dict)

    if not manifest_path.is_file():
        raise FileNotFoundError(f"Manifest not found: {manifest_path}")

    with manifest_path.open(encoding="utf-8-sig") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON in manifest at line {line_number}") from exc

            if not isinstance(record, dict):
                continue

            digest = record.get("sha256")
            path = record.get("path")
            if record.get("status") != "downloaded" or not digest or not path:
                continue

            groups[digest][path] = {
                "url": record.get("url", ""),
                "path": path,
                "source": record.get("source", ""),
                "bytes": record.get("bytes", 0),
            }

    return [
        {"sha256": digest, "count": len(records), "files": list(records.values())}
        for digest, records in sorted(groups.items())
        if len(records) > 1
    ]
