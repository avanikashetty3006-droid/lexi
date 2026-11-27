from __future__ import annotations

import asyncio
import json
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from app.config import settings
from app.engine.anaphora import detect_anaphora, has_anaphora_candidates
from app.engine.clarifier import prepare_clarification
from app.engine.confidence import run_vote_confidence
from app.engine.context import determine_resolution_basis, resolve_clarification
from app.engine.detector import (
    RawInterpretationItem,
    detect_ambiguity,
    stream_detect_ambiguity,
)
from app.engine.embeddings import EmbedFn, analyze_semantic_space
from app.engine.interpreter import build_interpretations
from app.engine.llm import LLMClient, default_llm_client
from app.schemas import (
    AnalyzeRequest,
    AnalyzeResponse,
    AmbiguitySpan,
    Interpretation,
    SemanticMapPoint,
    UncertaintyInfo,
)

_CACHE_TTL_SECONDS = 120.0
_CACHE_MAX_ENTRIES = 64

_GREETING_PUNCT_RE = re.compile(r"[!.,?]+$")
_GREETING_GROUPS: list[tuple[set[str], str]] = [
    (
        {
            "hi",
            "hey",
            "hello",
            "hii",
            "heya",
            "hi there",
            "hello there",
            "hey there",
            "good morning",
            "good afternoon",
            "good evening",
            "gm",
        },
        "Hi there! How can I help you today?",
    ),
    (
        {"how are you", "how are you doing", "whats up", "what's up", "sup"},
        "I'm doing great, thanks for asking! What would you like to check or chat about?",
    ),
    (
        {"thanks", "thank you", "thx", "ty", "thank u"},
        "You're welcome! Let me know if you need anything else.",
    ),
    (
        {"bye", "goodbye", "see you", "cya"},
        "Goodbye! Feel free to come back anytime.",
    ),
]


@dataclass
class _CachedAnalysis:
    created_at: float
    ambiguous: bool
    confidence: float
    ambiguities: list[AmbiguitySpan]
    interpretations: list[Interpretation]
    vote_split: dict[str, float]
    semantic_entropy: float
    semantic_map: list[SemanticMapPoint]
    draft_question: str | None
    draft_options: list[str]
    top_id: str | None


_ANALYZE_CACHE: dict[str, _CachedAnalysis] = {}


def clear_analyze_cache() -> None:
    """Clear in-memory threshold-reuse analysis cache."""
    _ANALYZE_CACHE.clear()


def match_greeting_reply(request: AnalyzeRequest) -> str | None:
    """Return an instant conversational reply for trivial unambiguous greetings/courtesies."""
    if request.clarification is not None:
        return None
    normalized = _GREETING_PUNCT_RE.sub("", request.sentence.strip().lower()).strip()
    for phrases, reply in _GREETING_GROUPS:
        if normalized in phrases:
            return reply
    return None


def _build_clean_response(
    *,
    request: AnalyzeRequest,
    meaning: str,
    threshold_used: float,
    started: float,
    resolution_basis: str = "none",
    embed_fn: EmbedFn | None = None,
) -> AnalyzeResponse:
    """Construct a contract-compliant clean AnalyzeResponse."""
    raw_interps = [RawInterpretationItem(id="i1", meaning=meaning)]
    vote_split = {"i1": 1.0}
    interpretations = build_interpretations(raw_interps, ambiguous=False, vote_split=vote_split)
    semantic_entropy, semantic_map = analyze_semantic_space(interpretations, embed_fn=embed_fn)
    latency_ms = int((time.perf_counter() - started) * 1000)
    return AnalyzeResponse(
        sentence=request.sentence,
        ambiguous=False,
        confidence=1.0,
        ambiguities=[],
        interpretations=interpretations,
        uncertainty=UncertaintyInfo(vote_split=vote_split, semantic_entropy=semantic_entropy),
        semantic_map=semantic_map,
        needs_clarification=False,
        clarification_question=None,
        options=[],
        resolved_interpretation_id="i1",
        resolution_basis=resolution_basis,  # type: ignore[arg-type]
        threshold_used=threshold_used,
        latency_ms=latency_ms,
    )


