from __future__ import annotations

import asyncio
import json
from collections import Counter
from pydantic import BaseModel

from app.config import settings
from app.engine.detector import RawInterpretationItem
from app.engine.llm import LLMClient, default_llm_client, load_prompt
from app.schemas import DomainType, HistoryMessage


class VoteResult(BaseModel):
    choice: str
    reason: str = ""


def compute_vote_confidence(
    choices: list[str],
    valid_ids: list[str],
) -> tuple[dict[str, float], float, str | None]:
    """Compute normalized vote_split, confidence score, and winning interpretation ID."""
    total = len(choices)
    if total == 0:
        split = {iid: round(1.0 / len(valid_ids), 4) for iid in valid_ids}
        return split, 0.0, None

    valid_set = set(valid_ids)
    normalized = [c if c in valid_set else "unclear" for c in choices]
    counts = Counter(normalized)

    vote_split: dict[str, float] = {
        iid: round(counts.get(iid, 0) / total, 4) for iid in valid_ids
    }
    if counts.get("unclear", 0) > 0:
        vote_split["unclear"] = round(counts["unclear"] / total, 4)

    interp_counts = [(iid, counts.get(iid, 0)) for iid in valid_ids]
    best_id, best_count = max(interp_counts, key=lambda pair: pair[1])
    confidence = round(best_count / total, 4)
    winner = best_id if best_count > 0 else None
    return vote_split, confidence, winner


async def run_vote_confidence(
    *,
    sentence: str,
    history: list[HistoryMessage],
    domain: DomainType,
    interpretations: list[RawInterpretationItem],
    n_samples: int | None = None,
    llm_client: LLMClient | None = None,
    on_vote=None,
) -> tuple[dict[str, float], float, str | None]:
    """Run N parallel high-temperature LLM votes to estimate speaker-intent confidence."""
    client = llm_client or default_llm_client
    system_prompt = load_prompt("vote")
    samples = n_samples or settings.n_samples
    valid_ids = [item.id for item in interpretations]

    user_prompt = json.dumps(
        {
            "sentence": sentence,
            "domain": domain,
            "history": [{"role": m.role, "content": m.content} for m in history],
            "interpretations": [
                {"id": item.id, "meaning": item.meaning} for item in interpretations
            ],
        },
        ensure_ascii=False,
    )

    async def _single_vote(idx: int):
        kwargs = {
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
            "temperature": settings.temperature_vote,
            "schema_model": VoteResult,
            "max_tokens": 80,
            "seed": settings.seed + idx,
        }
        if isinstance(client, LLMClient):
            kwargs["max_retries"] = 1
        return await client.call_json(**kwargs)

    tasks = [asyncio.create_task(_single_vote(i)) for i in range(samples)]
    choices: list[str] = []
    for completed_idx, fut in enumerate(asyncio.as_completed(tasks), start=1):
        try:
            res = await fut
            choice = res.choice.strip() if isinstance(res, VoteResult) else "unclear"
        except Exception:
            choice = "unclear"
        choices.append(choice)
        if on_vote is not None:
            await on_vote(completed_idx, samples, choice)

    return compute_vote_confidence(choices, valid_ids)
