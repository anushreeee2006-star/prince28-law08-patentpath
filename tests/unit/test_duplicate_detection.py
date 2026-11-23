import json

import pytest

from patentpath.ingest.duplicates import find_duplicates


def test_finds_files_with_matching_sha256(tmp_path):
    manifest = tmp_path / "manifest.jsonl"
    records = [
        {
            "url": "https://example.org/a.pdf",
            "path": "raw/a.pdf",
            "source": "example",
            "bytes": 100,
            "sha256": "abc123",
            "status": "downloaded",
        },
        {
            "url": "https://example.org/b.pdf",
            "path": "raw/b.pdf",
            "source": "example",
            "bytes": 100,
            "sha256": "abc123",
            "status": "downloaded",
        },
        {
            "url": "https://example.org/c.pdf",
            "path": "raw/c.pdf",
            "source": "example",
            "bytes": 200,
            "sha256": "unique456",
            "status": "downloaded",
        },
    ]
    manifest.write_text(
        "".join(json.dumps(record) + "\n" for record in records),
        encoding="utf-8",
    )

    duplicates = find_duplicates(manifest)

    assert len(duplicates) == 1
    assert duplicates[0]["sha256"] == "abc123"
    assert duplicates[0]["count"] == 2
    assert len(duplicates[0]["files"]) == 2


def test_ignores_records_not_downloaded(tmp_path):
    manifest = tmp_path / "manifest.jsonl"
    records = [
        {
            "url": "https://example.org/a.pdf",
            "sha256": "same",
            "status": "downloaded",
        },
        {
            "url": "https://example.org/b.pdf",
            "sha256": "same",
            "status": "failed",
        },
    ]
    manifest.write_text(
        "".join(json.dumps(record) + "\n" for record in records),
        encoding="utf-8",
    )

    assert find_duplicates(manifest) == []


def test_returns_empty_list_when_no_duplicates(tmp_path):
    manifest = tmp_path / "manifest.jsonl"
    records = [
        {"sha256": "one", "status": "downloaded"},
        {"sha256": "two", "status": "downloaded"},
    ]
    manifest.write_text(
        "".join(json.dumps(record) + "\n" for record in records),
        encoding="utf-8",
    )

    assert find_duplicates(manifest) == []


def test_rejects_invalid_json_line(tmp_path):
    manifest = tmp_path / "manifest.jsonl"
    manifest.write_text('{"sha256":"valid"}\nnot-json\n', encoding="utf-8")

    with pytest.raises(ValueError, match="line 2"):
        find_duplicates(manifest)


def test_rejects_missing_manifest(tmp_path):
    with pytest.raises(FileNotFoundError):
        find_duplicates(tmp_path / "missing.jsonl")


def test_ignores_repeated_manifest_entry_for_same_file(tmp_path):
    manifest = tmp_path / "manifest.jsonl"
    record = {
        "url": "https://example.org/a.pdf",
        "path": "raw/a.pdf",
        "sha256": "same",
        "status": "downloaded",
    }
    manifest.write_text(
        json.dumps(record) + "\n" + json.dumps(record) + "\n",
        encoding="utf-8",
    )

    assert find_duplicates(manifest) == []
