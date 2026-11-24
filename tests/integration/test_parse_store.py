"""Integration tests for parsed document and failure storage."""

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from patentpath.db.models import Document, Page, ParseFailure
from patentpath.ingest.parse import ParsedDoc, ParsedPage, ParseError
from patentpath.ingest.store import (
    document_id,
    parsed_ids,
    save_document,
    save_failure,
)

RECORD = {
    "url": "https://example.org/fever.pdf",
    "source": "example",
    "licence": "CC BY 4.0",
    "title": "",
    "path": "data/raw/example/fever-1a2b3c4d.pdf",
    "sha256": "ab" * 32,
}

PARSED = ParsedDoc(
    parser="pymupdf",
    kind="pdf",
    title="Fever Guidelines",
    scanned_pages=[2],
    pages=[
        ParsedPage(
            1,
            "# Fever Guidelines\n\n## Dengue\n\nRest and fluids.",
            [],
        ),
        ParsedPage(
            2,
            "Review after two days.",
            ["Fever Guidelines", "Dengue"],
        ),
    ],
)


@pytest.mark.asyncio
async def test_save_document_with_pages_and_headings(
    db_session_factory: async_sessionmaker[AsyncSession],
):
    async with db_session_factory() as session:
        await save_document(session, RECORD, PARSED)

        document = await session.scalar(
            select(Document).where(Document.external_id == document_id(RECORD["sha256"]))
        )

        assert document is not None
        assert document.title == "Fever Guidelines"
        assert document.doc_type == "pdf"
        assert document.metadata_["pages"] == 2
        assert document.metadata_["scanned_pages"] == [2]

        pages = list(
            await session.scalars(
                select(Page).where(Page.document_id == document.id).order_by(Page.page_no)
            )
        )

        assert len(pages) == 2
        assert pages[0].page_no == 1
        assert pages[1].page_no == 2
        assert pages[1].headings == ["Fever Guidelines", "Dengue"]
        assert document_id(RECORD["sha256"]) in await parsed_ids(session)


@pytest.mark.asyncio
async def test_save_failure_increments_attempts(
    db_session_factory: async_sessionmaker[AsyncSession],
):
    async with db_session_factory() as session:
        error = ParseError("corrupt", "The PDF file is damaged.")

        await save_failure(session, RECORD, error)
        await save_failure(session, RECORD, error)

        failure = await session.scalar(
            select(ParseFailure).where(ParseFailure.path == RECORD["path"])
        )

        assert failure is not None
        assert failure.reason == "corrupt"
        assert failure.attempts == 2


@pytest.mark.asyncio
async def test_successful_parse_clears_previous_failure(
    db_session_factory: async_sessionmaker[AsyncSession],
):
    async with db_session_factory() as session:
        error = ParseError("corrupt", "The PDF file is damaged.")

        await save_failure(session, RECORD, error)
        await save_document(session, RECORD, PARSED)

        failure = await session.scalar(
            select(ParseFailure).where(ParseFailure.path == RECORD["path"])
        )

        document = await session.scalar(
            select(Document).where(Document.external_id == document_id(RECORD["sha256"]))
        )

        assert failure is None
        assert document is not None
        assert document.title == "Fever Guidelines"
