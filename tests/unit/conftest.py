"""Shared pytest fixtures for API tests."""

import pytest
from fastapi.testclient import TestClient

from patentpath.api.deps import check_db, get_repo
from patentpath.api.main import create_app
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

    async def get_page(self, external_id, page_no):
        if external_id == "TEST001" and page_no == 2:
            return {
                "document_id": external_id,
                "page_no": 2,
                "text": "Patent specification page two.",
                "headings": ["Patent Specification", "Claims"],
            }
        return None


@pytest.fixture
def client(sample_records):
    """Create an API client with isolated test dependencies."""
    settings = Settings(app_env="ci", _env_file=None)
    app = create_app(settings)

    repository = FakeDocumentRepository(sample_records)

    app.dependency_overrides[get_repo] = lambda: repository
    app.dependency_overrides[check_db] = lambda: True

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
