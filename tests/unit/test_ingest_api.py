"""POST /v1/ingest and its progress endpoints, with a fake queue."""

import pytest
from fastapi.testclient import TestClient

from patentpath.api.deps import get_ingest_repo, get_manifest, get_queue
from patentpath.api.main import create_app
from patentpath.config import Settings

TOKEN = {"X-Admin-Token": "test-token"}

MANIFEST = [
    {
        "url": f"https://x.test/{n}.pdf",
        "source": "x",
        "licence": "CC BY 4.0",
        "path": f"data/raw/x/{n}.pdf",
        "sha256": str(n) * 64,
        "status": "downloaded",
    }
    for n in (1, 2)
] + [
    {
        "url": "https://x.test/3.pdf",
        "source": "x",
        "licence": "CC BY 4.0",
        "path": "data/raw/x/3.pdf",
        "sha256": "a" * 64,
        "status": "downloaded",
    },
    {
        "url": "https://x.test/4.pdf",
        "source": "x",
        "licence": "CC BY 4.0",
        "path": "data/raw/x/4.pdf",
        "sha256": "4" * 64,
        "status": "failed",
    },
]


@pytest.fixture
def ingest_client(settings, queue, ingest_repo):
    """Client with isolated ingestion dependencies."""
    app = create_app(settings)
    app.dependency_overrides[get_ingest_repo] = lambda: ingest_repo
    app.dependency_overrides[get_queue] = lambda: queue
    app.dependency_overrides[get_manifest] = lambda: MANIFEST

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


def test_start_answers_202_and_queues_one_job_per_new_document(ingest_client, queue, ingest_repo):
    response = ingest_client.post(
        "/v1/ingest",
        json={"limit": 10},
        headers=TOKEN,
    )
    assert response.status_code == 202
    assert response.json() == {
        "job_id": "job1",
        "queued": 2,
        "status_url": "/v1/ingest/job1",
    }
    assert queue.items == [1, 2]
    urls = [record["url"] for record in ingest_repo.jobs["job1"]]
    assert urls == ["https://x.test/1.pdf", "https://x.test/2.pdf"]


def test_start_needs_the_admin_token(ingest_client, queue):
    assert ingest_client.post("/v1/ingest", json={}).status_code == 401

    wrong = ingest_client.post(
        "/v1/ingest",
        json={},
        headers={"X-Admin-Token": "wrong"},
    )
    assert wrong.status_code == 401
    assert wrong.headers["content-type"] == "application/problem+json"
    assert queue.items == []


def test_without_a_configured_token_ingestion_is_closed_outside_your_laptop():
    settings = Settings(
        app_env="production",
        database_url="postgresql://localhost:5432/unused",
        admin_token="",
        _env_file=None,
    )
    with TestClient(create_app(settings)) as public:
        assert public.post("/v1/ingest", json={}).status_code == 403


def test_nothing_new_is_a_plain_200(ingest_client, queue, ingest_repo):
    ingest_repo.known |= {"f-" + "1" * 20, "f-" + "2" * 20}

    response = ingest_client.post(
        "/v1/ingest",
        json={},
        headers=TOKEN,
    )
    assert response.status_code == 200
    assert response.json()["queued"] == 0
    assert queue.items == []


def test_limit_and_source_are_respected_and_validated(ingest_client, queue):
    response = ingest_client.post(
        "/v1/ingest",
        json={"limit": 1},
        headers=TOKEN,
    )
    assert response.status_code == 202
    assert response.json()["queued"] == 1
    assert queue.items == [1]

    response = ingest_client.post(
        "/v1/ingest",
        json={"source": "somewhere-else"},
        headers=TOKEN,
    )
    assert response.status_code == 200
    assert response.json()["queued"] == 0

    assert (
        ingest_client.post(
            "/v1/ingest",
            json={"limit": 0},
            headers=TOKEN,
        ).status_code
        == 422
    )


def test_retry_failed_queues_the_dead_letter_list_again(ingest_client, queue, ingest_repo):
    response = ingest_client.post(
        "/v1/ingest",
        json={"retry_failed": True},
        headers=TOKEN,
    )
    assert response.status_code == 202
    assert response.json()["queued"] == 1
    assert ingest_repo.jobs["job1"][0]["url"] == "https://x.test/bad.pdf"
    assert queue.items == [1]


def test_progress_is_public_and_an_unknown_job_is_a_404_problem(ingest_client):
    response = ingest_client.post(
        "/v1/ingest",
        json={},
        headers=TOKEN,
    )
    job_id = response.json()["job_id"]

    progress = ingest_client.get(f"/v1/ingest/{job_id}")
    assert progress.status_code == 200
    assert progress.json()["counts"]["queued"] == 2

    missing = ingest_client.get("/v1/ingest/no-such-job")
    assert missing.status_code == 404
    assert missing.headers["content-type"] == "application/problem+json"


def test_dead_letter_lists_what_failed_for_good(ingest_client):
    response = ingest_client.get("/v1/ingest/dead-letter")
    assert response.status_code == 200
    assert response.json() == {
        "count": 1,
        "items": [
            {
                "item": 7,
                "job_id": "old",
                "url": "https://x.test/bad.pdf",
                "path": "data/raw/x/bad.pdf",
                "attempts": 3,
                "error": "parse: corrupt",
            }
        ],
    }


def test_when_redis_is_away_starting_is_a_503_and_the_rest_still_works(settings, ingest_repo):
    settings.redis_url = "redis://127.0.0.1:1"
    app = create_app(settings)
    app.dependency_overrides[get_ingest_repo] = lambda: ingest_repo
    app.dependency_overrides[get_manifest] = lambda: [
        {
            "url": "https://x.test/9.pdf",
            "sha256": "9" * 64,
            "status": "downloaded",
        }
    ]

    with TestClient(app) as lonely:
        response = lonely.post(
            "/v1/ingest",
            json={},
            headers=TOKEN,
        )
        assert response.status_code == 503
        assert "Redis" in response.json()["detail"]
        assert lonely.get("/health").status_code == 200

    app.dependency_overrides.clear()
