from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.engine.baseline import run_baseline
from app.engine.pipeline import analyze_sentence
from app.schemas import AnalyzeRequest, AnalyzeResponse, BaselineRequest, BaselineResponse

app = FastAPI(title="Lexi Ambiguity Engine", version="0.1.0")

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


@app.post("/baseline", response_model=BaselineResponse)
async def baseline(request: BaselineRequest) -> BaselineResponse:
    """Run silent-guess baseline without clarification."""
    try:
        return await run_baseline(request.sentence)
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
