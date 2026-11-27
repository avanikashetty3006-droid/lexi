from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from app.config import settings
from app.engine.anaphora import detect_anaphora, has_anaphora_candidates
from app.engine.clarifier import prepare_clarification
from app.engine.confidence import run_vote_confidence
from app.engine.context import determine_resolution_basis, resolve_clarification
from app.engine.detector import RawInterpretationItem, detect_ambiguity
from app.engine.embeddings import EmbedFn, analyze_semantic_space
from app.engine.interpreter import build_interpretations
from app.engine.llm import LLMClient, default_llm_client
from app.schemas import (
    AnalyzeRequest,
    AnalyzeResponse,
    AmbiguitySpan,
    UncertaintyInfo,
)


def log_interaction(
    request: AnalyzeRequest,
    response: AnalyzeResponse,
    log_path: Path | None = None,
) -> None:
    """Append each /analyze request, response, and latency_ms to interactions.jsonl."""
    target = log_path or settings.interactions_log_path
    target.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "provider": settings.llm_provider,
        "model": settings.model_name,
        "latency_ms": response.latency_ms,
        "request": request.model_dump(),
        "response": response.model_dump(),
    }
    with target.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def _merge_anaphora(
    *,
    ambiguous: bool,
    ambiguities: list[AmbiguitySpan],
    raw_interps: list[RawInterpretationItem],
    question: str | None,
    options: list[str],
    ana_ambiguous: bool,
    ana_spans: list[AmbiguitySpan],
    ana_meanings: list[str],
) -> tuple[bool, list[AmbiguitySpan], list[RawInterpretationItem], str | None, list[str]]:
    """Merge dual-resolver anaphora findings into detection output without duplicating spans."""
    if not ana_ambiguous or not ana_spans:
        return ambiguous, ambiguities, raw_interps, question, options

    existing_keys = {(a.type, a.start, a.end) for a in ambiguities}
    merged_spans = list(ambiguities)
    for span in ana_spans:
        if (span.type, span.start, span.end) not in existing_keys:
            merged_spans.append(span)

    if not ambiguous and len(ana_meanings) >= 2:
        merged_interps = [
            RawInterpretationItem(id=f"i{idx}", meaning=m)
            for idx, m in enumerate(ana_meanings[:4], start=1)
        ]
        target_pronoun = ana_spans[0].span
        return (
            True,
            merged_spans,
            merged_interps,
            f"Who or what does '{target_pronoun}' refer to?",
            [m[:65] for m in ana_meanings[:4]],
        )

    return True, merged_spans, raw_interps, question, options


async def analyze_sentence(
    request: AnalyzeRequest,
    llm_client: LLMClient | None = None,
    embed_fn: EmbedFn | None = None,
    log_path: Path | None = None,
    enable_logging: bool = True,
) -> AnalyzeResponse:
    """Execute full Lexi pipeline: Context -> Detect(+Anaphora) -> Vote -> Embed -> Decide -> Log."""
    started = time.perf_counter()
    client = llm_client or default_llm_client
    threshold_used = (
        request.threshold if request.threshold is not None else settings.threshold
    )

    # 1. Explicit clarification resolution path
    if request.clarification is not None:
        ctx_res = await resolve_clarification(
            sentence=request.sentence,
            history=request.history,
            clarification=request.clarification,
            llm_client=client,
        )
        if ctx_res.resolved and ctx_res.resolved_meaning.strip():
            raw_interps = [
                RawInterpretationItem(id="i1", meaning=ctx_res.resolved_meaning.strip())
            ]
            vote_split = {"i1": 1.0}
            interpretations = build_interpretations(
                raw_interps, ambiguous=False, vote_split=vote_split
            )
            semantic_entropy, semantic_map = analyze_semantic_space(
                interpretations, embed_fn=embed_fn
            )
            latency_ms = int((time.perf_counter() - started) * 1000)
            response = AnalyzeResponse(
                sentence=request.sentence,
                ambiguous=False,
                confidence=1.0,
                ambiguities=[],
                interpretations=interpretations,
                uncertainty=UncertaintyInfo(
                    vote_split=vote_split,
                    semantic_entropy=semantic_entropy,
                ),
                semantic_map=semantic_map,
                needs_clarification=False,
                clarification_question=None,
                options=[],
                resolved_interpretation_id="i1",
                resolution_basis="clarification",
                threshold_used=threshold_used,
                latency_ms=latency_ms,
            )
            if enable_logging:
                log_interaction(request, response, log_path=log_path)
            return response

    # 2. Detect + dual-resolver anaphora check (concurrent when pronoun candidates exist)
    run_anaphora = has_anaphora_candidates(request.sentence, request.history)
    detect_coro = detect_ambiguity(
        sentence=request.sentence,
        history=request.history,
        domain=request.domain,
        clarification=request.clarification,
        llm_client=client,
    )
    if run_anaphora:
        (
            (ambiguous, ambiguities, raw_interps, question, options),
            (ana_ambiguous, ana_spans, ana_meanings),
        ) = await asyncio.gather(
            detect_coro,
            detect_anaphora(
                sentence=request.sentence,
                history=request.history,
                llm_client=client,
            ),
        )
        ambiguous, ambiguities, raw_interps, question, options = _merge_anaphora(
            ambiguous=ambiguous,
            ambiguities=ambiguities,
            raw_interps=raw_interps,
            question=question,
            options=options,
            ana_ambiguous=ana_ambiguous,
            ana_spans=ana_spans,
            ana_meanings=ana_meanings,
        )
    else:
        ambiguous, ambiguities, raw_interps, question, options = await detect_coro

    # 3. Vote + Embed + Decide
    if not ambiguous:
        vote_split = {"i1": 1.0}
        confidence = 1.0
        interpretations = build_interpretations(
            raw_interps, ambiguous=False, vote_split=vote_split
        )
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
            llm_client=client,
        )
        interpretations = build_interpretations(
            raw_interps, ambiguous=True, vote_split=vote_split
        )
        needs_clarification = confidence < threshold_used
        if needs_clarification:
            clarification_question, final_options = await prepare_clarification(
                sentence=request.sentence,
                ambiguities=ambiguities,
                interpretations=interpretations,
                draft_question=question,
                draft_options=options,
                llm_client=client,
            )
            resolved_id = None
        else:
            clarification_question = None
            final_options = []
            resolved_id = top_id

    semantic_entropy, semantic_map = analyze_semantic_space(
        interpretations, embed_fn=embed_fn
    )
    resolution_basis = determine_resolution_basis(
        request, ambiguous=ambiguous, needs_clarification=needs_clarification
    )
    latency_ms = int((time.perf_counter() - started) * 1000)

    response = AnalyzeResponse(
        sentence=request.sentence,
        ambiguous=ambiguous,
        confidence=confidence,
        ambiguities=ambiguities,
        interpretations=interpretations,
        uncertainty=UncertaintyInfo(
            vote_split=vote_split,
            semantic_entropy=semantic_entropy,
        ),
        semantic_map=semantic_map,
        needs_clarification=needs_clarification,
        clarification_question=clarification_question,
        options=final_options,
        resolved_interpretation_id=resolved_id,
        resolution_basis=resolution_basis,
        threshold_used=threshold_used,
        latency_ms=latency_ms,
    )
    if enable_logging:
        log_interaction(request, response, log_path=log_path)
    return response
