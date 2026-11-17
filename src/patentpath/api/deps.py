"""FastAPI dependencies for application services."""

from typing import Annotated

from fastapi import Depends, HTTPException, Request

from patentpath.store import RecordStore


def get_store(request: Request) -> RecordStore:
    """Get the record store from application state."""
    store = getattr(request.app.state, "store", None)

    if store is None:
        raise HTTPException(
            status_code=503,
            detail="Record store is not available.",
        )

    return store


StoreDependency = Annotated[RecordStore, Depends(get_store)]