def _make_cache_key(request: AnalyzeRequest) -> str:
    payload = {
        "sentence": request.sentence,
        "history": [m.model_dump() for m in request.history],
        "domain": request.domain,
        "clarification": request.clarification.model_dump() if request.clarification else None,
        "model": settings.model_name,
    }
    return json.dumps(payload, sort_keys=True, ensure_ascii=False)


def _get_cached(key: str) -> _CachedAnalysis | None:
    entry = _ANALYZE_CACHE.get(key)
    if entry is None:
        return None
    if (time.monotonic() - entry.created_at) > _CACHE_TTL_SECONDS:
        _ANALYZE_CACHE.pop(key, None)
        return None
    return entry


def _put_cached(key: str, entry: _CachedAnalysis) -> None:
    if len(_ANALYZE_CACHE) >= _CACHE_MAX_ENTRIES:
        oldest_key = min(_ANALYZE_CACHE, key=lambda k: _ANALYZE_CACHE[k].created_at)
        _ANALYZE_CACHE.pop(oldest_key, None)
    _ANALYZE_CACHE[key] = entry


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
            [m[:50] for m in ana_meanings[:4]],
        )

    return True, merged_spans, raw_interps, question, options


def _finalize_from_cached(
    request: AnalyzeRequest,
    cached: _CachedAnalysis,
    threshold_used: float,
    started: float,
) -> AnalyzeResponse:
    """Apply threshold decision on cached detection/vote/embedding outputs."""
    if not cached.ambiguous:
        needs_clarification = False
        clarification_question = None
        final_options: list[str] = []
        resolved_id: str | None = "i1"
    else:
        needs_clarification = cached.confidence < threshold_used
        if needs_clarification:
            clarification_question = cached.draft_question
            final_options = cached.draft_options
            resolved_id = None
        else:
            clarification_question = None
            final_options = []
            resolved_id = cached.top_id

    resolution_basis = determine_resolution_basis(
        request, ambiguous=cached.ambiguous, needs_clarification=needs_clarification
    )
    latency_ms = int((time.perf_counter() - started) * 1000)

    return AnalyzeResponse(
        sentence=request.sentence,
        ambiguous=cached.ambiguous,
        confidence=cached.confidence,
        ambiguities=cached.ambiguities,
        interpretations=cached.interpretations,
        uncertainty=UncertaintyInfo(
            vote_split=cached.vote_split,
            semantic_entropy=cached.semantic_entropy,
        ),
        semantic_map=cached.semantic_map,
        needs_clarification=needs_clarification,
        clarification_question=clarification_question,
        options=final_options,
        resolved_interpretation_id=resolved_id,
        resolution_basis=resolution_basis,
        threshold_used=threshold_used,
        latency_ms=latency_ms,
    )


