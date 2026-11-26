"""Tests for the chat and usage API."""

from pathlib import Path

import pytest

from patentpath.api.deps import get_gateway, get_usage_repository
from patentpath.llm.gateway import FakeLLM, LLMGateway, LLMResult, LLMUnavailable


def make_result() -> LLMResult:
    return LLMResult(
        text="A provisional patent protects an early invention disclosure.",
        provider="groq",
        model="test-model",
        tokens_in=20,
        tokens_out=12,
        latency_ms=100,
        attempts=2,
        fallback_used=True,
        cost_inr=0.25,
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
        return [
            {
                "day": "2026-11-25",
                "calls": 2,
                "errors": 0,
                "fallbacks": 1,
                "tokens_in": 40,
                "tokens_out": 24,
                "cost_inr": 0.25,
            }
        ]


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
    assert body["provider"] == "groq"
    assert body["attempts"] == 2
    assert body["fallback_used"] is True


def test_chat_streaming(client, fake_gateway):
    response = client.post(
        "/v1/chat",
        json={"message": "What is a provisional patent?", "stream": True},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert '"delta": "A provisional patent "' in response.text
    assert "event: done" in response.text
    assert '"provider": "groq"' in response.text


def test_prompt_contains_uncertainty_instruction():
    prompt = Path("prompts/chat_system_v1.md").read_text(encoding="utf-8")
    assert "If you are not sure, say" in prompt


def test_chat_rejects_empty_message(client, fake_gateway):
    response = client.post(
        "/v1/chat",
        json={"message": "", "stream": False},
    )

    assert response.status_code == 422


def test_chat_returns_503_when_model_unavailable(client):
    class UnavailableGateway:
        async def generate(self, messages, **options):
            raise LLMUnavailable("No provider available")

    client.app.dependency_overrides[get_gateway] = lambda: UnavailableGateway()

    response = client.post(
        "/v1/chat",
        json={"message": "Explain patentability", "stream": False},
    )

    client.app.dependency_overrides.pop(get_gateway, None)
    assert response.status_code == 503


def test_chat_stream_reports_midstream_error(client):
    class BrokenStreamGateway:
        async def generate(self, messages, **options):
            return type("FakeResult", (), {"text": "docs"})()

        async def stream(self, messages, **options):
            yield "Partial answer "
            raise LLMUnavailable("Provider failed mid-answer")

    client.app.dependency_overrides[get_gateway] = lambda: BrokenStreamGateway()

    response = client.post(
        "/v1/chat",
        json={"message": "Explain patentability", "stream": True},
    )

    client.app.dependency_overrides.pop(get_gateway, None)
    assert response.status_code == 200
    assert "event: error" in response.text
    assert "stopped while generating the answer" in response.text


def test_usage_endpoint(client):
    client.app.dependency_overrides[get_usage_repository] = lambda: FakeUsageRepository()

    response = client.get("/v1/usage?days=7")

    client.app.dependency_overrides.pop(get_usage_repository, None)

    assert response.status_code == 200
    body = response.json()
    assert body["days"][0]["calls"] == 2
    assert body["total_cost_inr"] == 0.25
    assert body["calls"] == 2


def test_llm_status_returns_configured_providers(client):
    gateway = LLMGateway(
        [
            FakeLLM("gemini", "gemini-3.8-flash"),
            FakeLLM("groq", "openai/gpt-oss-20b"),
        ]
    )
    client.app.state.gateway = gateway

    response = client.get("/v1/llm/status")

    assert response.status_code == 200
    assert response.json() == {
        "providers": [
            {
                "name": "gemini",
                "model": "gemini-3.8-flash",
                "breaker_state": "closed",
            },
            {
                "name": "groq",
                "model": "openai/gpt-oss-20b",
                "breaker_state": "closed",
            },
        ]
    }


def test_llm_status_reports_open_breaker(client):
    gateway = LLMGateway(
        [
            FakeLLM("gemini", "gemini-3.8-flash"),
            FakeLLM("groq", "openai/gpt-oss-20b"),
        ]
    )
    for _ in range(3):
        gateway.breakers["gemini"].failure()
    client.app.state.gateway = gateway

    response = client.get("/v1/llm/status")

    assert response.status_code == 200
    providers = response.json()["providers"]
    assert providers[0]["breaker_state"] == "open"
    assert providers[1]["breaker_state"] == "closed"
