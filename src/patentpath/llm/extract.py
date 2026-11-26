"""Extract structured metadata from parsed patent documents."""

import json
import re
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from patentpath.db.models import Document, Page
from patentpath.llm.doc_meta import DocMeta
from patentpath.llm.gateway import LLMResult


def parse_json(text: str) -> dict[str, Any]:
    """Parse a JSON object from an LLM response."""
    text = text.strip()

    # Remove a surrounding Markdown code fence, if present.
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text)

    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        # Try to recover a JSON object embedded in extra text.
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("No JSON object found in model response") from None
        value = json.loads(text[start : end + 1])

    if not isinstance(value, dict):
        raise ValueError("Model response must be a JSON object")

    return value


def explain(error: ValidationError | ValueError) -> str:
    """Return a concise, readable validation error for repair prompts."""
    if isinstance(error, ValidationError):
        details = [
            f"{'.'.join(str(part) for part in item['loc'])}: {item['msg']}"
            for item in error.errors()
        ]
        return "; ".join(details[:8])

    return str(error)[:500]


@dataclass
class Extraction:
    """Validated metadata and model usage for one extraction."""

    meta: DocMeta
    model: str
    attempts: int
    tokens_in: int = 0
    tokens_out: int = 0
    cost_inr: float = 0.0
    last_result: LLMResult | None = None


async def extract(
    gateway: Any,
    prompt: str,
    version: str,
    text: str,
    *,
    use_schema: bool = False,
) -> Extraction:
    """Ask the LLM for metadata and repair invalid JSON up to three attempts."""
    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": text[:6000]},
    ]
    last_error = "No response received"
    last_result = None

    for attempt in range(1, 4):
        options: dict[str, Any] = {"temperature": 0}
        if use_schema:
            options["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": "document_metadata",
                    "strict": True,
                    "schema": DocMeta.model_json_schema(),
                },
            }

        if attempt > 1:
            messages.append(
                {
                    "role": "user",
                    "content": (
                        "Your previous response was invalid. Fix these issues: "
                        f"{last_error}. Return only corrected JSON."
                    ),
                }
            )

        last_result = await gateway.generate(
            messages,
            purpose="extract",
            prompt_version=version,
            **options,
        )

        try:
            data = parse_json(last_result.text)
            meta = DocMeta.model_validate(data)
        except (ValueError, ValidationError) as exc:
            last_error = explain(exc)
            messages.append({"role": "assistant", "content": last_result.text})
            continue

        return Extraction(
            meta=meta,
            model=last_result.model,
            attempts=attempt,
            tokens_in=last_result.tokens_in,
            tokens_out=last_result.tokens_out,
            cost_inr=last_result.cost_inr,
            last_result=last_result,
        )

    raise ValueError(f"Metadata extraction failed after 3 attempts: {last_error}")


async def pending(
    session: AsyncSession,
    prompt_version: str,
    *,
    retry_failed: bool = False,
    limit: int | None = None,
) -> list[Document]:
    """Return parsed documents not yet extracted with this prompt version."""
    stmt = select(Document).where(Document.doc_type != "record").order_by(Document.external_id)
    documents = list(await session.scalars(stmt))
    result: list[Document] = []

    for doc in documents:
        metadata = doc.metadata_ or {}
        previous = metadata.get("extract") or {}

        if previous.get("error"):
            if not retry_failed:
                continue
        elif previous.get("prompt") == prompt_version:
            continue

        result.append(doc)
        if limit is not None and len(result) >= limit:
            break

    return result


async def document_text(
    session: AsyncSession,
    doc: Document,
    max_chars: int = 6000,
) -> str:
    """Return text from the first three pages, limited to max_chars."""
    stmt = select(Page).where(Page.document_id == doc.id).order_by(Page.page_no).limit(3)
    pages = list(await session.scalars(stmt))
    text = "\n\n".join(page.text for page in pages)
    return text[:max_chars]


async def save(
    session: AsyncSession,
    doc: Document,
    *,
    prompt_version: str,
    extraction: Extraction | None = None,
    error: str | None = None,
) -> None:
    """Merge extracted metadata without replacing ingestion metadata."""
    metadata = dict(doc.metadata_ or {})
    reserved = {
        "source",
        "path",
        "parser",
        "pages",
        "tables",
        "chars",
        "extract",
    }

    if extraction is not None:
        extracted = extraction.meta.model_dump()
        metadata.update({key: value for key, value in extracted.items() if key not in reserved})
        metadata["extract"] = {
            "prompt": prompt_version,
            "model": extraction.model,
            "attempts": extraction.attempts,
        }
    else:
        metadata["extract"] = {
            "prompt": prompt_version,
            "error": (error or "Unknown extraction error")[:500],
        }

    doc.metadata_ = metadata
    await session.commit()


async def run(
    gateway: Any,
    prompt: str,
    prompt_version: str,
    *,
    limit: int | None = None,
    rpm: int = 12,
    chars: int = 6000,
    retry_failed: bool = False,
    use_schema: bool = False,
) -> dict[str, int | float]:
    """Extract metadata for pending documents and return run statistics."""
    import asyncio

    from patentpath.db.session import AsyncSessionLocal
    from patentpath.llm.gateway import LLMUnavailable

    if rpm < 1:
        raise ValueError("rpm must be at least 1")

    stats: dict[str, int | float] = {
        "selected": 0,
        "success": 0,
        "failed": 0,
        "tokens_in": 0,
        "tokens_out": 0,
        "cost_inr": 0.0,
    }
    delay = 60.0 / rpm
    consecutive_unavailable = 0

    async with AsyncSessionLocal() as session:
        documents = await pending(
            session,
            prompt_version,
            retry_failed=retry_failed,
            limit=limit,
        )
        stats["selected"] = len(documents)

        for index, doc in enumerate(documents):
            if index:
                await asyncio.sleep(delay)

            text = await document_text(session, doc, max_chars=chars)
            if not text.strip():
                await save(
                    session,
                    doc,
                    prompt_version=prompt_version,
                    error="No text available for metadata extraction",
                )
                stats["failed"] += 1
                consecutive_unavailable = 0
                continue

            try:
                extraction = await extract(
                    gateway,
                    prompt,
                    prompt_version,
                    text,
                    use_schema=use_schema,
                )
                await save(
                    session,
                    doc,
                    prompt_version=prompt_version,
                    extraction=extraction,
                )
                stats["success"] += 1
                stats["tokens_in"] += extraction.tokens_in
                stats["tokens_out"] += extraction.tokens_out
                stats["cost_inr"] += extraction.cost_inr
                consecutive_unavailable = 0
            except Exception as error:
                await save(
                    session,
                    doc,
                    prompt_version=prompt_version,
                    error=str(error),
                )
                stats["failed"] += 1

                if isinstance(error, LLMUnavailable):
                    consecutive_unavailable += 1
                    if consecutive_unavailable >= 2:
                        break
                else:
                    consecutive_unavailable = 0

    return stats
