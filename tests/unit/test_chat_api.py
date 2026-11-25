"""Tests for the chat and usage API."""

import pytest

from patentpath.api.deps import get_gateway, get_usage_repository
from patentpath.llm.gateway import LLMResult


def make_result() -> LLMResult:
    return LLMResult(
        text="A provisional patent protects an early invention disclosure.",
        provider="groq",
        model="test-model",
        tokens_in=20,
        tokens_out=12,
        latency_ms=100,
        attempts=1,
        fallback_used=False,
        cost_inr=0.0,
    )


class FakeGateway:
    async def generate(self, messages, **options):
        return make_result()

    async def stream(self, messages, **options):
        yield "A provisional patent "
        yield "protects an early invention disclosure."
        yield make_result()


class FakeUsageRepository:
    async def by_day(self, days):
        return [{"date": "2026-11-25", "calls": 2}]


@pytest.fixture
def fake_gateway(client):
    gateway = FakeGateway()
    client.app.dependency_overrides[get_gateway] = lambda: gateway
    yield gateway
    client.app.dependency_overrides.pop(get_gateway, None)


def test_chat_non_streaming(client, fake_gateway):
    response = client.post(
        "/v1/chat",
        json={"message": "What is a provisional patent?", "stream": False},
    )

    assert response.status_code == 200
    body = response.json()
    assert "provisional patent" in body["answer"]
    assert body["summary"]["provider"] == "groq"


def test_chat_streaming(client, fake_gateway):
    response = client.post(
        "/v1/chat",
        json={"message": "What is a provisional patent?", "stream": True},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "event: delta" in response.text
    assert "event: done" in response.text
    assert "A provisional patent" in response.text


def test_chat_rejects_empty_message(client, fake_gateway):
    response = client.post(
        "/v1/chat",
        json={"message": "", "stream": False},
    )

    assert response.status_code == 422


def test_usage_endpoint(client):
    client.app.dependency_overrides[get_usage_repository] = lambda: FakeUsageRepository()

    response = client.get("/v1/usage?days=7")

    client.app.dependency_overrides.pop(get_usage_repository, None)

    assert response.status_code == 200
    assert response.json()["days"] == 7
    assert response.json()["items"][0]["calls"] == 2


def test_usage_rejects_invalid_days(client):
    response = client.get("/v1/usage?days=0")

    assert response.status_code == 422
