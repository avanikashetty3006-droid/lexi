from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent  # backend/
REPO_ROOT = BASE_DIR.parent  # lexi/

# Load .env from repo root first, then backend/.env if present
load_dotenv(REPO_ROOT / ".env")
load_dotenv(BASE_DIR / ".env")

PROVIDER_BASE_URLS: dict[str, str | None] = {
    "gemini": "https://generativelanguage.googleapis.com/v1beta/openai/",
    "groq": "https://api.groq.com/openai/v1",
    "openai": None,
}

PROVIDER_DEFAULT_MODELS: dict[str, str] = {
    "gemini": "gemini-3.1-flash-lite",
    "groq": "openai/gpt-oss-20b",
    "openai": "gpt-4o-mini",
}


def resolve_provider_credentials(provider: str) -> tuple[str, str | None, str]:
    """Return (api_key, base_url, default_model) for a configured LLM provider."""
    norm = provider.strip().lower()
    base_url = os.getenv("LLM_BASE_URL") or PROVIDER_BASE_URLS.get(norm)
    default_model = PROVIDER_DEFAULT_MODELS.get(norm, "gemini-3.1-flash-lite")

    if norm == "gemini":
        api_key = (
            os.getenv("GEMINI_API_KEY")
            or os.getenv("GOOGLE_API_KEY")
            or os.getenv("OPENAI_API_KEY")
            or ""
        )
    elif norm == "groq":
        api_key = os.getenv("GROQ_API_KEY") or os.getenv("OPENAI_API_KEY") or ""
    else:
        api_key = os.getenv("OPENAI_API_KEY") or ""

    return api_key.strip(), base_url, default_model


@dataclass(frozen=True)
class Settings:
    llm_provider: str
    model_name: str
    api_key: str
    base_url: str | None
    backup_provider: str
    backup_model: str
    backup_api_key: str
    backup_base_url: str | None
    embed_model: str
    threshold: float
    n_samples: int
    temperature_detect: float
    temperature_vote: float
    seed: int
    llm_timeout_seconds: float
    llm_max_retries: int
    prompts_dir: Path
    logs_dir: Path
    interactions_log_path: Path


def get_settings() -> Settings:
    """Build runtime settings from environment variables."""
    provider = os.getenv("LLM_PROVIDER", "gemini").strip().lower()
    api_key, base_url, default_model = resolve_provider_credentials(provider)
    model_name = (os.getenv("MODEL_NAME") or os.getenv("MODEL") or default_model).strip()

    backup_provider = os.getenv("BACKUP_PROVIDER", "groq").strip().lower()
    backup_key, backup_base_url, backup_default_model = resolve_provider_credentials(
        backup_provider
    )
    backup_model = (os.getenv("BACKUP_MODEL") or backup_default_model).strip()

    # Only use backup credentials if a dedicated key exists for the backup provider
    if backup_provider == "groq" and not os.getenv("GROQ_API_KEY"):
        backup_key = ""
    elif backup_provider == "gemini" and not (
        os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    ):
        backup_key = ""

    return Settings(
        llm_provider=provider,
        model_name=model_name,
        api_key=api_key,
        base_url=base_url,
        backup_provider=backup_provider,
        backup_model=backup_model,
        backup_api_key=backup_key,
        backup_base_url=backup_base_url,
        embed_model=os.getenv("EMBED_MODEL", "all-MiniLM-L6-v2").strip(),
        threshold=float(os.getenv("THRESHOLD", "0.7")),
        n_samples=int(os.getenv("N_SAMPLES", "5")),
        temperature_detect=float(os.getenv("TEMPERATURE_DETECT", "0.0")),
        temperature_vote=float(os.getenv("TEMPERATURE_VOTE", "0.8")),
        seed=int(os.getenv("SEED", "42")),
        llm_timeout_seconds=float(os.getenv("LLM_TIMEOUT_SECONDS", "15.0")),
        llm_max_retries=int(os.getenv("LLM_MAX_RETRIES", "2")),
        prompts_dir=BASE_DIR / "app" / "prompts",
        logs_dir=BASE_DIR / "logs",
        interactions_log_path=BASE_DIR / "logs" / "interactions.jsonl",
    )


settings = get_settings()
