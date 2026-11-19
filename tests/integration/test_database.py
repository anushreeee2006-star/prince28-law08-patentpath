"""Integration tests for the PostgreSQL document repository."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from patentpath.db.models import Document
from patentpath.db.repository import DocumentRepository


async def insert_document(
    session: AsyncSession,
    external_id: str,
    title: str,
    metadata: dict,
) -> None:
    """Insert a document into the real PostgreSQL database."""
    session.add(
        Document(
            external_id=external_id,
            title=title,
            doc_type="record",
            sha256="a" * 64,
            metadata_=metadata,
        )
    )
    await session.commit()


@pytest.mark.asyncio
async def test_insert_and_get_document(
    db_session_factory: async_sessionmaker[AsyncSession],
):
    async with db_session_factory() as session:
        await insert_document(
            session,
            "integration-001",
            "Patent application",
            {"section": "12"},
        )

        repository = DocumentRepository(session)
        document = await repository.get("integration-001")

        assert document is not None
        assert document["id"] == "integration-001"
        assert document["title"] == "Patent application"


@pytest.mark.asyncio
async def test_get_unknown_document(
    db_session_factory: async_sessionmaker[AsyncSession],
):
    async with db_session_factory() as session:
        repository = DocumentRepository(session)

        assert await repository.get("does-not-exist") is None


@pytest.mark.asyncio
async def test_list_documents_and_count(
    db_session_factory: async_sessionmaker[AsyncSession],
):
    async with db_session_factory() as session:
        await insert_document(session, "doc-001", "Patent rules", {})
        await insert_document(session, "doc-002", "Trademark rules", {})

        repository = DocumentRepository(session)
        total, documents = await repository.list(
            q=None,
            filters={},
            limit=20,
            offset=0,
        )

        assert total == 2
        assert len(documents) == 2


@pytest.mark.asyncio
async def test_search_documents_in_postgresql(
    db_session_factory: async_sessionmaker[AsyncSession],
):
    async with db_session_factory() as session:
        await insert_document(
            session,
            "search-001",
            "Patent examination manual",
            {},
        )
        await insert_document(
            session,
            "search-002",
            "Trademark examination manual",
            {},
        )

        repository = DocumentRepository(session)
        total, documents = await repository.list(
            q="patent",
            filters={},
            limit=20,
            offset=0,
        )

        assert total == 1
        assert documents[0]["id"] == "search-001"


@pytest.mark.asyncio
async def test_search_is_case_insensitive(
    db_session_factory: async_sessionmaker[AsyncSession],
):
    async with db_session_factory() as session:
        await insert_document(
            session,
            "case-001",
            "PATENT LAW",
            {},
        )

        repository = DocumentRepository(session)
        total, documents = await repository.list(
            q="patent",
            filters={},
            limit=20,
            offset=0,
        )

        assert total == 1
        assert documents[0]["id"] == "case-001"


@pytest.mark.asyncio
async def test_filter_documents_by_jsonb_metadata(
    db_session_factory: async_sessionmaker[AsyncSession],
):
    async with db_session_factory() as session:
        await insert_document(
            session,
            "filter-001",
            "Document one",
            {"section": "12", "rule": "3"},
        )
        await insert_document(
            session,
            "filter-002",
            "Document two",
            {"section": "15", "rule": "4"},
        )

        repository = DocumentRepository(session)
        total, documents = await repository.list(
            q=None,
            filters={"section": "12"},
            limit=20,
            offset=0,
        )

        assert total == 1
        assert documents[0]["id"] == "filter-001"


@pytest.mark.asyncio
async def test_list_documents_pagination(
    db_session_factory: async_sessionmaker[AsyncSession],
):
    async with db_session_factory() as session:
        for number in range(3):
            await insert_document(
                session,
                f"page-{number:03}",
                f"Document {number}",
                {},
            )

        repository = DocumentRepository(session)
        total, documents = await repository.list(
            q=None,
            filters={},
            limit=1,
            offset=1,
        )

        assert total == 3
        assert len(documents) == 1
