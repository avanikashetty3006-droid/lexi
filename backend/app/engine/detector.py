from __future__ import annotations

import json
from pydantic import BaseModel, Field

from app.config import settings
from app.engine.llm import LLMClient, default_llm_client, load_prompt
from app.schemas import AmbiguitySpan, AmbiguityType, ClarificationInput, DomainType, HistoryMessage


class RawAmbiguityItem(BaseModel):
    type: AmbiguityType
    span: str
    explanation: str


class RawInterpretationItem(BaseModel):
    id: str
    meaning: str


class RawDetectionResult(BaseModel):
    ambiguous: bool
    ambiguities: list[RawAmbiguityItem] = Field(default_factory=list)
    interpretations: list[RawInterpretationItem] = Field(min_length=1)
    clarification_question: str | None = None
    options: list[str] = Field(default_factory=list)


def locate_span(sentence: str, span: str) -> tuple[str, int, int]:
    """Find deterministic [start, end) character offsets for span in sentence."""
    if not span:
        return sentence, 0, len(sentence)

    idx = sentence.find(span)
    if idx != -1:
        return span, idx, idx + len(span)

    lower_idx = sentence.lower().find(span.lower())
    if lower_idx != -1:
        end = lower_idx + len(span)
        return sentence[lower_idx:end], lower_idx, end

    return sentence, 0, len(sentence)


def format_detection_payload(
    sentence: str,
    history: list[HistoryMessage],
    domain: DomainType,
    clarification: ClarificationInput | None,
) -> str:
    """Serialize request context as structured JSON for the detection prompt."""
    payload = {
        "sentence": sentence,
        "domain": domain,
        "history": [{"role": m.role, "content": m.content} for m in history],
        "clarification": (
            {"question": clarification.question, "answer": clarification.answer}
            if clarification is not None
            else None
        ),
    }
    return json.dumps(payload, ensure_ascii=False)


def normalize_detection(sentence: str, raw: RawDetectionResult) -> tuple[bool, list[AmbiguitySpan], list[RawInterpretationItem], str | None, list[str]]:
    """Enforce contract invariants on raw LLM detection output."""
    if not raw.ambiguous or not raw.ambiguities:
        first_meaning = raw.interpretations[0].meaning.strip()
        return (
            False,
            [],
            [RawInterpretationItem(id="i1", meaning=first_meaning)],
            None,
            [],
        )

    spans: list[AmbiguitySpan] = []
    for item in raw.ambiguities:
        matched_span, start, end = locate_span(sentence, item.span.strip())
        spans.append(
            AmbiguitySpan(
                type=item.type,
                span=matched_span,
                start=start,
                end=end,
                explanation=item.explanation.strip(),
            )
        )

    interps = [
        RawInterpretationItem(id=f"i{idx}", meaning=item.meaning.strip())
        for idx, item in enumerate(raw.interpretations[:4], start=1)
        if item.meaning.strip()
    ]
    if len(interps) < 2:
        # Cannot claim ambiguity with fewer than 2 distinct interpretations.
        return (
            False,
            [],
            [RawInterpretationItem(id="i1", meaning=interps[0].meaning if interps else sentence)],
            None,
            [],
        )

    options = [opt.strip() for opt in raw.options if opt.strip()][: len(interps)]
    if len(options) < 2:
        options = [interp.meaning for interp in interps]

    question = (raw.clarification_question or "").strip() or (
        "Could you clarify which meaning you intended?"
    )
    return True, spans, interps, question, options


async def detect_ambiguity(
    *,
    sentence: str,
    history: list[HistoryMessage],
    domain: DomainType,
    clarification: ClarificationInput | None,
    llm_client: LLMClient | None = None,
) -> tuple[bool, list[AmbiguitySpan], list[RawInterpretationItem], str | None, list[str]]:
    """Run temperature-0 ambiguity detection and normalize spans and interpretations."""
    client = llm_client or default_llm_client
    system_prompt = load_prompt("detect")
    user_prompt = format_detection_payload(sentence, history, domain, clarification)
    raw = await client.call_json(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        temperature=settings.temperature_detect,
        schema_model=RawDetectionResult,
        seed=settings.seed,
    )
    return normalize_detection(sentence, raw)


class PerTypeDetectionResult(BaseModel):
    found: bool
    span: str = ""
    explanation: str = ""
    interpretations: list[str] = Field(default_factory=list)


async def detect_by_type(
    *,
    ambiguity_type: AmbiguityType,
    sentence: str,
    history: list[HistoryMessage],
    domain: DomainType,
    clarification: ClarificationInput | None,
    llm_client: LLMClient | None = None,
) -> tuple[AmbiguitySpan | None, list[str]]:
    """Run targeted single-type ambiguity detection from prompts/detect_per_type.txt."""
    client = llm_client or default_llm_client
    template = load_prompt("detect_per_type")
    system_prompt = template.replace("{ambiguity_type}", ambiguity_type)
    user_prompt = format_detection_payload(sentence, history, domain, clarification)
    res = await client.call_json(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        temperature=settings.temperature_detect,
        schema_model=PerTypeDetectionResult,
        max_tokens=512,
        seed=settings.seed,
    )
    if not res.found or len(res.interpretations) < 2:
        return None, []
    matched_span, start, end = locate_span(sentence, res.span.strip())
    span_obj = AmbiguitySpan(
        type=ambiguity_type,
        span=matched_span,
        start=start,
        end=end,
        explanation=res.explanation.strip() or f"Detected {ambiguity_type} ambiguity.",
    )
    return span_obj, [item.strip() for item in res.interpretations[:4] if item.strip()]

