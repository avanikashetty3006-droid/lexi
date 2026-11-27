"""POST /feedback: stores user override, thumbs and slider events (contract v1.1).

Events are appended to backend/logs/feedback.jsonl so the user study and the
dashboard can use them. Nothing here calls an LLM.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.config import settings

LOG_PATH = settings.logs_dir / "feedback.jsonl"

router = APIRouter()


class FeedbackEvent(BaseModel):
    event: Literal["override", "feedback", "slider"]
    session_id: str | None = None
    sentence: str | None = None
    message_id: str | None = None
    vote: Literal["up", "down"] | None = None
    original_id: str | None = None
    chosen_id: str | None = None
    chosen_meaning: str | None = Field(default=None, max_length=1000)
    threshold: float | None = Field(default=None, ge=0.0, le=1.0)


@router.post("/feedback")
async def feedback(event: FeedbackEvent) -> dict[str, str]:
    """Append one user-interaction event to the feedback log."""
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "provider": settings.llm_provider,
        "model": settings.model_name,
        **event.model_dump(),
    }
    with LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    return {"status": "ok"}
