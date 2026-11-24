"""Optional Cloudflare R2 object storage using AWS Signature V4."""

import hashlib
import hmac
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import quote, urlsplit

import httpx

from patentpath.config import Settings

CHUNK_SIZE = 1024 * 1024


def _sign(key: bytes, message: str) -> bytes:
    """Return an HMAC-SHA256 signature."""
    return hmac.new(key, message.encode("utf-8"), hashlib.sha256).digest()


def _signing_key(secret: str, date: str, region: str, service: str) -> bytes:
    """Derive the AWS Signature V4 signing key."""
    date_key = _sign(("AWS4" + secret).encode("utf-8"), date)
    region_key = _sign(date_key, region)
    service_key = _sign(region_key, service)
    return _sign(service_key, "aws4_request")


def _file_sha256(path: Path) -> str:
    """Hash a file without loading it all into memory."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


async def _file_chunks(path: Path):
    """Yield file chunks for an asynchronous HTTP request."""
    with path.open("rb") as handle:
        while chunk := handle.read(CHUNK_SIZE):
            yield chunk


async def upload_file(
    client: httpx.AsyncClient,
    settings: Settings,
    file_path: Path,
    object_key: str,
    content_type: str = "application/octet-stream",
) -> dict:
    """Upload a local file to Cloudflare R2 using an S3-compatible PUT."""
    required = {
        "R2_ACCOUNT_ID": settings.r2_account_id,
        "R2_ACCESS_KEY_ID": settings.r2_access_key_id,
        "R2_SECRET_ACCESS_KEY": settings.r2_secret_access_key,
        "R2_BUCKET_NAME": settings.r2_bucket_name,
        "R2_ENDPOINT_URL": settings.r2_endpoint_url,
    }
    missing = [name for name, value in required.items() if not value.strip()]
    if missing:
        raise ValueError("Missing R2 configuration: " + ", ".join(missing))

    if not file_path.is_file():
        raise FileNotFoundError(file_path)

    endpoint = urlsplit(settings.r2_endpoint_url)
    if endpoint.scheme != "https" or not endpoint.netloc or endpoint.query or endpoint.fragment:
        raise ValueError("R2_ENDPOINT_URL must be a valid HTTPS endpoint without query or fragment")

    key = object_key.strip("/")
    if not key:
        raise ValueError("object_key must not be empty")

    region = settings.r2_region.strip() or "auto"
    date_time = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    date_stamp = date_time[:8]
    service = "s3"

    encoded_bucket = quote(settings.r2_bucket_name, safe="-_.~")
    encoded_key = quote(key, safe="/-_.~")
    canonical_uri = f"{endpoint.path.rstrip('/')}/{encoded_bucket}/{encoded_key}"
    canonical_uri = canonical_uri or "/"

    url = f"{endpoint.scheme}://{endpoint.netloc}{canonical_uri}"
    host = endpoint.netloc
    payload_hash = _file_sha256(file_path)

    canonical_headers = f"host:{host}\nx-amz-content-sha256:{payload_hash}\nx-amz-date:{date_time}"
    signed_headers = "host;x-amz-content-sha256;x-amz-date"

    canonical_request = "\n".join(
        [
            "PUT",
            canonical_uri,
            "",
            canonical_headers,
            signed_headers,
            payload_hash,
        ]
    )

    credential_scope = f"{date_stamp}/{region}/{service}/aws4_request"
    string_to_sign = "\n".join(
        [
            "AWS4-HMAC-SHA256",
            date_time,
            credential_scope,
            hashlib.sha256(canonical_request.encode("utf-8")).hexdigest(),
        ]
    )

    signing_key = _signing_key(
        settings.r2_secret_access_key,
        date_stamp,
        region,
        service,
    )
    signature = hmac.new(
        signing_key,
        string_to_sign.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    authorization = (
        "AWS4-HMAC-SHA256 "
        f"Credential={settings.r2_access_key_id}/{credential_scope}, "
        f"SignedHeaders={signed_headers}, "
        f"Signature={signature}"
    )

    headers = {
        "Authorization": authorization,
        "Content-Type": content_type or "application/octet-stream",
        "Content-Length": str(file_path.stat().st_size),
        "x-amz-content-sha256": payload_hash,
        "x-amz-date": date_time,
    }

    response = await client.put(
        url,
        headers=headers,
        content=_file_chunks(file_path),
    )
    response.raise_for_status()

    return {
        "object_key": key,
        "etag": response.headers.get("ETag"),
        "bytes": file_path.stat().st_size,
        "sha256": payload_hash,
        "storage": "cloudflare-r2",
    }
