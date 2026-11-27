from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass

from pydantic import BaseModel, Field

from app.engine.llm import LLMClient, default_llm_client, load_prompt
from app.schemas import AmbiguitySpan, HistoryMessage

# Third-person and demonstrative pronouns that commonly trigger anaphoric ambiguity.
# Note: "that" is matched only when NOT acting as a complementizer after reporting verbs.
_PRONOUN_RE = re.compile(
    r"\b(?:the former|the latter|he|him|his|she|her|hers|they|them|their|theirs|it|its)\b"
    r"|\b(?:this|these|those)\b(?=\s+(?:is|was|are|were|will|would|could|should|can|may|might|has|had|means|makes|upset|caused|failed|worked|broke)\b|[.,;:?!]|$)",
    re.IGNORECASE,
)
_COMPLEMENTIZER_THAT_RE = re.compile(
    r"\b(?:told|said|say|says|think|thinks|thought|know|knows|knew|believe|believes|found|saw|heard|noted)\b[^.?!]*?\bthat\b",
    re.IGNORECASE,
)
_STANDALONE_THAT_RE = re.compile(
    r"\bthat\b(?=\s+(?:is|was|will|would|could|should|can|may|might|has|had|means|causes|failed|worked|broke)\b)",
    re.IGNORECASE,
)

_PROPER_NOUN_RE = re.compile(r"\b([A-Z][a-z]{1,25})\b")
_NP_STOP_SECOND_WORDS = (
    "at|in|on|by|to|for|with|from|of|into|onto|over|under|before|after|"
    "because|since|when|while|and|or|but|that|which|who|whom|whose|"
    "is|was|are|were|be|been|has|had|have|did|do|does|can|will|would|could|should|may|might"
)
_NP_CHUNK_RE = re.compile(
    rf"\b(?:the|a|an|this|that|my|our|their|his|her)\s+([a-z]{{2,20}})(?:\s+(?!(?:{_NP_STOP_SECOND_WORDS})\b)([a-z]{{2,20}}))?",
    re.IGNORECASE,
)
_SUBORDINATE_LEAD_RE = re.compile(
    r"^\s*(?:when|while|if|after|before|because|since|although|though)\b",
    re.IGNORECASE,
)

_NON_ENTITY_CAPITALS = {
    "The", "A", "An", "This", "That", "These", "Those", "When", "While", "Where",
    "If", "Unless", "Because", "Since", "After", "Before", "Although", "However",
    "Please", "Make", "Schedule", "Turn", "Water", "Every", "Two", "Three", "He",
    "She", "They", "It", "We", "You", "I", "In", "On", "At", "By", "For",
}


class PronounResolution(BaseModel):
    pronoun: str
    antecedent: str
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class AnaphoraResolverOutput(BaseModel):
    resolutions: list[PronounResolution] = Field(default_factory=list)


@dataclass(frozen=True)
class PronounMention:
    text: str
    start: int
    end: int


def extract_pronouns(sentence: str) -> list[PronounMention]:
    """Extract candidate anaphoric pronouns and their exact character spans."""
    mentions: list[PronounMention] = []
    seen_spans: set[tuple[int, int]] = set()

    for match in _PRONOUN_RE.finditer(sentence):
        span = (match.start(), match.end())
        if span not in seen_spans:
            seen_spans.add(span)
            mentions.append(PronounMention(text=match.group(0), start=span[0], end=span[1]))

    if not _COMPLEMENTIZER_THAT_RE.search(sentence):
        for match in _STANDALONE_THAT_RE.finditer(sentence):
            span = (match.start(), match.end())
            if span not in seen_spans:
                seen_spans.add(span)
                mentions.append(PronounMention(text=match.group(0), start=span[0], end=span[1]))

    mentions.sort(key=lambda m: m.start)
    return mentions


def _extract_entities_with_positions(text: str) -> list[tuple[str, int]]:
    """Extract proper nouns and determiner+noun phrases with character start positions."""
    items: list[tuple[str, int]] = []
    for match in _PROPER_NOUN_RE.finditer(text):
        word = match.group(1)
        if word not in _NON_ENTITY_CAPITALS:
            items.append((word, match.start()))
    for match in _NP_CHUNK_RE.finditer(text):
        phrase = match.group(0).strip(" ,.;:!?\"'")
        if phrase.lower() not in {"the former", "the latter"}:
            items.append((phrase, match.start()))
    items.sort(key=lambda pair: pair[1])
    return items