async def analyze_sentence(
    request: AnalyzeRequest,
    llm_client: LLMClient | None = None,
    embed_fn: EmbedFn | None = None,
    log_path: Path | None = None,
    enable_logging: bool = True,
    use_cache: bool = True,
) -> AnalyzeResponse:
    """Execute full Lexi pipeline: FastPath -> Cache -> Context -> Detect(+Anaphora) -> Vote -> Embed -> Decide -> Log."""
    started = time.perf_counter()
    client = llm_client or default_llm_client
    threshold_used = (
        request.threshold if request.threshold is not None else settings.threshold
    )

    greeting_reply = match_greeting_reply(request)
    if greeting_reply is not None:
        response = _build_clean_response(
            request=request,
            meaning=greeting_reply,
            threshold_used=threshold_used,
            started=started,
            resolution_basis="none",
            embed_fn=embed_fn,
        )
        if enable_logging:
            log_interaction(request, response, log_path=log_path)
        return response

    cache_allowed = use_cache and isinstance(client, LLMClient) and embed_fn is None
    cache_key = _make_cache_key(request) if cache_allowed else ""

    if cache_allowed:
        cached = _get_cached(cache_key)
        if cached is not None:
            response = _finalize_from_cached(request, cached, threshold_used, started)
            if enable_logging:
                log_interaction(request, response, log_path=log_path)
            return response

    # 1. Explicit clarification resolution path
    if request.clarification is not None:
        ctx_res = await resolve_clarification(
            sentence=request.sentence,
            history=request.history,
            clarification=request.clarification,
            llm_client=client,
        )
        if ctx_res.resolved and ctx_res.resolved_meaning.strip():
            response = _build_clean_response(
                request=request,
                meaning=ctx_res.resolved_meaning.strip(),
                threshold_used=threshold_used,
                started=started,
                resolution_basis="clarification",
                embed_fn=embed_fn,
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
    top_id: str | None = "i1"
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
    if cache_allowed:
        draft_q, draft_opts = (
            (clarification_question, final_options)
            if (ambiguous and needs_clarification)
            else (question, options)
        )
        _put_cached(
            cache_key,
            _CachedAnalysis(
                created_at=time.monotonic(),
                ambiguous=ambiguous,
                confidence=confidence,
                ambiguities=ambiguities,
                interpretations=interpretations,
                vote_split=vote_split,
                semantic_entropy=semantic_entropy,
                semantic_map=semantic_map,
                draft_question=draft_q,
                draft_options=draft_opts,
                top_id=top_id,
            ),
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


def format_sse(event: str, payload: dict) -> str:
    """Format a Server-Sent Events (SSE) frame."""
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _extract_reply_text(response: AnalyzeResponse) -> str:
    """Select the primary assistant message text to stream for the chat bubble."""
    if response.needs_clarification and response.clarification_question:
        return response.clarification_question
    rid = response.resolved_interpretation_id
    for interp in response.interpretations:
        if rid and interp.id == rid:
            return interp.meaning
    return response.interpretations[0].meaning if response.interpretations else ""


async def stream_analyze_sentence(
    request: AnalyzeRequest,
    llm_client: LLMClient | None = None,
    embed_fn: EmbedFn | None = None,
    log_path: Path | None = None,
    enable_logging: bool = True,
    use_cache: bool = True,
):
    """
    Async generator streaming real-time SSE progress (`stage`, `vote`), live
    incremental response tokens (`token`), and the final validated `AnalyzeResponse` (`done`).
    """
    started = time.perf_counter()
    client = llm_client or default_llm_client
    threshold_used = (
        request.threshold if request.threshold is not None else settings.threshold
    )

    greeting_reply = match_greeting_reply(request)
    if greeting_reply is not None:
        yield format_sse("stage", {"step": "detected", "ambiguous": False, "ambiguities": [], "interpretations": [{"id": "i1", "meaning": greeting_reply}]})
        for idx, word in enumerate(greeting_reply.split(" ")):
            yield format_sse("token", {"text": ("" if idx == 0 else " ") + word})
        response = _build_clean_response(
            request=request,
            meaning=greeting_reply,
            threshold_used=threshold_used,
            started=started,
            resolution_basis="none",
            embed_fn=embed_fn,
        )
        if enable_logging:
            log_interaction(request, response, log_path=log_path)
        yield format_sse("done", response.model_dump())
        return

    cache_allowed = use_cache and isinstance(client, LLMClient) and embed_fn is None
    cache_key = _make_cache_key(request) if cache_allowed else ""

    yield format_sse("stage", {"step": "detecting", "message": "Checking ambiguity..."})

    try:
        if cache_allowed:
            cached = _get_cached(cache_key)
            if cached is not None:
                response = _finalize_from_cached(request, cached, threshold_used, started)
                text = _extract_reply_text(response)
                for idx, word in enumerate(text.split(" ")):
                    yield format_sse("token", {"text": ("" if idx == 0 else " ") + word})
                if enable_logging:
                    log_interaction(request, response, log_path=log_path)
                yield format_sse("done", response.model_dump())
                return

        if request.clarification is not None:
            ctx_res = await resolve_clarification(
                sentence=request.sentence,
                history=request.history,
                clarification=request.clarification,
                llm_client=client,
            )
            if ctx_res.resolved and ctx_res.resolved_meaning.strip():
                response = _build_clean_response(
                    request=request,
                    meaning=ctx_res.resolved_meaning.strip(),
                    threshold_used=threshold_used,
                    started=started,
                    resolution_basis="clarification",
                    embed_fn=embed_fn,
                )
                for idx, word in enumerate(_extract_reply_text(response).split(" ")):
                    yield format_sse("token", {"text": ("" if idx == 0 else " ") + word})
                if enable_logging:
                    log_interaction(request, response, log_path=log_path)
                yield format_sse("done", response.model_dump())
                return

        run_anaphora = has_anaphora_candidates(request.sentence, request.history)
        streamed_text_parts: list[str] = []

        if run_anaphora:
            (
                (ambiguous, ambiguities, raw_interps, question, options),
                (ana_ambiguous, ana_spans, ana_meanings),
            ) = await asyncio.gather(
                detect_ambiguity(
                    sentence=request.sentence,
                    history=request.history,
                    domain=request.domain,
                    clarification=request.clarification,
                    llm_client=client,
                ),
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
            det_result = None
            async for evt, payload in stream_detect_ambiguity(
                sentence=request.sentence,
                history=request.history,
                domain=request.domain,
                clarification=request.clarification,
                llm_client=client,
            ):
                if evt == "token":
                    streamed_text_parts.append(payload)
                    yield format_sse("token", {"text": payload})
                elif evt == "result":
                    det_result = payload
            ambiguous, ambiguities, raw_interps, question, options = det_result

        yield format_sse(
            "stage",
            {
                "step": "detected",
                "ambiguous": ambiguous,
                "ambiguities": [a.model_dump() for a in ambiguities],
                "interpretations": [{"id": r.id, "meaning": r.meaning} for r in raw_interps],
            },
        )

        top_id: str | None = "i1"
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
            yield format_sse("stage", {"step": "voting", "total_samples": settings.n_samples})
            vote_queue: asyncio.Queue[tuple[int, int, str] | None] = asyncio.Queue()

            async def _push_vote(completed: int, total: int, choice: str) -> None:
                await vote_queue.put((completed, total, choice))

            async def _run_votes():
                try:
                    return await run_vote_confidence(
                        sentence=request.sentence,
                        history=request.history,
                        domain=request.domain,
                        interpretations=raw_interps,
                        llm_client=client,
                        on_vote=_push_vote,
                    )
                finally:
                    await vote_queue.put(None)

            vote_task = asyncio.create_task(_run_votes())
            while True:
                item = await vote_queue.get()
                if item is None:
                    break
                completed, total, choice = item
                yield format_sse(
                    "vote", {"completed": completed, "total": total, "choice": choice}
                )
            vote_split, confidence, top_id = await vote_task

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
        if cache_allowed:
            draft_q, draft_opts = (
                (clarification_question, final_options)
                if (ambiguous and needs_clarification)
                else (question, options)
            )
            _put_cached(
                cache_key,
                _CachedAnalysis(
                    created_at=time.monotonic(),
                    ambiguous=ambiguous,
                    confidence=confidence,
                    ambiguities=ambiguities,
                    interpretations=interpretations,
                    vote_split=vote_split,
                    semantic_entropy=semantic_entropy,
                    semantic_map=semantic_map,
                    draft_question=draft_q,
                    draft_options=draft_opts,
                    top_id=top_id,
                ),
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
        already_streamed = "".join(streamed_text_parts)
        reply_text = _extract_reply_text(response)
        if not already_streamed:
            for idx, word in enumerate(reply_text.split(" ")):
                yield format_sse("token", {"text": ("" if idx == 0 else " ") + word})
        elif len(reply_text) > len(already_streamed) and reply_text.startswith(already_streamed):
            yield format_sse("token", {"text": reply_text[len(already_streamed) :]})

        if enable_logging:
            log_interaction(request, response, log_path=log_path)
        yield format_sse("done", response.model_dump())
    except Exception as exc:
        yield format_sse("error", {"detail": str(exc)})
