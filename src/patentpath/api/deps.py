"""FastAPI dependencies for database and LLM access."""

from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from patentpath.db.llm_calls import UsageRepository
from patentpath.db.repository import DocumentRepository
from patentpath.db.session import get_db
from patentpath.llm.gateway import LLMGateway

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


def get_gateway(request: Request) -> LLMGateway:
    """Get the configured LLM gateway from the application."""
    return request.app.state.gateway


GatewayDependency = Annotated[
    LLMGateway,
    Depends(get_gateway),
]


def get_usage_repository(
    session: DatabaseDependency,
) -> UsageRepository:
    """Get the LLM usage repository for the current request."""
    return UsageRepository(session)


UsageDependency = Annotated[
    UsageRepository,
    Depends(get_usage_repository),
]
