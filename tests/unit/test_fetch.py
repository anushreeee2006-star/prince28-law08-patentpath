import hashlib
import json

import httpx
import pytest

from patentpath.ingest.fetch import (
    DownloadError,
    Manifest,
    Source,
    _download,
    backoff_delay,
    fetch_sources,
    file_stem,
    pick_ext,
    read_sources,
    retry_after_seconds,
    slug,
)


def test_slug_creates_safe_name():
    assert slug("Patent Office Manual 2019") == "patent-office-manual-2019"


def test_file_stem_is_stable():
    url = "https://example.org/docs/patents-act.pdf"
    assert file_stem(url) == file_stem(url)
    assert file_stem(url).startswith("patents-act-")


def test_pick_ext_from_url():
    assert pick_ext("https://example.org/act.pdf", "") == ".pdf"


def test_pick_ext_from_content_type():
    assert (
        pick_ext(
            "https://example.org/document",
            "application/pdf; charset=binary",
        )
        == ".pdf"
    )


def test_backoff_delay_stays_within_cap():
    assert 0 <= backoff_delay(3, base=1, cap=4) <= 4


def test_retry_after_seconds_parses_seconds():
    assert retry_after_seconds("15") == 15.0


def test_retry_after_seconds_handles_invalid_value():
    assert retry_after_seconds("not-a-date") is None


def test_read_sources_skips_comments_and_duplicates(tmp_path):
    csv_file = tmp_path / "sources.csv"
    csv_file.write_text(
        "# PatentPath sources\n"
        "url,source,licence,title\n"
        "https://example.org/act.pdf,ipindia,Official policy,Patents Act\n"
        "https://example.org/act.pdf,ipindia,Official policy,Duplicate\n",
        encoding="utf-8",
    )

    sources = read_sources(csv_file)

    assert len(sources) == 1
    assert sources[0] == Source(
        "https://example.org/act.pdf",
        "ipindia",
        "Official policy",
        "Patents Act",
    )


