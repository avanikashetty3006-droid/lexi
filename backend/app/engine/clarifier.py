from __future__ import annotations

import json
import re
from pydantic import BaseModel, Field

from app.config import settings
from app.engine.llm import LLMClient, default_llm_client, load_prompt
from app.schemas import AmbiguitySpan, HistoryMessage, Interpretation

_WORD_RE = re.compile(r"[a-z0-9']+")
_RESOLVED_PREFIX_RE = re.compile(
    r"^(?:Got it:\s*)?(.*?)(?:\s*\((?:resolved by .*?|based on earlier in this chat)\))?\.?$",
    re.IGNORECASE,
)
_STOPWORDS = {
    "the", "and", "for", "with", "that", "this", "from", "into", "your",
    "you", "did", "mean", "are", "was", "were", "has", "had", "have",
    "saw", "see", "got", "resolved", "answer", "context", "earlier",
    "talking", "about", "something", "same", "her", "his", "she", "him", "they",
    "them", "their", "its", "not", "can", "will", "would", "could",
}


def _distinctive_words(text: str) -> set[str]:
    return {
        w
        for w in _WORD_RE.findall(text.lower())
        if len(w) >= 3 and w not in _STOPWORDS
    }


def enrich_clarification_with_history(
    *,
    question: str,
    options: list[str],
    interpretations: list[Interpretation],
    history: list[HistoryMessage] | None,
) -> tuple[str, list[str]]:
    """Remind the user when one candidate sense matches an earlier resolved turn in chat."""
    if not history or len(interpretations) < 2:
        return question, options

    for msg in reversed(history):
        if msg.role != "assistant":
            continue
        lowered = msg.content.lower()
        if (
            "resolved by" not in lowered
            and "based on earlier in this chat" not in lowered
        ):
            continue
        match = _RESOLVED_PREFIX_RE.match(msg.content.strip())
        prior_meaning = (match.group(1) if match else msg.content).strip()
        prior_words = _distinctive_words(prior_meaning)
        if not prior_words:
            continue

        scores = [
            len(prior_words & _distinctive_words(interp.meaning))
            for interp in interpretations
        ]
        best_score = max(scores)
        if best_score >= 1 and scores.count(best_score) == 1:
            best_idx = scores.index(best_score)
            if "earlier" not in question.lower():
                question = (
                    f'Earlier in this chat you meant "{prior_meaning}" — '
                    f"did you still mean that, or something else? {question}"
                )
            updated_options = list(options)
            if (
                best_idx < len(updated_options)
                and "earlier" not in updated_options[best_idx].lower()
                and len(updated_options[best_idx]) <= 40
            ):
                updated_options[best_idx] = f"{updated_options[best_idx]} (same as earlier)"
            return question, updated_options

    return question, options


class ClarifierOutput(BaseModel):
    clarification_question: str
    options: list[str] = Field(min_length=2)


def _needs_option_refinement(question: str | None, options: list[str]) -> bool:
    if not question or len(options) < 2:
        return True
    return any(len(opt) > 90 for opt in options)


async def prepare_clarification(
    *,
    sentence: str,
    ambiguities: list[AmbiguitySpan],
    interpretations: list[Interpretation],
    draft_question: str | None,
    draft_options: list[str],
    history: list[HistoryMessage] | None = None,
    llm_client: LLMClient | None = None,
) -> tuple[str, list[str]]:
    """Return a concise clarifying question and 2-4 short clickable option buttons."""
    if not _needs_option_refinement(draft_question, draft_options):
        return enrich_clarification_with_history(
            question=draft_question.strip(),
            options=[opt.strip() for opt in draft_options[:4]],
            interpretations=interpretations,
            history=history,
        )

    client = llm_client or default_llm_client
    try:
        system_prompt = load_prompt("clarify")
        payload = json.dumps(
            {
                "sentence": sentence,
                "ambiguities": [a.model_dump() for a in ambiguities],
                "interpretations": [i.model_dump() for i in interpretations],
            },
            ensure_ascii=False,
        )
        refined = await client.call_json(
            system_prompt=system_prompt,
            user_prompt=payload,
            temperature=settings.temperature_detect,
            schema_model=ClarifierOutput,
            max_tokens=256,
            seed=settings.seed,
        )
        return enrich_clarification_with_history(
            question=refined.clarification_question.strip(),
            options=[opt.strip() for opt in refined.options[:4] if opt.strip()],
            interpretations=interpretations,
            history=history,
        )
    except Exception:
        fallback_q = (draft_question or "Could you clarify which meaning you intended?").strip()
        fallback_opts = [
            opt.strip() for opt in draft_options[:4] if opt.strip()
        ] or [interp.meaning[:65] for interp in interpretations[:4]]
        return enrich_clarification_with_history(
            question=fallback_q,
            options=fallback_opts,
            interpretations=interpretations,
            history=history,
        )
