import hashlib

import httpx
import pytest

from patentpath.config import Settings
from patentpath.ingest.object_storage import upload_file


def configured_settings():
    return Settings(
        r2_account_id="test-account",
        r2_access_key_id="test-access",
        r2_secret_access_key="test-secret",  # pragma: allowlist secret
        r2_bucket_name="patent-documents",
        r2_endpoint_url="https://test-account.r2.cloudflarestorage.com",
    )


@pytest.mark.asyncio
async def test_upload_file_sends_signed_put_request(tmp_path):
    content = b"%PDF-1.7 PatentPath test"
    file_path = tmp_path / "patent.pdf"
    file_path.write_bytes(content)
    captured = {}

    async def handler(request):
        captured["method"] = request.method
        captured["path"] = request.url.raw_path.decode("ascii")
        captured["authorization"] = request.headers["Authorization"]
        captured["payload_hash"] = request.headers["x-amz-content-sha256"]
        captured["body"] = await request.aread()
        captured["content_type"] = request.headers["Content-Type"]
        return httpx.Response(200, headers={"ETag": '"r2-test"'})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await upload_file(
            client,
            configured_settings(),
            file_path,
            "acts/Patent Act.pdf",
            "application/pdf",
        )

    expected_hash = hashlib.sha256(content).hexdigest()
    assert captured["method"] == "PUT"
    assert captured["path"] == "/patent-documents/acts/Patent%20Act.pdf"
    assert captured["body"] == content
    assert captured["payload_hash"] == expected_hash
    assert captured["authorization"].startswith("AWS4-HMAC-SHA256 ")
    assert "SignedHeaders=host;x-amz-content-sha256;x-amz-date" in captured["authorization"]
    assert captured["content_type"] == "application/pdf"
    assert result["object_key"] == "acts/Patent Act.pdf"
    assert result["etag"] == '"r2-test"'
    assert result["bytes"] == len(content)
    assert result["sha256"] == expected_hash
    assert result["storage"] == "cloudflare-r2"


@pytest.mark.asyncio
async def test_upload_file_rejects_missing_configuration(tmp_path):
    file_path = tmp_path / "patent.pdf"
    file_path.write_bytes(b"test")

    async with httpx.AsyncClient() as client:
        with pytest.raises(ValueError, match="Missing R2 configuration"):
            await upload_file(client, Settings(), file_path, "patent.pdf")


@pytest.mark.asyncio
async def test_upload_file_rejects_non_https_endpoint(tmp_path):
    file_path = tmp_path / "patent.pdf"
    file_path.write_bytes(b"test")
    settings = configured_settings()
    settings.r2_endpoint_url = "http://example.org"

    async with httpx.AsyncClient() as client:
        with pytest.raises(ValueError, match="HTTPS"):
            await upload_file(client, settings, file_path, "patent.pdf")


@pytest.mark.asyncio
async def test_upload_file_raises_on_r2_http_error(tmp_path):
    file_path = tmp_path / "patent.pdf"
    file_path.write_bytes(b"test")

    async def handler(request):
        return httpx.Response(403, text="Access denied")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(httpx.HTTPStatusError):
            await upload_file(
                client,
                configured_settings(),
                file_path,
                "patent.pdf",
            )
