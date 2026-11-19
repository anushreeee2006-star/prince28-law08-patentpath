"""Fixtures for PostgreSQL integration tests."""

import os
from collections.abc import AsyncIterator, Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from patentpath.api.main import create_app
from patentpath.db.models import Base
from patentpath.db.session import get_db
from patentpath.db.url import to_asyncpg_url


@pytest.fixture
def test_database_url() -> str:
    return os.getenv(
        "TEST_DATABASE_URL",
        "postgresql://app:app@localhost:5433/app_test",  # pragma: allowlist secret
    )


@pytest.fixture
async def db_session_factory(
    test_database_url: str,
) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(
        to_asyncpg_url(test_database_url),
        pool_pre_ping=True,
    )

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    yield factory

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest.fixture
def client(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> Iterator[TestClient]:
    async def override_get_db():
        async with db_session_factory() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
