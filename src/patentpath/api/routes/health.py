"""Health and readiness endpoints."""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter(tags=["Health"])


@router.get("/health")
async def health():
    """Check whether the application is running."""
    return {"status": "ok"}


@router.get("/ready")
async def ready(request: Request):
    """Check whether the application is ready to serve requests."""
    store = getattr(request.app.state, "store", None)

    records_loaded = store is not None and len(store.records) > 0

    response = {
        "status": "ok" if records_loaded else "not_ready",
        "checks": {
            "records_loaded": records_loaded,
        },
    }

    return JSONResponse(
        status_code=200 if records_loaded else 503,
        content=response,
    )
