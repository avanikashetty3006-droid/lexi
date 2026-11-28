from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from app.config import settings
from app.engine.baseline import run_baseline
from app.engine.embeddings import embed_texts
from app.engine.llm import default_llm_client
from app.engine.pipeline import analyze_sentence, stream_analyze_sentence
from app.feedback import router as feedback_router
from app.schemas import AnalyzeRequest, AnalyzeResponse, BaselineRequest, BaselineResponse


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Pre-warm local SentenceTransformer embeddings and HTTP client pool on startup."""
    if os.getenv("LEXI_SKIP_WARMUP") != "1":
        embed_texts(["Lexi embedding warmup"])
        for use_backup in (False, True):
            try:
                default_llm_client._get_client(use_backup=use_backup)
            except RuntimeError:
                pass
    yield


app = FastAPI(title="Lexi Ambiguity Engine", version="0.1.0", lifespan=lifespan)

app.include_router(feedback_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict[str, str]:
    """Health check reporting configured provider and model."""
    return {
        "status": "ok",
        "provider": settings.llm_provider,
        "model": settings.model_name,
    }


@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze(request: AnalyzeRequest) -> AnalyzeResponse:
    """Analyze a sentence for ambiguity, vote confidence, and clarification need."""
    try:
        return await analyze_sentence(request)
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post("/analyze/stream")
async def analyze_stream(request: AnalyzeRequest) -> StreamingResponse:
    """Stream stage updates, live 5-sample votes, response tokens, and final JSON via SSE."""
    return StreamingResponse(
        stream_analyze_sentence(request),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/baseline", response_model=BaselineResponse)
async def baseline(request: BaselineRequest) -> BaselineResponse:
    """Run silent-guess baseline without clarification."""
    try:
        return await run_baseline(request.sentence)
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
