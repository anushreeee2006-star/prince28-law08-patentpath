import argparse
import asyncio
import hashlib
import re
from pathlib import Path
from urllib.parse import quote

import httpx

from patentpath.ingest.fetch import Manifest, fetch_all, now_iso, read_sources


def fetch_repo(repository, paths, extensions, ref, root, source_name=None, licence=None):
    import io
    import zipfile

    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
        raise ValueError("Repository must be in OWNER/REPO format")

    paths = [p.strip("/") for p in paths] or ["."]
    extensions = {
        e.lower() if e.startswith(".") else f".{e.lower()}"
        for e in (extensions or [".md", ".mdx", ".rst", ".adoc", ".yml", ".json", ".txt"])
    }

    headers = {"User-Agent": "PatentPathBot/0.1"}
    with httpx.Client(headers=headers, timeout=120.0, follow_redirects=True) as client:
        if not ref:
            response = client.get(f"https://api.github.com/repos/{repository}")
            response.raise_for_status()
            ref = response.json()["default_branch"]

        response = client.get(
            f"https://api.github.com/repos/{repository}/commits/{quote(ref, safe='')}"
        )
        response.raise_for_status()
        commit = response.json()["sha"]

        destination = root / "data" / "raw" / repository.replace("/", "-")
        manifest = Manifest(root / "data" / "manifest.jsonl")
        existing = [
            record
            for record in manifest.records.values()
            if record.get("commit") == commit
            and record.get("source") == (source_name or repository)
            and record.get("status") == "downloaded"
        ]
        if existing and all(
            (root / record["path"]).is_file()
            and (root / record["path"]).stat().st_size == record.get("bytes")
            for record in existing
        ):
            print(
                f"repo={repository} commit={commit[:10]} "
                f"added=0 unchanged={len(existing)} (ZIP skipped)"
            )
            return

        archive = client.get(f"https://codeload.github.com/{repository}/zip/{commit}")
        archive.raise_for_status()

    destination = root / "data" / "raw" / repository.replace("/", "-")
    added = unchanged = 0
    manifest = Manifest(root / "data" / "manifest.jsonl")

    with zipfile.ZipFile(io.BytesIO(archive.content)) as bundle:
        for item in bundle.infolist():
            if item.is_dir():
                continue

            parts = Path(item.filename.replace("\\\\", "/")).parts
            relative_parts = parts[1:]
            if not relative_parts:
                continue

            relative = Path(*relative_parts)
            if relative.suffix.lower() not in extensions:
                continue

            relative_text = relative.as_posix()
            if paths != ["."] and not any(
                relative_text == p or relative_text.startswith(p + "/") for p in paths
            ):
                continue

            target = destination / relative
            content = bundle.read(item)
            digest = hashlib.sha256(content).hexdigest()

            if target.exists() and hashlib.sha256(target.read_bytes()).hexdigest() == digest:
                unchanged += 1
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(content)
                added += 1

            if source_name:
                relative_path = target.relative_to(root).as_posix()
                manifest.add(
                    {
                        "url": f"https://github.com/{repository}/blob/{commit}/{relative_text}",
                        "source": source_name or repository,
                        "commit": commit,
                        "path": relative_path,
                        "bytes": len(content),
                        "sha256": digest,
                        "status": "downloaded",
                        "licence": licence or "Not supplied",
                        "licence_status": "not_verified",
                        "fetched_at": now_iso(),
                    }
                )

    print(f"repo={repository} commit={commit[:10]} added={added} unchanged={unchanged}")


def main():
    parser = argparse.ArgumentParser(description="PatentPath corpus collection")
    subparsers = parser.add_subparsers(dest="door", required=True)

    urls = subparsers.add_parser("urls", help="Download URLs from data/sources.csv")
    urls.add_argument("--delay", type=float, default=0.5)
    urls.add_argument("--concurrency", type=int, choices=range(1, 5), default=4)
    urls.add_argument("--retries", type=int, default=4)

    repo = subparsers.add_parser("repo", help="Fetch selected files from a GitHub repository")
    repo.add_argument("repository", help="GitHub repository in OWNER/REPO format")
    repo.add_argument("--path", action="append", default=[], help="Folder to fetch (repeatable)")
    repo.add_argument(
        "--ext", action="append", default=[], help="File extension to include (repeatable)"
    )
    repo.add_argument("--ref", help="Branch or tag to fetch")
    repo.add_argument("--source", help="Source name for manifest records")
    repo.add_argument("--licence", help="Licence or reuse terms")

    args = parser.parse_args()

    if args.door == "urls":
        if args.delay < 0:
            parser.error("--delay must be non-negative")
        if args.retries < 1:
            parser.error("--retries must be at least 1")

        root = Path(__file__).resolve().parent.parent
        sources = read_sources(root / "data" / "sources.csv")
        summary = asyncio.run(
            fetch_all(
                sources,
                root=root,
                max_concurrency=args.concurrency,
                per_host_delay=args.delay,
                max_attempts=args.retries,
            )
        )
        for key, value in summary.items():
            print(f"{key}: {value}")

    elif args.door == "repo":
        root = Path(__file__).resolve().parent.parent
        try:
            fetch_repo(
                args.repository,
                args.path,
                args.ext,
                args.ref,
                root,
                source_name=args.source,
                licence=args.licence,
            )
        except (ValueError, FileNotFoundError, httpx.HTTPError) as exc:
            detail = str(exc)
            parser.error(detail or str(exc))


if __name__ == "__main__":
    main()
