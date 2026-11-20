"""Health and readiness endpoints."""

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from patentpath.config import get_settings
from patentpath.db.session import AsyncSessionLocal

router = APIRouter(tags=["Health"])


@router.get("/health")
async def health():
    """Check whether the application is running and identify its version."""
    settings = get_settings()
    return {
        "status": "ok",
        "git_sha": settings.git_sha,
    }


@router.get("/ready")
async def ready():
    """Check whether the database is ready."""
    database_ready = False

    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        database_ready = True
    except Exception:
        database_ready = False

    response = {
        "status": "ready" if database_ready else "not_ready",
        "checks": {
            "database": database_ready,
        },
    }

    return JSONResponse(
        status_code=200 if database_ready else 503,
        content=response,
    )
