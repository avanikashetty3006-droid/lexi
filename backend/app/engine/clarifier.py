from __future__ import annotations

import json
from pydantic import BaseModel, Field

from app.config import settings
from app.engine.llm import LLMClient, default_llm_client, load_prompt
from app.schemas import AmbiguitySpan, Interpretation


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
    llm_client: LLMClient | None = None,
) -> tuple[str, list[str]]:
    """Return a concise clarifying question and 2-4 short clickable option buttons."""
    if not _needs_option_refinement(draft_question, draft_options):
        return draft_question.strip(), [opt.strip() for opt in draft_options[:4]]

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
        return refined.clarification_question.strip(), [
            opt.strip() for opt in refined.options[:4] if opt.strip()
        ]
    except Exception:
        fallback_q = (draft_question or "Could you clarify which meaning you intended?").strip()
        fallback_opts = [
            opt.strip() for opt in draft_options[:4] if opt.strip()
        ] or [interp.meaning[:65] for interp in interpretations[:4]]
        return fallback_q, fallback_opts
