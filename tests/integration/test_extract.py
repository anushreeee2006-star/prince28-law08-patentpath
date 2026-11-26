"""Integration tests for metadata extraction storage and resume behavior."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from patentpath.db.models import Document, Page
from patentpath.llm.doc_meta import DocMeta
from patentpath.llm.extract import Extraction, document_text, pending, save


@pytest.mark.asyncio
async def test_extraction_merges_metadata_and_skips_same_prompt(
    db_session_factory: async_sessionmaker[AsyncSession],
):
    async with db_session_factory() as session:
        document = Document(
            external_id="extract-test-001",
            title="Patent Filing Guideline",
            source_url="https://example.org/guideline.pdf",
            licence="CC BY 4.0",
            doc_type="pdf",
            sha256="ab" * 32,
            metadata_={
                "source": "example",
                "path": "data/raw/example/guideline.pdf",
                "parser": "pymupdf",
                "pages": 1,
            },
        )
        session.add(document)
        await session.flush()

        session.add(
            Page(
                document_id=document.id,
                page_no=1,
                text="Patent filing guideline text for metadata extraction.",
                headings=["Patent Filing"],
            )
        )
        await session.flush()

        assert await document_text(session, document) == (
            "Patent filing guideline text for metadata extraction."
        )

        meta = DocMeta(
            doc_kind="guideline",
            year=2024,
            language="en",
            summary="This guideline explains patent filing procedures and requirements.",
            topics=["Patent Filing", "Forms"],
            section=["Section 3"],
            rule=[],
            form=["Form 1"],
            fee_category=[],
            topic=[],
        )
        extraction = Extraction(
            meta=meta,
            model="test-model",
            attempts=1,
            tokens_in=10,
            tokens_out=20,
            cost_inr=0.01,
        )

        await save(
            session,
            document,
            prompt_version="extract_v1",
            extraction=extraction,
        )

        await session.refresh(document)
        assert document.metadata_["source"] == "example"
        assert document.metadata_["path"] == "data/raw/example/guideline.pdf"
        assert document.metadata_["parser"] == "pymupdf"
        assert document.metadata_["pages"] == 1
        assert document.metadata_["doc_kind"] == "guideline"
        assert document.metadata_["topics"] == ["patent filing", "forms"]
        assert document.metadata_["extract"]["prompt"] == "extract_v1"
        assert document.metadata_["extract"]["model"] == "test-model"

        waiting = await pending(session, "extract_v1")
        assert document not in waiting

        other_version = await pending(session, "extract_v2")
        assert document in other_version


@pytest.mark.asyncio
async def test_extraction_failure_is_saved_and_can_be_retried(
    db_session_factory: async_sessionmaker[AsyncSession],
):
    async with db_session_factory() as session:
        document = Document(
            external_id="extract-test-002",
            title="Patent Rules",
            source_url="https://example.org/rules.pdf",
            licence="CC BY 4.0",
            doc_type="pdf",
            sha256="cd" * 32,
            metadata_={"source": "example", "pages": 1},
        )
        session.add(document)
        await session.flush()

        await save(
            session,
            document,
            prompt_version="extract_v1",
            error="Model response could not be validated",
        )

        await session.refresh(document)
        assert document.metadata_["source"] == "example"
        assert document.metadata_["extract"]["error"] == ("Model response could not be validated")

        no_retry = await pending(session, "extract_v1")
        assert document not in no_retry

        retry = await pending(session, "extract_v1", retry_failed=True)
        assert document in retry
