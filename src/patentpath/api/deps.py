"""FastAPI dependencies for database access."""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from patentpath.db.repository import DocumentRepository
from patentpath.db.session import get_db

DatabaseDependency = Annotated[AsyncSession, Depends(get_db)]


def get_repository(
    session: DatabaseDependency,
) -> DocumentRepository:
    """Get the document repository for the current request."""
    return DocumentRepository(session)


RepositoryDependency = Annotated[
    DocumentRepository,
    Depends(get_repository),
]
