"""Optional integration tests against a dedicated PostgreSQL test database."""

import os

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from patentpath.db.models import Base, Document
from patentpath.db.repository import DocumentRepository
from patentpath.db.url import to_asyncpg_url

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="TEST_DATABASE_URL is not configured",
)


@pytest.fixture
async def db_session():
    """Create an isolated schema for integration tests."""
    engine = create_async_engine(to_asyncpg_url(TEST_DATABASE_URL))

    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        session_factory = async_sessionmaker(engine, expire_on_commit=False)

        async with session_factory() as session:
            yield session

    finally:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.drop_all)

        await engine.dispose()


@pytest.fixture
async def repository(db_session):
    return DocumentRepository(db_session)


@pytest.mark.anyio
async def test_repository_get_document(repository, db_session):
    document = Document(
        external_id="INTEGRATION001",
        title="Integration patent",
        sha256="a" * 64,
        metadata_={"section": "10"},
    )
    db_session.add(document)
    await db_session.commit()

    result = await repository.get("INTEGRATION001")

    assert result is not None
    assert result["id"] == "INTEGRATION001"
    assert result["title"] == "Integration patent"


@pytest.mark.anyio
async def test_repository_filter_by_metadata(repository, db_session):
    db_session.add_all(
        [
            Document(
                external_id="INTEGRATION002",
                title="Patent A",
                sha256="b" * 64,
                metadata_={"section": "10"},
            ),
            Document(
                external_id="INTEGRATION003",
                title="Patent B",
                sha256="c" * 64,
                metadata_={"section": "11"},
            ),
        ]
    )
    await db_session.commit()

    total, items = await repository.list(
        q=None,
        filters={"section": "10"},
        limit=20,
        offset=0,
    )

    assert total == 1
    assert items[0]["id"] == "INTEGRATION002"


@pytest.mark.anyio
async def test_repository_get_missing_document(repository):
    result = await repository.get("DOES_NOT_EXIST")

    assert result is None