def test_read_sources_rejects_invalid_url(tmp_path):
    csv_file = tmp_path / "sources.csv"
    csv_file.write_text(
        "url,source,licence\nftp://example.org/file.pdf,ipindia,Official policy\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="http"):
        read_sources(csv_file)


def test_read_sources_requires_licence(tmp_path):
    csv_file = tmp_path / "sources.csv"
    csv_file.write_text(
        "url,source,licence\nhttps://example.org/file.pdf,ipindia,\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="licence"):
        read_sources(csv_file)


def test_manifest_records_completed_download(tmp_path):
    manifest_path = tmp_path / "manifest.jsonl"
    root = tmp_path
    downloaded = root / "raw" / "act.pdf"
    downloaded.parent.mkdir(parents=True)
    downloaded.write_bytes(b"%PDF-test")

    manifest = Manifest(manifest_path)
    manifest.add(
        {
            "url": "https://example.org/act.pdf",
            "status": "downloaded",
            "path": "raw/act.pdf",
        }
    )

    assert manifest.done("https://example.org/act.pdf", root)


def test_manifest_does_not_skip_missing_file(tmp_path):
    manifest_path = tmp_path / "manifest.jsonl"
    manifest_path.write_text(
        json.dumps(
            {
                "url": "https://example.org/act.pdf",
                "status": "downloaded",
                "path": "raw/missing.pdf",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    manifest = Manifest(manifest_path)
    assert not manifest.done("https://example.org/act.pdf", tmp_path)


def test_manifest_does_not_skip_empty_file(tmp_path):
    empty_file = tmp_path / "raw" / "empty.pdf"
    empty_file.parent.mkdir()
    empty_file.write_bytes(b"")

    manifest_path = tmp_path / "manifest.jsonl"
    manifest_path.write_text(
        json.dumps(
            {
                "url": "https://example.org/empty.pdf",
                "status": "downloaded",
                "path": "raw/empty.pdf",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    manifest = Manifest(manifest_path)
    assert not manifest.done("https://example.org/empty.pdf", tmp_path)


def test_manifest_repairs_missing_final_newline(tmp_path):
    manifest_path = tmp_path / "manifest.jsonl"
    manifest_path.write_text(
        '{"url":"https://example.org/act.pdf","status":"downloaded","path":"act.pdf"}',
        encoding="utf-8",
    )

    Manifest(manifest_path)

    assert manifest_path.read_text(encoding="utf-8").endswith("\n")


@pytest.mark.asyncio
async def test_robots_allows_url_when_no_rules_on_404():
    import httpx

    from patentpath.ingest.fetch import Robots

    transport = httpx.MockTransport(lambda request: httpx.Response(404))

    async with httpx.AsyncClient(transport=transport) as client:
        robots = Robots(client)
        allowed, delay = await robots.check("https://example.org/document.pdf")

    assert allowed
    assert delay == 0.0


@pytest.mark.asyncio
async def test_robots_denies_url_when_forbidden():
    import httpx

    from patentpath.ingest.fetch import Robots

    transport = httpx.MockTransport(lambda request: httpx.Response(403))

    async with httpx.AsyncClient(transport=transport) as client:
        robots = Robots(client)
        allowed, _ = await robots.check("https://example.org/document.pdf")

    assert not allowed


@pytest.mark.asyncio
async def test_robots_denies_url_when_server_error():
    import httpx

    from patentpath.ingest.fetch import Robots

    transport = httpx.MockTransport(lambda request: httpx.Response(503))

    async with httpx.AsyncClient(transport=transport) as client:
        robots = Robots(client)
        allowed, _ = await robots.check("https://example.org/document.pdf")

    assert not allowed


@pytest.mark.asyncio
async def test_robots_respects_disallow_rule():
    import httpx

    from patentpath.ingest.fetch import Robots

    body = "User-agent: *\nDisallow: /private/\n"

    transport = httpx.MockTransport(lambda request: httpx.Response(200, text=body))

    async with httpx.AsyncClient(transport=transport) as client:
        robots = Robots(client)
        allowed, _ = await robots.check("https://example.org/private/document.pdf")

    assert not allowed


@pytest.mark.asyncio
async def test_robots_allows_url_not_disallowed():
    import httpx

    from patentpath.ingest.fetch import Robots

    body = "User-agent: *\nDisallow: /private/\n"

    transport = httpx.MockTransport(lambda request: httpx.Response(200, text=body))

    async with httpx.AsyncClient(transport=transport) as client:
        robots = Robots(client)
        allowed, _ = await robots.check("https://example.org/public/document.pdf")

    assert allowed


@pytest.mark.asyncio
async def test_robots_denies_when_connection_fails():
    import httpx

    from patentpath.ingest.fetch import Robots

    def fail_request(request):
        raise httpx.ConnectError("Connection failed")

    transport = httpx.MockTransport(fail_request)

    async with httpx.AsyncClient(transport=transport) as client:
        robots = Robots(client)
        allowed, _ = await robots.check("https://example.org/document.pdf")

    assert not allowed


@pytest.mark.asyncio
async def test_download_saves_file_and_sha256(tmp_path):
    content = b"%PDF-1.7 test document"

    async def handler(request):
        return httpx.Response(
            200,
            headers={"Content-Type": "application/pdf"},
            content=content,
        )

    src = Source(
        url="https://example.org/patents-act.pdf",
        source="Patent Act",
        licence="Test licence",
        title="Patents Act",
    )
    root = tmp_path
    raw_dir = root / "data" / "raw"

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await _download(client, src, root, raw_dir)

    target = root / result["path"]
    assert target.exists()
    assert target.read_bytes() == content
    assert result["bytes"] == len(content)
    assert result["sha256"] == hashlib.sha256(content).hexdigest()
    assert result["content_type"] == "application/pdf"
    assert result["http_status"] == 200
    assert isinstance(result["request_duration_seconds"], float)
    assert result["request_duration_seconds"] >= 0
    assert not list(raw_dir.rglob("*.part"))


@pytest.mark.asyncio
async def test_download_rejects_http_error(tmp_path):
    async def handler(request):
        return httpx.Response(503, headers={"Retry-After": "10"})

    src = Source(
        url="https://example.org/patents-act.pdf",
        source="Patent Act",
        licence="Test licence",
    )
    raw_dir = tmp_path / "data" / "raw"

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(DownloadError) as exc_info:
            await _download(client, src, tmp_path, raw_dir)

    assert exc_info.value.code == 503
    assert exc_info.value.retry_after == 10.0
    assert not raw_dir.exists()


class BrokenDownloadStream(httpx.AsyncByteStream):
    async def __aiter__(self):
        yield b"%PDF-1.7 partial content"
        raise httpx.ReadError("Connection interrupted")

    async def aclose(self):
        pass


@pytest.mark.asyncio
async def test_download_removes_partial_file_on_interruption(tmp_path):
    async def handler(request):
        return httpx.Response(
            200,
            headers={"Content-Type": "application/pdf"},
            stream=BrokenDownloadStream(),
        )

    src = Source(
        url="https://example.org/interrupted.pdf",
        source="Patent Act",
        licence="Test licence",
    )
    raw_dir = tmp_path / "data" / "raw"

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(httpx.ReadError):
            await _download(client, src, tmp_path, raw_dir)

    assert not list(raw_dir.rglob("*.part"))
    assert not list(raw_dir.rglob("*.pdf"))


@pytest.mark.asyncio
async def test_fetch_sources_downloads_then_skips_completed(tmp_path, monkeypatch):
    from patentpath.ingest import fetch as fetch_module

    content = b"%PDF-1.7 PatentPath test"
    requests = []

    async def handler(request):
        requests.append(request.url.path)

        if request.url.path == "/robots.txt":
            return httpx.Response(404)

        return httpx.Response(
            200,
            headers={"Content-Type": "application/pdf"},
            content=content,
        )

    def client_factory(max_concurrency=4):
        return httpx.AsyncClient(transport=httpx.MockTransport(handler))

    monkeypatch.setattr(fetch_module, "make_client", client_factory)

    src = Source(
        url="https://example.org/patents-act.pdf",
        source="Patent Act",
        licence="Test licence",
        title="Patents Act",
    )
    root = tmp_path
    raw_dir = root / "data" / "raw"
    manifest_path = root / "data" / "manifest.jsonl"

    async def no_wait(seconds):
        pass

    first = await fetch_sources(
        [src],
        root,
        raw_dir,
        manifest_path,
        delay=0,
        retries=0,
        sleep=no_wait,
    )

    assert first["downloaded"] == 1
    assert first["skipped"] == 0
    assert first["failed"] == 0
    assert first["blocked"] == 0
    assert len(requests) == 2

    records = [json.loads(line) for line in manifest_path.read_text(encoding="utf-8").splitlines()]
    assert len(records) == 1
    assert records[0]["status"] == "downloaded"
    assert records[0]["url"] == src.url

    second = await fetch_sources(
        [src],
        root,
        raw_dir,
        manifest_path,
        delay=0,
        retries=0,
        sleep=no_wait,
    )

    assert second["downloaded"] == 0
    assert second["skipped"] == 1
    assert second["failed"] == 0
    assert len(requests) == 2


@pytest.mark.asyncio
async def test_fetch_sources_revalidates_etag_and_updates_content(tmp_path, monkeypatch):
    from patentpath.ingest import fetch as fetch_module

    old_content = b"%PDF-1.7 original"
    new_content = b"%PDF-1.7 updated"
    document_requests = []

    async def handler(request):
        if request.url.path == "/robots.txt":
            return httpx.Response(404)

        document_requests.append(request)

        if len(document_requests) == 1:
            return httpx.Response(
                200,
                headers={"Content-Type": "application/pdf", "ETag": '"v1"'},
                content=old_content,
            )

        assert request.headers.get("If-None-Match") == '"v1"'

        if len(document_requests) == 2:
            return httpx.Response(304, headers={"ETag": '"v1"'})

        return httpx.Response(
            200,
            headers={"Content-Type": "application/pdf", "ETag": '"v2"'},
            content=new_content,
        )

    def client_factory(max_concurrency=4):
        return httpx.AsyncClient(transport=httpx.MockTransport(handler))

    monkeypatch.setattr(fetch_module, "make_client", client_factory)

    src = Source(
        url="https://example.org/patents-act.pdf",
        source="Patent Act",
        licence="Test licence",
        title="Patents Act",
    )
    root = tmp_path
    raw_dir = root / "data" / "raw"
    manifest_path = root / "data" / "manifest.jsonl"

    async def no_wait(seconds):
        pass

    first = await fetch_sources(
        [src],
        root,
        raw_dir,
        manifest_path,
        delay=0,
        retries=0,
        sleep=no_wait,
    )
    assert first["downloaded"] == 1
    assert len(document_requests) == 1

    record = json.loads(manifest_path.read_text(encoding="utf-8").splitlines()[-1])
    target = root / record["path"]
    assert record["etag"] == '"v1"'
    assert target.read_bytes() == old_content

    second = await fetch_sources(
        [src],
        root,
        raw_dir,
        manifest_path,
        delay=0,
        retries=0,
        sleep=no_wait,
    )
    assert second["skipped"] == 1
    assert second["downloaded"] == 0
    assert len(document_requests) == 2
    assert target.read_bytes() == old_content

    not_modified = json.loads(manifest_path.read_text(encoding="utf-8").splitlines()[-1])
    assert not_modified["http_status"] == 304
    assert isinstance(not_modified["request_duration_seconds"], float)
    assert not_modified["request_duration_seconds"] >= 0

    third = await fetch_sources(
        [src],
        root,
        raw_dir,
        manifest_path,
        delay=0,
        retries=0,
        sleep=no_wait,
    )
    assert third["downloaded"] == 1
    assert len(document_requests) == 3
    assert target.read_bytes() == new_content

    latest = json.loads(manifest_path.read_text(encoding="utf-8").splitlines()[-1])
    assert latest["etag"] == '"v2"'
    assert latest["sha256"] == hashlib.sha256(new_content).hexdigest()


@pytest.mark.asyncio
async def test_fetch_sources_uploads_downloaded_file_to_r2(tmp_path, monkeypatch):
    from types import SimpleNamespace

    from patentpath.ingest import fetch as fetch_module

    settings = SimpleNamespace(
        r2_account_id="test-account",
        r2_access_key_id="test-key",
        r2_secret_access_key="test-secret",  # pragma: allowlist secret
        r2_bucket_name="test-bucket",
        r2_endpoint_url="https://test-account.r2.cloudflarestorage.com",
        r2_region="auto",
    )
    monkeypatch.setattr(fetch_module, "get_settings", lambda: settings)

    document_requests = []
    uploads = []

    async def handler(request):
        if request.url.path == "/robots.txt":
            return httpx.Response(404)

        document_requests.append(request)
        return httpx.Response(
            200,
            headers={"Content-Type": "application/pdf"},
            content=b"%PDF-1.7 test document",
        )

    async def fake_upload(client, upload_settings, file_path, object_key, content_type):
        uploads.append((file_path, object_key, content_type))
        return {
            "object_key": object_key,
            "etag": '"r2-test"',
            "bytes": file_path.stat().st_size,
            "sha256": hashlib.sha256(file_path.read_bytes()).hexdigest(),
            "storage": "cloudflare-r2",
        }

    monkeypatch.setattr(fetch_module, "upload_file", fake_upload)
    monkeypatch.setattr(
        fetch_module,
        "make_client",
        lambda max_concurrency=4: httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )

    src = Source(
        url="https://example.org/patents-act.pdf",
        source="Patent Act",
        licence="Test licence",
        title="Patents Act",
    )

    async def no_wait(seconds):
        pass

    result = await fetch_module.fetch_sources(
        [src],
        tmp_path,
        tmp_path / "data" / "raw",
        tmp_path / "data" / "manifest.jsonl",
        delay=0,
        retries=0,
        sleep=no_wait,
    )

    assert result["downloaded"] == 1
    assert len(document_requests) == 1
    assert len(uploads) == 1
    assert uploads[0][0].is_file()
    assert uploads[0][1].startswith("data/raw/")
    assert uploads[0][2] == "application/pdf"

    record = json.loads(
        (tmp_path / "data" / "manifest.jsonl").read_text(encoding="utf-8").splitlines()[-1]
    )
    assert record["r2_status"] == "uploaded"
    assert record["r2_etag"] == '"r2-test"'
    assert record["r2_storage"] == "cloudflare-r2"


@pytest.mark.asyncio
async def test_fetch_sources_retries_failed_r2_upload_without_redownloading(tmp_path, monkeypatch):
    from types import SimpleNamespace

    from patentpath.ingest import fetch as fetch_module

    settings = SimpleNamespace(
        r2_account_id="test-account",
        r2_access_key_id="test-key",
        r2_secret_access_key="test-secret",  # pragma: allowlist secret
        r2_bucket_name="test-bucket",
        r2_endpoint_url="https://test-account.r2.cloudflarestorage.com",
        r2_region="auto",
    )
    monkeypatch.setattr(fetch_module, "get_settings", lambda: settings)

    document_requests = []
    upload_attempts = []

    async def handler(request):
        if request.url.path == "/robots.txt":
            return httpx.Response(404)

        document_requests.append(request)
        return httpx.Response(
            200,
            headers={"Content-Type": "application/pdf"},
            content=b"%PDF-1.7 retry document",
        )

    async def fake_upload(client, upload_settings, file_path, object_key, content_type):
        upload_attempts.append(file_path)
        if len(upload_attempts) == 1:
            raise httpx.ConnectError("Simulated R2 outage")

        return {
            "object_key": object_key,
            "etag": '"r2-retry"',
            "bytes": file_path.stat().st_size,
            "sha256": hashlib.sha256(file_path.read_bytes()).hexdigest(),
            "storage": "cloudflare-r2",
        }

    monkeypatch.setattr(fetch_module, "upload_file", fake_upload)
    monkeypatch.setattr(
        fetch_module,
        "make_client",
        lambda max_concurrency=4: httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )

    src = Source(
        url="https://example.org/retry-act.pdf",
        source="Patent Act",
        licence="Test licence",
        title="Retry Act",
    )

    async def no_wait(seconds):
        pass

    first = await fetch_module.fetch_sources(
        [src],
        tmp_path,
        tmp_path / "data" / "raw",
        tmp_path / "data" / "manifest.jsonl",
        delay=0,
        retries=0,
        sleep=no_wait,
    )

    assert first["downloaded"] == 1
    assert len(document_requests) == 1
    assert len(upload_attempts) == 1
    assert upload_attempts[0].is_file()

    first_record = json.loads(
        (tmp_path / "data" / "manifest.jsonl").read_text(encoding="utf-8").splitlines()[-1]
    )
    assert first_record["r2_status"] == "failed"
    assert "Simulated R2 outage" in first_record["r2_error"]

    second = await fetch_module.fetch_sources(
        [src],
        tmp_path,
        tmp_path / "data" / "raw",
        tmp_path / "data" / "manifest.jsonl",
        delay=0,
        retries=0,
        sleep=no_wait,
    )

    assert second["skipped"] == 1
    assert second["downloaded"] == 0
    assert len(document_requests) == 1
    assert len(upload_attempts) == 2
    assert upload_attempts[0] == upload_attempts[1]

    latest = json.loads(
        (tmp_path / "data" / "manifest.jsonl").read_text(encoding="utf-8").splitlines()[-1]
    )
    assert latest["r2_status"] == "uploaded"
    assert latest["r2_etag"] == '"r2-retry"'
    assert "r2_error" not in latest
