"""Polite, resumable downloader for the PatentPath document corpus."""

import asyncio
import csv
import hashlib
import json
import random
import re
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import unquote, urlsplit

import httpx
from protego import Protego

USER_AGENT = (
    "PatentPathBot/0.1 "
    "(student project; "
    "+https://github.com/anushreeee2006-star/prince28-law08-patentpath)"
)
ROBOTS_TOKEN = "PatentPathBot"

RETRYABLE = {408, 425, 429, 500, 502, 503, 504}
MAX_WAIT = 120.0
MAX_BYTES = 200 * 1024 * 1024
ATTEMPT_TIMEOUT = 300.0

KNOWN_EXT = {
    ".pdf",
    ".html",
    ".htm",
    ".json",
    ".txt",
    ".md",
    ".mdx",
    ".rst",
    ".adoc",
    ".xml",
    ".yaml",
    ".yml",
    ".zip",
    ".docx",
    ".xlsx",
    ".xls",
    ".csv",
}

EXT_BY_TYPE = {
    "application/pdf": ".pdf",
    "text/html": ".html",
    "application/json": ".json",
    "text/plain": ".txt",
    "text/markdown": ".md",
    "text/csv": ".csv",
    "application/xml": ".xml",
    "text/xml": ".xml",
    "application/zip": ".zip",
    "application/yaml": ".yaml",
}

Sleep = Callable[[float], Awaitable[None]]


@dataclass(frozen=True)
class Source:
    url: str
    source: str
    licence: str
    title: str = ""


class DownloadError(Exception):
    def __init__(
        self,
        message: str,
        *,
        code: int | None = None,
        retry_after: float | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.retry_after = retry_after


def now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def slug(text: str, limit: int = 60) -> str:
    """Return a filesystem-safe lowercase name."""
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:limit] or "document"


def file_stem(url: str) -> str:
    """Create a stable filename from a URL."""
    parts = urlsplit(url)
    last = unquote(parts.path.rstrip("/").rsplit("/", 1)[-1])
    if not last:
        last = parts.netloc
    name = last.rsplit(".", 1)[0] if "." in last else last
    suffix = hashlib.sha256(url.encode()).hexdigest()[:8]
    return f"{slug(name)}-{suffix}"


def pick_ext(url: str, content_type: str) -> str:
    suffix = Path(urlsplit(url).path).suffix.lower()
    if suffix in KNOWN_EXT:
        return suffix
    media_type = content_type.split(";")[0].strip().lower()
    return EXT_BY_TYPE.get(media_type, ".bin")


def backoff_delay(
    attempt: int,
    *,
    base: float = 1.0,
    cap: float = 60.0,
) -> float:
    """Exponential backoff with full jitter."""
    return random.uniform(0, min(cap, base * 2**attempt))


def retry_after_seconds(value: str | None) -> float | None:
    """Parse Retry-After as seconds or an HTTP date."""
    if not value:
        return None

    value = value.strip()
    if value.isdigit():
        return float(value)

    try:
        when = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None

    if when.tzinfo is None:
        when = when.replace(tzinfo=UTC)

    return max(0.0, (when - datetime.now(UTC)).total_seconds())


def read_sources(path: Path) -> list[Source]:
    """Read and validate data/sources.csv."""
    sources: list[Source] = []
    seen: set[str] = set()

    with path.open(encoding="utf-8-sig", newline="") as handle:
        lines = (line for line in handle if line.strip() and not line.lstrip().startswith("#"))
        reader = csv.DictReader(lines)

        required = {"url", "source", "licence"}
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise ValueError("sources.csv must contain url,source,licence columns")

        for number, row in enumerate(reader, start=1):
            url = (row.get("url") or "").strip()
            name = (row.get("source") or "").strip()
            licence = (row.get("licence") or "").strip()
            title = (row.get("title") or "").strip()

            parts = urlsplit(url)
            if parts.scheme not in {"http", "https"} or not parts.netloc:
                raise ValueError(f"sources row {number}: not an http(s) URL")

            if not name or not licence:
                raise ValueError(f"sources row {number}: source and licence are required")

            if url not in seen:
                seen.add(url)
                sources.append(Source(url, name, licence, title))

    return sources


