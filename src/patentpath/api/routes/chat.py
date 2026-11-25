"""Chat and LLM usage endpoints."""

import json
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from patentpath.api.deps import GatewayDependency, UsageDependency
from patentpath.llm.gateway import LLMResult, LLMUnavailable

router = APIRouter(prefix="/v1", tags=["Chat"])

PROMPT_VERSION = "chat_system_v1"


class ChatRequest(BaseModel):
    """A single user message to PatentPath."""

    message: str = Field(min_length=1, max_length=4000)
    stream: bool = True


def result_summary(result: LLMResult) -> dict[str, Any]:
    """Return model-call metadata without duplicating the answer text."""
    return {
        "provider": result.provider,
        "model": result.model,
        "tokens_in": result.tokens_in,
        "tokens_out": result.tokens_out,
        "latency_ms": result.latency_ms,
        "fallback_used": result.fallback_used,
        "cost_inr": result.cost_inr,
    }


def sse(event: str, data: dict[str, Any]) -> str:
    """Encode one Server-Sent Event."""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("/chat")
async def chat(
    body: ChatRequest,
    request: Request,
    gateway: GatewayDependency,
):
    """Answer a PatentPath question, optionally streaming the response."""
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

        return {
            "answer": result.text,
            "summary": result_summary(result),
        }

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

    async def events():
        try:
            if isinstance(first, str):
                yield sse("delta", {"text": first})
            elif isinstance(first, LLMResult):
                yield sse("done", {"summary": result_summary(first)})
                return

            async for item in stream:
                if isinstance(item, str):
                    yield sse("delta", {"text": item})
                elif isinstance(item, LLMResult):
                    yield sse("done", {"summary": result_summary(item)})
        except LLMUnavailable:
            yield sse(
                "error",
                {"message": "The model stopped while generating the answer."},
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
    return {
        "days": days,
        "items": await repository.by_day(days),
    }