def extract_candidate_antecedents(
    sentence: str,
    history: list[HistoryMessage],
    max_sentence_pos: int | None = None,
) -> list[str]:
    """
    Extract unique candidate noun-phrase antecedents from history and the current sentence.
    When max_sentence_pos is provided (and history is empty without cataphoric subordinate lead),
    only antecedents appearing prior to max_sentence_pos are included.
    """
    candidates: list[str] = []
    seen_lower: set[str] = set()

    def _add(item: str) -> None:
        cleaned = item.strip(" ,.;:!?\"'")
        low = cleaned.lower()
        if cleaned and low not in seen_lower:
            seen_lower.add(low)
            candidates.append(cleaned)

    for msg in history:
        for ent, _ in _extract_entities_with_positions(msg.content):
            _add(ent)

    allow_cataphora = bool(history) or bool(_SUBORDINATE_LEAD_RE.search(sentence))
    for ent, pos in _extract_entities_with_positions(sentence):
        if max_sentence_pos is not None and not allow_cataphora and pos >= max_sentence_pos:
            continue
        _add(ent)

    return candidates


def has_anaphora_candidates(sentence: str, history: list[HistoryMessage]) -> bool:
    """True when at least one pronoun has >=2 plausible prior/context candidate antecedents."""
    pronouns = extract_pronouns(sentence)
    if not pronouns:
        return False
    furthest_pos = max(p.start for p in pronouns)
    candidates = extract_candidate_antecedents(sentence, history, max_sentence_pos=furthest_pos)
    return len(candidates) >= 2


def _index_resolutions(items: list[PronounResolution]) -> dict[str, str]:
    return {item.pronoun.strip().lower(): item.antecedent.strip() for item in items}


async def detect_anaphora(
    *,
    sentence: str,
    history: list[HistoryMessage],
    llm_client: LLMClient | None = None,
) -> tuple[bool, list[AmbiguitySpan], list[str]]:
    """
    Run two independent anaphora resolvers on extracted pronouns and candidates.
    Disagreement (or 'unclear') between the two resolvers indicates anaphoric ambiguity.
    Returns (is_ambiguous, ambiguity_spans, candidate_interpretations).
    """
    pronouns = extract_pronouns(sentence)
    if not pronouns:
        return False, [], []

    furthest_pos = max(p.start for p in pronouns)
    candidates = extract_candidate_antecedents(sentence, history, max_sentence_pos=furthest_pos)
    if len(candidates) < 2:
        return False, [], []

    client = llm_client or default_llm_client
    prompt_a = load_prompt("anaphora_resolver_a")
    prompt_b = load_prompt("anaphora_resolver_b")

    payload = json.dumps(
        {
            "sentence": sentence,
            "history": [{"role": m.role, "content": m.content} for m in history],
            "pronouns": [p.text for p in pronouns],
            "candidates": candidates,
        },
        ensure_ascii=False,
    )

    res_a, res_b = await asyncio.gather(
        client.call_json(
            system_prompt=prompt_a,
            user_prompt=payload,
            temperature=0.0,
            schema_model=AnaphoraResolverOutput,
            max_tokens=512,
        ),
        client.call_json(
            system_prompt=prompt_b,
            user_prompt=payload,
            temperature=0.2,
            schema_model=AnaphoraResolverOutput,
            max_tokens=512,
        ),
        return_exceptions=True,
    )

    if not isinstance(res_a, AnaphoraResolverOutput) or not isinstance(res_b, AnaphoraResolverOutput):
        return False, [], []

    map_a = _index_resolutions(res_a.resolutions)
    map_b = _index_resolutions(res_b.resolutions)

    spans: list[AmbiguitySpan] = []
    meanings: list[str] = []

    for mention in pronouns:
        key = mention.text.lower()
        ant_a = map_a.get(key, "unclear")
        ant_b = map_b.get(key, "unclear")

        disagree = ant_a.lower() != ant_b.lower()
        either_unclear = ant_a.lower() == "unclear" or ant_b.lower() == "unclear"

        if disagree or either_unclear:
            competing = [c for c in [ant_a, ant_b] if c.lower() != "unclear"]
            unique_competing: list[str] = []
            for item in competing + candidates:
                if item.lower() not in {u.lower() for u in unique_competing}:
                    unique_competing.append(item)
                if len(unique_competing) >= 2:
                    break

            spans.append(
                AmbiguitySpan(
                    type="anaphoric",
                    span=mention.text,
                    start=mention.start,
                    end=mention.end,
                    explanation=(
                        f"Pronoun '{mention.text}' has competing antecedents "
                        f"({', '.join(unique_competing[:2])})."
                    ),
                )
            )
            if not meanings:
                for ant in unique_competing[:2]:
                    meanings.append(
                        f"'{mention.text}' refers to '{ant}' in: {sentence}"
                    )

    return bool(spans), spans, meanings
