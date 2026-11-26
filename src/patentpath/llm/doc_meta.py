from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints, field_validator

ShortValue = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=80),
]

FormValue = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=20,
        pattern=r"^Form\s+\d+[A-Z]?$",
    ),
]

ShortValues = Annotated[list[ShortValue], Field(max_length=8)]
FormValues = Annotated[list[FormValue], Field(max_length=8)]


class DocMeta(BaseModel):
    model_config = {"extra": "forbid"}

    doc_kind: Literal[
        "guideline",
        "rule",
        "notice",
        "list",
        "report",
        "faq",
        "form",
        "tutorial",
        "reference",
        "other",
    ]

    year: Annotated[int, Field(ge=1950, le=2027)] | None = None
    language: Literal["en", "ta", "hi", "other"]
    summary: Annotated[str, Field(min_length=20, max_length=300)]
    topics: Annotated[list[ShortValue], Field(min_length=1, max_length=6)]

    section: ShortValues = Field(default_factory=list)
    rule: ShortValues = Field(default_factory=list)
    form: FormValues = Field(default_factory=list)
    fee_category: ShortValues = Field(default_factory=list)
    topic: ShortValues = Field(default_factory=list)

    @field_validator("topics")
    @classmethod
    def lowercase_and_deduplicate_topics(cls, values: list[str]) -> list[str]:
        result: list[str] = []
        seen: set[str] = set()

        for value in values:
            normalized = value.lower()
            if normalized not in seen:
                seen.add(normalized)
                result.append(normalized)

        return result
