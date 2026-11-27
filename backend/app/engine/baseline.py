from __future__ import annotations

import json

from app.config import settings
from app.engine.llm import LLMClient, default_llm_client, load_prompt
from app.schemas import BaselineResponse


async def run_baseline(
    sentence: str,
    llm_client: LLMClient | None = None,
) -> BaselineResponse:
    """Run the silent-guess baseline model that commits to one meaning without asking."""
    client = llm_client or default_llm_client
    system_prompt = load_prompt("baseline")
    user_prompt = json.dumps({"sentence": sentence}, ensure_ascii=False)
    return await client.call_json(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        temperature=settings.temperature_detect,
        schema_model=BaselineResponse,
        max_tokens=256,
        seed=settings.seed,
    )
