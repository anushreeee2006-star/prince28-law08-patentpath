"""FastAPI dependencies for database, LLM, and ingestion access."""

import asyncio
import json
import secrets
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from patentpath.config import Settings
from patentpath.db.ingest_jobs import IngestRepository
from patentpath.db.llm_calls import UsageRepository
from patentpath.db.repository import DocumentRepository
from patentpath.llm.gateway import LLMGateway
from patentpath.workers.queue import Queue


def get_app_settings(request: Request) -> Settings:
    return request.app.state.settings


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    """One session per request, closed automatically afterwards."""
    async with request.app.state.sessionmaker() as session:
        yield session


async def get_repo(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> DocumentRepository:
    return DocumentRepository(session)


async def check_db(request: Request) -> bool:
    """Check whether SELECT 1 succeeds within two seconds."""
    try:
        async with request.app.state.engine.connect() as conn:
            await asyncio.wait_for(
                conn.execute(text("SELECT 1")),
                timeout=2.0,
            )
        return True
    except Exception:
        return False


def get_gateway(request: Request) -> LLMGateway:
    return request.app.state.gateway


async def get_usage_repo(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> UsageRepository:
    return UsageRepository(session)


async def get_ingest_repo(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> IngestRepository:
    return IngestRepository(session)


async def get_queue(request: Request) -> Queue:
    """Connect to Redis lazily, so the API can start without Redis."""
    state = request.app.state
    if getattr(state, "queue", None) is None:
        try:
            state.queue = await Queue.connect(state.settings.redis_url)
        except Exception as exc:
            detail = "The job queue (Redis) cannot be reached."
            raise HTTPException(status_code=503, detail=detail) from exc
    return state.queue


def get_manifest(request: Request) -> list[dict]:
    """Return the newest manifest record for each URL."""
    path = request.app.state.settings.manifest_file
    if not path.is_file():
        return []

    latest: dict[str, dict] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(record, dict) and isinstance(record.get("url"), str):
            latest[record["url"]] = record

    return list(latest.values())


def require_admin(
    request: Request,
    x_admin_token: Annotated[str, Header()] = "",
) -> None:
    """Protect ingestion endpoints with the configured admin token."""
    settings: Settings = request.app.state.settings

    if not settings.admin_token:
        if settings.app_env == "local":
            return
        raise HTTPException(
            status_code=403,
            detail="Set ADMIN_TOKEN before enabling ingestion.",
        )

    if not secrets.compare_digest(x_admin_token, settings.admin_token):
        raise HTTPException(
            status_code=401,
            detail="Missing or wrong X-Admin-Token.",
        )


SettingsDep = Annotated[Settings, Depends(get_app_settings)]
IngestRepoDep = Annotated[IngestRepository, Depends(get_ingest_repo)]
QueueDep = Annotated[Queue, Depends(get_queue)]
ManifestDep = Annotated[list[dict], Depends(get_manifest)]
GatewayDep = Annotated[LLMGateway, Depends(get_gateway)]
UsageDep = Annotated[UsageRepository, Depends(get_usage_repo)]
RepoDep = Annotated[DocumentRepository, Depends(get_repo)]
DbCheckDep = Annotated[bool, Depends(check_db)]

# Backwards-compatible aliases used by the existing routes.
DatabaseDependency = Annotated[AsyncSession, Depends(get_session)]
RepositoryDependency = Annotated[
    DocumentRepository,
    Depends(get_repo),
]
GatewayDependency = GatewayDep
UsageDependency = UsageDep

# Backwards-compatible names used by existing tests.
get_repository = get_repo
get_usage_repository = get_usage_repo
