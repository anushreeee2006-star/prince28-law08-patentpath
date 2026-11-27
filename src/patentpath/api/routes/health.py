"""Health and readiness endpoints."""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from patentpath.api.deps import DbCheckDep, SettingsDep

router = APIRouter(tags=["Health"])


@router.api_route("/health", methods=["GET", "HEAD"])
async def health(settings: SettingsDep) -> dict:
    """Check whether the application is running and identify its version."""
    return {
        "status": "ok",
        "git_sha": settings.git_sha,
    }


@router.get("/ready")
async def ready(database_ready: DbCheckDep):
    """Check whether the application database is ready."""
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
