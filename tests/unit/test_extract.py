"""Unit tests for structured metadata extraction."""

from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from patentpath.llm.doc_meta import DocMeta
from patentpath.llm.extract import extract, parse_json

VALID_JSON = """
{
  "doc_kind": "guideline",
  "year": 2024,
  "language": "en",
  "summary": "This guideline explains patent filing procedures and requirements.",
  "topics": ["Patent Filing", "Forms"],
  "section": ["Section 3"],
  "rule": [],
  "form": ["Form 1"],
  "fee_category": [],
  "topic": []
}
"""


class StubGateway:
    """Return scripted responses without making network calls."""

    def __init__(self, *responses: str):
        self.responses = list(responses)
        self.calls = []

    async def generate(self, messages, **kwargs):
        self.calls.append((messages, kwargs))
        response = self.responses.pop(0)
        return SimpleNamespace(
            text=response,
            model="test-model",
            tokens_in=10,
            tokens_out=20,
            cost_inr=0.01,
        )


def test_parse_json_reads_plain_json():
    assert parse_json('{"answer": 42}') == {"answer": 42}


def test_parse_json_reads_markdown_fenced_json():
    result = parse_json('```json\n{"answer": 42}\n```')
    assert result == {"answer": 42}


def test_parse_json_rejects_text_without_json():
    with pytest.raises(ValueError, match="No JSON object found"):
        parse_json("No structured response here.")


def test_doc_meta_accepts_valid_metadata():
    metadata = DocMeta.model_validate(parse_json(VALID_JSON))
    assert metadata.doc_kind == "guideline"
    assert metadata.year == 2024
    assert metadata.form == ["Form 1"]
    assert metadata.topics == ["patent filing", "forms"]


def test_doc_meta_rejects_extra_fields():
    data = parse_json(VALID_JSON)
    data["unexpected"] = "not allowed"
    with pytest.raises(ValidationError):
        DocMeta.model_validate(data)


def test_doc_meta_rejects_year_outside_range():
    data = parse_json(VALID_JSON)
    data["year"] = 1949
    with pytest.raises(ValidationError):
        DocMeta.model_validate(data)


@pytest.mark.asyncio
async def test_extract_returns_validated_metadata():
    gateway = StubGateway(VALID_JSON)

    result = await extract(
        gateway,
        "Extract metadata as JSON.",
        "extract_v1",
        "Patent filing guideline text.",
    )

    assert result.meta.doc_kind == "guideline"
    assert result.model == "test-model"
    assert result.attempts == 1
    assert result.tokens_in == 10
    assert result.tokens_out == 20
    assert result.cost_inr == 0.01
    assert len(gateway.calls) == 1


@pytest.mark.asyncio
async def test_extract_retries_after_invalid_json():
    gateway = StubGateway("not json", VALID_JSON)

    result = await extract(
        gateway,
        "Extract metadata as JSON.",
        "extract_v1",
        "Patent filing guideline text.",
    )

    assert result.meta.doc_kind == "guideline"
    assert result.attempts == 2
    assert len(gateway.calls) == 2


def test_extraction_prompt_mentions_all_metadata_fields():
    from pathlib import Path

    prompt = Path("prompts/extract_v1.md").read_text(encoding="utf-8").lower()
    required_fields = {
        "doc_kind",
        "year",
        "language",
        "summary",
        "topics",
        "section",
        "rule",
        "form",
        "fee_category",
        "topic",
    }

    for field in required_fields:
        assert field in prompt, f"Prompt is missing field: {field}"
