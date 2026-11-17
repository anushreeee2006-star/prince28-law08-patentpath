"""Document listing, searching, and retrieval endpoints."""

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from patentpath.api.deps import StoreDependency

router = APIRouter(prefix="/v1/documents", tags=["Documents"])


@router.get("")
async def list_documents(
    store: StoreDependency,
    q: str | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    """List documents with optional search and pagination."""

    records = store.list_records()

    if q:
        search_text = q.casefold()
        records = [
            record
            for record in records
            if search_text in " ".join(str(value) for value in record.values()).casefold()
        ]

    total = len(records)
    items = records[offset : offset + limit]

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": items,
    }


@router.get("/{document_id}")
async def get_document(
    document_id: str,
    store: StoreDependency,
) -> dict[str, Any]:
    """Retrieve a document using its ID."""

    document = store.get_record(document_id)

    if document is None:
        raise HTTPException(
            status_code=404,
            detail=f"No document with ID {document_id}",
        )

    return document
