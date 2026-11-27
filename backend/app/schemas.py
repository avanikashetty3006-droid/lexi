from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, Field, field_validator

AmbiguityType = Literal[
    "lexical",
    "syntactic",
    "semantic",
    "contextual",
    "anaphoric",
]
DomainType = Literal["general", "requirements"]
ResolutionBasis = Literal["none", "context", "clarification"]


class HistoryMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(..., min_length=1)


class ClarificationInput(BaseModel):
    question: str = Field(..., min_length=1)
    answer: str = Field(..., min_length=1)


class AnalyzeRequest(BaseModel):
    sentence: str = Field(..., min_length=1)
    history: list[HistoryMessage] = Field(default_factory=list)
    domain: DomainType = "general"
    threshold: float | None = Field(default=None, ge=0.0, le=1.0)
    clarification: ClarificationInput | None = None

    @field_validator("sentence")
    @classmethod
    def strip_non_empty(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("sentence must not be blank")
        return cleaned


class AmbiguitySpan(BaseModel):
    type: AmbiguityType
    span: str
    start: int = Field(..., ge=0)
    end: int = Field(..., ge=0)
    explanation: str


class Interpretation(BaseModel):
    id: str
    meaning: str
    probability: float = Field(..., ge=0.0, le=1.0)


class UncertaintyInfo(BaseModel):
    vote_split: dict[str, float]
    semantic_entropy: float = Field(..., ge=0.0)


class SemanticMapPoint(BaseModel):
    id: str
    x: float
    y: float
    label: str


class AnalyzeResponse(BaseModel):
    sentence: str
    ambiguous: bool
    confidence: float = Field(..., ge=0.0, le=1.0)
    ambiguities: list[AmbiguitySpan]
    interpretations: list[Interpretation] = Field(..., min_length=1)
    uncertainty: UncertaintyInfo
    semantic_map: list[SemanticMapPoint]
    needs_clarification: bool
    clarification_question: str | None = None
    options: list[str]
    resolved_interpretation_id: str | None = None
    resolution_basis: ResolutionBasis
    threshold_used: float = Field(..., ge=0.0, le=1.0)
    latency_ms: int = Field(..., ge=0)


class BaselineRequest(BaseModel):
    sentence: str = Field(..., min_length=1)

    @field_validator("sentence")
    @classmethod
    def strip_non_empty(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("sentence must not be blank")
        return cleaned


class BaselineResponse(BaseModel):
    ambiguous: bool
    chosen_meaning: str
