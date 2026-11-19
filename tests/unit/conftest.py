"""Shared pytest fixtures for API tests."""

import pytest
from fastapi.testclient import TestClient

from patentpath.api.deps import get_repository
from patentpath.api.main import create_app
from patentpath.api.routes import health
from patentpath.config import Settings


@pytest.fixture
def sample_records():
    """Return predictable patent records for testing."""
    return [
        {
            "id": "TEST001",
            "section": "10",
            "rule": "13",
            "form": "Form 2",
            "fee_category": None,
            "topic": "Patent specification",
        },
        {
            "id": "TEST002",
            "section": "11A",
            "rule": "24A",
            "form": "Form 9",
            "fee_category": None,
            "topic": "Patent publication",
        },
        {
            "id": "TEST003",
            "section": "11B",
            "rule": "24B",
            "form": "Form 18",
            "fee_category": None,
            "topic": "Patent examination",
        },
    ]


class FakeDocumentRepository:
    """In-memory repository for isolated API tests."""

    def __init__(self, records):
        self.records = records

    async def list(self, *, q, filters, limit, offset):
        records = self.records

        if q:
            records = [
                record
                for record in records
                if q.casefold() in " ".join(str(value) for value in record.values()).casefold()
            ]

        for key, value in filters.items():
            records = [
                record
                for record in records
                if str(record.get(key, "")).casefold() == value.casefold()
            ]

        total = len(records)
        return total, records[offset : offset + limit]

    async def get(self, external_id):
        return next(
            (record for record in self.records if record["id"] == external_id),
            None,
        )


class FakeDatabaseSession:
    """Fake successful database session for readiness tests."""

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        return None

    async def execute(self, statement):
        return None


@pytest.fixture
def client(monkeypatch, sample_records):
    """Create an API client with isolated test dependencies."""

    app = create_app(Settings(app_env="ci"))

    repository = FakeDocumentRepository(sample_records)
    app.dependency_overrides[get_repository] = lambda: repository

    monkeypatch.setattr(
        health,
        "AsyncSessionLocal",
        FakeDatabaseSession,
    )

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
