from __future__ import annotations

import time

from app.config import settings
from app.engine.confidence import run_vote_confidence
from app.engine.detector import detect_ambiguity
from app.engine.interpreter import build_interpretations
from app.engine.llm import LLMClient, default_llm_client
from app.schemas import (
    AnalyzeRequest,
    AnalyzeResponse,
    ResolutionBasis,
    SemanticMapPoint,
    UncertaintyInfo,
)


def build_fallback_semantic_map(interpretations: list) -> list[SemanticMapPoint]:
    """Provide deterministic placeholder coordinates until embeddings.py is wired in."""
    if len(interpretations) == 1:
        return [
            SemanticMapPoint(
                id=interpretations[0].id,
                x=0.0,
                y=0.0,
                label=interpretations[0].meaning,
            )
        ]
    points: list[SemanticMapPoint] = []
    for idx, interp in enumerate(interpretations):
        x = -1.0 + (2.0 * idx / max(1, len(interpretations) - 1))
        y = 0.25 if idx % 2 == 0 else -0.25
        points.append(SemanticMapPoint(id=interp.id, x=round(x, 4), y=round(y, 4), label=interp.meaning))
    return points


async def analyze_sentence(
    request: AnalyzeRequest,
    llm_client: LLMClient | None = None,
) -> AnalyzeResponse:
    """Execute the core Lexi analysis pipeline: Detect -> Vote -> Decide."""
    started = time.perf_counter()
    threshold_used = (
        request.threshold if request.threshold is not None else settings.threshold
    )

    ambiguous, ambiguities, raw_interps, question, options = await detect_ambiguity(
        sentence=request.sentence,
        history=request.history,
        domain=request.domain,
        clarification=request.clarification,
        llm_client=llm_client or default_llm_client,
    )

    resolution_basis: ResolutionBasis = "none"
    if not ambiguous:
        if request.clarification is not None:
            resolution_basis = "clarification"
        elif request.history:
            resolution_basis = "context"

        vote_split = {"i1": 1.0}
        confidence = 1.0
        interpretations = build_interpretations(raw_interps, ambiguous=False, vote_split=vote_split)
        needs_clarification = False
        clarification_question = None
        final_options: list[str] = []
        resolved_id: str | None = "i1"
    else:
        vote_split, confidence, top_id = await run_vote_confidence(
            sentence=request.sentence,
            history=request.history,
            domain=request.domain,
            interpretations=raw_interps,
            llm_client=llm_client or default_llm_client,
        )
        interpretations = build_interpretations(raw_interps, ambiguous=True, vote_split=vote_split)
        needs_clarification = confidence < threshold_used
        if needs_clarification:
            clarification_question = question
            final_options = options
            resolved_id = None
        else:
            clarification_question = None
            final_options = []
            resolved_id = top_id
            if request.clarification is not None:
                resolution_basis = "clarification"
            elif request.history:
                resolution_basis = "context"

    latency_ms = int((time.perf_counter() - started) * 1000)

    return AnalyzeResponse(
        sentence=request.sentence,
        ambiguous=ambiguous,
        confidence=confidence,
        ambiguities=ambiguities,
        interpretations=interpretations,
        uncertainty=UncertaintyInfo(
            vote_split=vote_split,
            semantic_entropy=0.0,
        ),
        semantic_map=build_fallback_semantic_map(interpretations),
        needs_clarification=needs_clarification,
        clarification_question=clarification_question,
        options=final_options,
        resolved_interpretation_id=resolved_id,
        resolution_basis=resolution_basis,
        threshold_used=threshold_used,
        latency_ms=latency_ms,
    )
