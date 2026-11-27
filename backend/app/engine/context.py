from __future__ import annotations

import json
from pydantic import BaseModel

from app.config import settings
from app.engine.llm import LLMClient, default_llm_client, load_prompt
from app.schemas import AnalyzeRequest, ClarificationInput, HistoryMessage, ResolutionBasis


class ContextResolutionResult(BaseModel):
    resolved: bool
    resolved_meaning: str
    matched_option_index: int | None = None


async def resolve_clarification(
    *,
    sentence: str,
    history: list[HistoryMessage],
    clarification: ClarificationInput,
    llm_client: LLMClient | None = None,
) -> ContextResolutionResult:
    """Resolve ambiguity when the user provides an explicit clarification answer."""
    client = llm_client or default_llm_client
    system_prompt = load_prompt("context_resolve")
    payload = json.dumps(
        {
            "sentence": sentence,
            "history": [{"role": m.role, "content": m.content} for m in history],
            "clarification": {
                "question": clarification.question,
                "answer": clarification.answer,
            },
        },
        ensure_ascii=False,
    )
    return await client.call_json(
        system_prompt=system_prompt,
        user_prompt=payload,
        temperature=settings.temperature_detect,
        schema_model=ContextResolutionResult,
        max_tokens=512,
        seed=settings.seed,
    )


def determine_resolution_basis(
    request: AnalyzeRequest,
    ambiguous: bool,
    needs_clarification: bool,
) -> ResolutionBasis:
    """Compute contract-compliant resolution_basis from request context and outcome."""
    if needs_clarification:
        return "none"
    if request.clarification is not None and not ambiguous:
        return "clarification"
    if request.history and not ambiguous:
        return "context"
    if request.clarification is not None:
        return "clarification"
    if request.history:
        return "context"
    return "none"
