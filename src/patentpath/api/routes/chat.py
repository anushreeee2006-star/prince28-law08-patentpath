"""POST /v1/chat and GET /v1/usage."""

import json
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from patentpath.api.deps import GatewayDependency, UsageDependency
from patentpath.llm.classify import classify
from patentpath.llm.gateway import LLMResult, LLMUnavailable

router = APIRouter(prefix="/v1", tags=["Chat"])

PROMPT_VERSION = "chat_system_v1"
PERSONAL_ANSWER = "I can't know that from PatentPath's documents."
OFF_TOPIC_ANSWER = "I can only help with Indian patent-related questions."


class ChatRequest(BaseModel):
    """A single user message to PatentPath."""

    message: str = Field(min_length=1, max_length=4000)
    stream: bool = True


def result_summary(result: LLMResult) -> dict[str, Any]:
    """Return model metadata without duplicating the answer."""
    return {
        "provider": result.provider,
        "model": result.model,
        "tokens_in": result.tokens_in,
        "tokens_out": result.tokens_out,
        "latency_ms": result.latency_ms,
        "attempts": result.attempts,
        "fallback_used": result.fallback_used,
        "cost_inr": result.cost_inr,
    }


def sse(data: dict[str, Any], event: str = "") -> str:
    """Encode one server-sent event."""
    head = f"event: {event}\n" if event else ""
    return f"{head}data: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("/chat")
async def chat(
    body: ChatRequest,
    request: Request,
    gateway: GatewayDependency,
):
    """Answer a PatentPath question, optionally streaming."""
    try:
        label, _ = await classify(
            gateway,
            request.app.state.classify_prompt,
            request.app.state.classify_prompt_version,
            body.message,
        )
    except LLMUnavailable as exc:
        raise HTTPException(
            status_code=503,
            detail="PatentPath's language models are temporarily unavailable.",
        ) from exc

    if label == "personal":
        return {"answer": PERSONAL_ANSWER}
    if label == "off_topic":
        return {"answer": OFF_TOPIC_ANSWER}

    messages = [
        {"role": "system", "content": request.app.state.system_prompt},
        {"role": "user", "content": body.message},
    ]

    if not body.stream:
        try:
            result = await gateway.generate(
                messages,
                purpose="chat",
                prompt_version=PROMPT_VERSION,
                temperature=0.2,
            )
        except LLMUnavailable as exc:
            raise HTTPException(
                status_code=503,
                detail="PatentPath's language models are temporarily unavailable.",
            ) from exc

        return {"answer": result.text, **result_summary(result)}

    stream = gateway.stream(
        messages,
        purpose="chat",
        prompt_version=PROMPT_VERSION,
        temperature=0.2,
    )

    try:
        first = await anext(stream)
    except LLMUnavailable as exc:
        raise HTTPException(
            status_code=503,
            detail="PatentPath's language models are temporarily unavailable.",
        ) from exc

    async def events() -> AsyncIterator[str]:
        item: str | LLMResult = first

        try:
            while True:
                if isinstance(item, LLMResult):
                    yield sse(result_summary(item), event="done")
                    return

                yield sse({"delta": item})
                item = await anext(stream)

        except LLMUnavailable:
            yield sse(
                {"detail": "The model stopped while generating the answer."},
                event="error",
            )

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/usage")
async def usage(
    repository: UsageDependency,
    days: int = Query(default=7, ge=1, le=90),
):
    """Return daily LLM usage and estimated costs."""
    rows = await repository.by_day(days)

    return {
        "days": rows,
        "total_cost_inr": round(sum(row["cost_inr"] for row in rows), 4),
        "calls": sum(row["calls"] for row in rows),
    }
