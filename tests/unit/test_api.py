"""Tests for PatentPath API endpoints."""

from patentpath.llm.gateway import FakeLLM


def test_health_is_ok(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_health_includes_git_sha(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["git_sha"] == "dev"


def test_ready_endpoint(client):
    response = client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "checks": {"database": True},
    }


def test_list_documents(client):
    response = client.get("/v1/documents")

    assert response.status_code == 200
    data = response.json()

    assert data["total"] == 3
    assert len(data["items"]) == 3


def test_list_documents_pagination(client):
    response = client.get("/v1/documents?limit=1&offset=1")

    assert response.status_code == 200
    data = response.json()

    assert data["total"] == 3
    assert data["limit"] == 1
    assert data["offset"] == 1
    assert data["items"][0]["id"] == "TEST002"


def test_search_documents(client):
    response = client.get("/v1/documents?q=publication")

    assert response.status_code == 200
    data = response.json()

    assert data["total"] == 1
    assert data["items"][0]["id"] == "TEST002"


def test_search_is_case_insensitive(client):
    response = client.get("/v1/documents?q=PATENT")

    assert response.status_code == 200
    assert response.json()["total"] == 3


def test_get_document_by_id(client):
    response = client.get("/v1/documents/TEST001")

    assert response.status_code == 200
    assert response.json()["topic"] == "Patent specification"


def test_get_unknown_document(client):
    response = client.get("/v1/documents/UNKNOWN")

    assert response.status_code == 404
    assert response.json()["title"] == "Not Found"
    assert response.json()["detail"] == "No document with ID UNKNOWN"


def test_invalid_limit(client):
    response = client.get("/v1/documents?limit=0")

    assert response.status_code == 422
    assert response.json()["title"] == "Unprocessable Entity"


def test_invalid_offset(client):
    response = client.get("/v1/documents?offset=-1")

    assert response.status_code == 422
    assert response.json()["title"] == "Unprocessable Entity"


def test_filter_by_section(client):
    response = client.get("/v1/documents?section=10")

    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["id"] == "TEST001"


def test_filter_by_rule(client):
    response = client.get("/v1/documents?rule=24A")

    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["id"] == "TEST002"


def test_filter_by_form(client):
    response = client.get("/v1/documents?form=Form%209")

    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["id"] == "TEST002"


def test_multiple_filters(client):
    response = client.get("/v1/documents?section=10&rule=13")

    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["id"] == "TEST001"


def test_invalid_filter_name(client):
    response = client.get("/v1/documents?Bad-Name=1")

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid filter name: Bad-Name"


def test_search_no_results(client):
    response = client.get("/v1/documents?q=nonexistent")

    assert response.status_code == 200
    assert response.json()["total"] == 0
    assert response.json()["items"] == []


def test_get_document_page(client):
    response = client.get("/v1/documents/TEST001/pages?page_no=2")

    assert response.status_code == 200
    assert response.json() == {
        "document_id": "TEST001",
        "page_no": 2,
        "text": "Patent specification page two.",
        "headings": ["Patent Specification", "Claims"],
    }


def test_get_missing_document_page(client):
    response = client.get("/v1/documents/UNKNOWN/pages?page_no=2")

    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["title"] == "Not Found"


def test_personal_question_is_classified_and_not_answered_by_chat(client):
    fake = FakeLLM(script=["personal"])
    client.app.state.gateway = fake

    response = client.post(
        "/v1/chat",
        json={"message": "Will my patent be granted?", "stream": False},
    )

    assert response.status_code == 200
    assert response.json()["answer"] == ("I can't know that from PatentPath's documents.")
    assert fake.calls == 1
    assert fake.seen[0]["purpose"] == "classify"


def test_off_topic_question_is_classified_and_not_answered_by_chat(client):
    fake = FakeLLM(script=["off_topic"])
    client.app.state.gateway = fake

    response = client.post(
        "/v1/chat",
        json={"message": "Tell me a joke about cricket.", "stream": False},
    )

    assert response.status_code == 200
    assert response.json()["answer"] == ("I can only help with Indian patent-related questions.")
    assert fake.calls == 1
    assert fake.seen[0]["purpose"] == "classify"