class Manifest:
    """Append-only JSONL log; the latest valid record for a URL wins."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.records: dict[str, dict] = {}

        if path.exists():
            content = path.read_text(encoding="utf-8")
            for line in content.splitlines():
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue

                if isinstance(record, dict) and "url" in record:
                    self.records[record["url"]] = record

            if content and not content.endswith("\n"):
                with path.open("a", encoding="utf-8") as handle:
                    handle.write("\n")

    def done(self, url: str, root: Path) -> bool:
        record = self.records.get(url)
        if not record or record.get("status") != "downloaded":
            return False

        relative_path = record.get("path")
        if not relative_path:
            return False

        file_path = root / relative_path
        return file_path.is_file() and file_path.stat().st_size > 0

    def add(self, record: dict) -> None:
        self.records[record["url"]] = record
        self.path.parent.mkdir(parents=True, exist_ok=True)

        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")


class Robots:
    """Check robots.txt once per website."""

    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client
        self._rules: dict[str, Protego | None] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    async def _load(self, origin: str) -> Protego | None:
        try:
            response = await self._client.get(origin + "/robots.txt")
        except httpx.HTTPError:
            return None

        if response.status_code == 404:
            return Protego.parse("")
        if response.status_code >= 400:
            return None

        return Protego.parse(response.text)

    async def check(self, url: str) -> tuple[bool, float]:
        """Return whether the URL is allowed and its crawl delay."""
        parts = urlsplit(url)
        origin = f"{parts.scheme}://{parts.netloc}"

        async with self._locks.setdefault(origin, asyncio.Lock()):
            if origin not in self._rules:
                self._rules[origin] = await self._load(origin)

        rules = self._rules[origin]
        if rules is None:
            return False, 0.0

        return rules.can_fetch(url, ROBOTS_TOKEN), float(rules.crawl_delay(ROBOTS_TOKEN) or 0.0)


class HostGate:
    """Ensure a pause between requests to the same host."""

    def __init__(self, delay: float, sleep: Callable[[float], Awaitable[None]]) -> None:
        self._delay = delay
        self._sleep = sleep
        self._next_ok: dict[str, float] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    async def wait(self, host: str, crawl_delay: float = 0.0) -> None:
        async with self._locks.setdefault(host, asyncio.Lock()):
            pause = self._next_ok.get(host, 0.0) - time.monotonic()
            if pause > 0:
                await self._sleep(pause)

            self._next_ok[host] = time.monotonic() + max(self._delay, crawl_delay)


def make_client(max_concurrency: int = 4) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        headers={"User-Agent": USER_AGENT},
        timeout=httpx.Timeout(30.0, connect=10.0),
        limits=httpx.Limits(max_connections=max_concurrency),
        follow_redirects=True,
    )


async def _download(
    client: httpx.AsyncClient,
    src: Source,
    root: Path,
    raw_dir: Path,
    headers: dict[str, str] | None = None,
) -> dict:
    """Stream a document to a temporary file and rename it when complete."""
    async with client.stream("GET", src.url, headers=headers) as response:
        if response.status_code == 304:
            return {
                "not_modified": True,
                "http_status": 304,
                "etag": response.headers.get("ETag"),
            }

        if response.status_code != 200:
            raise DownloadError(
                f"HTTP {response.status_code}",
                code=response.status_code,
                retry_after=retry_after_seconds(response.headers.get("Retry-After")),
            )

        content_type = response.headers.get("Content-Type", "")
        name = file_stem(src.url) + pick_ext(src.url, content_type)
        target = raw_dir / slug(src.source) / name
        target.parent.mkdir(parents=True, exist_ok=True)
        part = target.with_name(name + ".part")

        digest, size = hashlib.sha256(), 0

        try:
            with part.open("wb") as handle:
                async for chunk in response.aiter_bytes():
                    size += len(chunk)
                    if size > MAX_BYTES:
                        raise DownloadError(f"File larger than {MAX_BYTES} bytes")
                    digest.update(chunk)
                    handle.write(chunk)

            part.replace(target)
        finally:
            part.unlink(missing_ok=True)

    return {
        "path": target.relative_to(root).as_posix(),
        "bytes": size,
        "sha256": digest.hexdigest(),
        "content_type": content_type.split(";")[0].strip(),
        "http_status": 200,
        "etag": response.headers.get("ETag"),
    }


async def fetch_one(
    client: httpx.AsyncClient,
    src: Source,
    *,
    root: Path,
    raw_dir: Path,
    robots: Robots,
    gate: HostGate,
    slots: asyncio.Semaphore,
    max_attempts: int,
    sleep: Sleep,
    previous_record: dict | None = None,
) -> dict:
    """Fetch one permitted source and return its manifest record."""
    base = {
        "url": src.url,
        "source": src.source,
        "licence": src.licence,
        "title": src.title,
        "via": "http",
        "fetched_at": now_iso(),
    }

    request_headers = {}
    if previous_record and previous_record.get("etag"):
        request_headers["If-None-Match"] = previous_record["etag"]

    async with slots:
        allowed, crawl_delay = await robots.check(src.url)
        if not allowed:
            return {**base, "status": "blocked", "attempts": 0}

        host = urlsplit(src.url).netloc

        for attempt in range(1, max_attempts + 1):
            await gate.wait(host, crawl_delay)

            try:
                async with asyncio.timeout(ATTEMPT_TIMEOUT):
                    result = await _download(
                        client, src, root, raw_dir, headers=request_headers or None
                    )

                if result.get("not_modified"):
                    return {
                        **base,
                        **previous_record,
                        "url": src.url,
                        "status": "downloaded",
                        "http_status": 304,
                        "etag": previous_record["etag"],
                        "attempts": attempt,
                        "revalidated": True,
                        "fetched_at": now_iso(),
                    }

                return {
                    **base,
                    **result,
                    "status": "downloaded",
                    "attempts": attempt,
                    "fetched_at": now_iso(),
                }

            except DownloadError as exc:
                retryable = exc.code in RETRYABLE
                message = str(exc)
                retry_after = exc.retry_after

            except (httpx.HTTPError, TimeoutError) as exc:
                retryable = True
                message = str(exc) or type(exc).__name__
                retry_after = None

            if not retryable or attempt >= max_attempts:
                return {
                    **base,
                    "status": "failed",
                    "attempts": attempt,
                    "error": message,
                    "fetched_at": now_iso(),
                }

            wait = retry_after if retry_after is not None else backoff_delay(attempt - 1)
            await sleep(min(MAX_WAIT, wait))

    return {**base, "status": "failed", "error": "Attempts exhausted"}


async def fetch_all(
    sources: list[Source],
    *,
    root: Path = Path("."),
    raw_dir: Path | None = None,
    manifest_path: Path | None = None,
    max_concurrency: int = 4,
    per_host_delay: float = 0.5,
    max_attempts: int = 4,
    client: httpx.AsyncClient | None = None,
    sleep: Sleep = asyncio.sleep,
    on_result: Callable[[dict], None] | None = None,
) -> dict:
    """Fetch all sources, recording each result promptly for resume support."""
    if not 1 <= max_concurrency <= 4:
        raise ValueError("max_concurrency must be between 1 and 4")
    if per_host_delay < 0 or max_attempts < 1:
        raise ValueError("delay must be non-negative and max_attempts at least 1")

    raw_dir = raw_dir or root / "data" / "raw"
    manifest_path = manifest_path or root / "data" / "manifest.jsonl"

    manifest = Manifest(manifest_path)
    gate = HostGate(per_host_delay, sleep)
    slots = asyncio.Semaphore(max_concurrency)

    summary = {
        "downloaded": 0,
        "skipped": 0,
        "blocked": 0,
        "failed": 0,
        "errors": [],
    }

    async def run(client_instance: httpx.AsyncClient) -> None:
        robots = Robots(client_instance)

        async def process(src: Source) -> None:
            previous_record = manifest.records.get(src.url)
            is_done = manifest.done(src.url, root)

            if is_done and not (previous_record or {}).get("etag"):
                summary["skipped"] += 1
                return

            record = await fetch_one(
                client_instance,
                src,
                root=root,
                raw_dir=raw_dir,
                robots=robots,
                gate=gate,
                slots=slots,
                max_attempts=max_attempts,
                sleep=sleep,
                previous_record=previous_record if is_done else None,
            )

            if record["status"] in {"downloaded", "blocked", "failed"}:
                manifest.add(record)

            if record["status"] == "downloaded" and record.get("http_status") == 304:
                summary["skipped"] += 1
            elif record["status"] in summary:
                summary[record["status"]] += 1

            if record["status"] == "failed":
                summary["errors"].append(
                    {
                        "url": src.url,
                        "error": record.get("error", "Unknown error"),
                    }
                )

            if on_result is not None:
                on_result(record)

        await asyncio.gather(*(process(src) for src in sources))

    if client is not None:
        await run(client)
    else:
        async with make_client(max_concurrency) as owned_client:
            await run(owned_client)

    return summary


async def fetch_sources(
    sources: list[Source],
    root: Path,
    raw_dir: Path,
    manifest_path: Path,
    *,
    delay: float = 3.0,
    max_concurrency: int = 4,
    retries: int = 5,
    sleep: Sleep = asyncio.sleep,
) -> dict:
    """Backward-compatible wrapper for existing callers and tests."""
    return await fetch_all(
        sources,
        root=root,
        raw_dir=raw_dir,
        manifest_path=manifest_path,
        max_concurrency=max_concurrency,
        per_host_delay=delay,
        max_attempts=retries + 1,
        sleep=sleep,
    )
