"""Document listing, searching, and retrieval endpoints."""

from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request

from patentpath.api.deps import RepositoryDependency
from patentpath.db.repository import FILTER_KEY

router = APIRouter(prefix="/v1/documents", tags=["Documents"])


@router.get("")
async def list_documents(
    repository: RepositoryDependency,
    request: Request,
    q: str | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    """List documents with optional search, filters, and pagination."""

    filters: dict[str, str] = {}

    for key, value in request.query_params.items():
        if key in {"q", "limit", "offset"}:
            continue

        if not FILTER_KEY.fullmatch(key):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid filter name: {key}",
            )

        filters[key] = value

    total, items = await repository.list(
        q=q,
        filters=filters,
        limit=limit,
        offset=offset,
    )

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "filters": filters,
        "items": items,
    }


@router.get("/{document_id}")
async def get_document(
    document_id: str,
    repository: RepositoryDependency,
) -> dict[str, Any]:
    """Retrieve a document using its ID."""

    document = await repository.get(document_id)

    if document is None:
        raise HTTPException(
            status_code=404,
            detail=f"No document with ID {document_id}",
        )

    return document
