
"""Shared pytest fixtures for API tests."""

import json

import pytest
from fastapi.testclient import TestClient

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


@pytest.fixture
def client(tmp_path, sample_records):
    """Create a test client with temporary patent data."""
    data_file = tmp_path / "sample_records.json"
    data_file.write_text(
        json.dumps(sample_records),
        encoding="utf-8",
    )

    settings = Settings(
        app_env="ci",
        data_file=data_file,
    )

    app = create_app(settings)

    with TestClient(app) as test_client:
        yield test_client
