from __future__ import annotations

import asyncio
import json
import re
from functools import lru_cache
from typing import Any, TypeVar

from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AsyncOpenAI,
    DefaultAsyncHttpxClient,
    RateLimitError,
)
from pydantic import BaseModel, ValidationError

from app.config import Settings, settings

T = TypeVar("T", bound=BaseModel)

_CODE_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE | re.MULTILINE)


def _build_ipv4_http_client(timeout_seconds: float):
    """Force IPv4 transport to avoid Windows IPv6 DNS/TCP 21-second stalls."""
    try:
        import httpx2

        return DefaultAsyncHttpxClient(
            transport=httpx2.AsyncHTTPTransport(local_address="0.0.0.0"),
            timeout=timeout_seconds,
        )
    except Exception:
        import httpx

        return httpx.AsyncClient(
            transport=httpx.AsyncHTTPTransport(local_address="0.0.0.0"),
            timeout=timeout_seconds,
        )


@lru_cache(maxsize=32)
def load_prompt(name: str) -> str:
    """Load a prompt template from backend/app/prompts/<name>.txt."""
    path = settings.prompts_dir / f"{name}.txt"
    if not path.exists():
        raise FileNotFoundError(f"Prompt file not found: {path}")
    return path.read_text(encoding="utf-8").strip()


def extract_json_object(raw_text: str) -> dict[str, Any]:
    """Parse a JSON object from raw LLM output, stripping markdown fences if needed."""
    cleaned = _CODE_FENCE_RE.sub("", raw_text).strip()
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start == -1 or end <= start:
            raise ValueError(f"LLM response did not contain a JSON object: {raw_text[:200]}")
        parsed = json.loads(cleaned[start : end + 1])

    if not isinstance(parsed, dict):
        raise ValueError(f"Expected JSON object, got {type(parsed).__name__}")
    return parsed


class LLMClient:
    """Async OpenAI-compatible JSON LLM client with retry and backup-provider fallback."""

    def __init__(self, cfg: Settings | None = None) -> None:
        self.cfg = cfg or settings
        self._primary_client: AsyncOpenAI | None = None
        self._backup_client: AsyncOpenAI | None = None

    def _get_client(self, use_backup: bool = False) -> tuple[AsyncOpenAI, str, str]:
        if use_backup:
            if not self.cfg.backup_api_key:
                raise RuntimeError("Backup LLM API key is not configured.")
            if self._backup_client is None:
                self._backup_client = AsyncOpenAI(
                    api_key=self.cfg.backup_api_key,
                    base_url=self.cfg.backup_base_url,
                    http_client=_build_ipv4_http_client(self.cfg.llm_timeout_seconds),
                )
            return self._backup_client, self.cfg.backup_model, self.cfg.backup_provider

        if not self.cfg.api_key:
            raise RuntimeError(
                f"API key missing for provider '{self.cfg.llm_provider}'. "
                "Set GEMINI_API_KEY (or GROQ_API_KEY / OPENAI_API_KEY) in .env."
            )
        if self._primary_client is None:
            self._primary_client = AsyncOpenAI(
                api_key=self.cfg.api_key,
                base_url=self.cfg.base_url,
                http_client=_build_ipv4_http_client(self.cfg.llm_timeout_seconds),
            )
        return self._primary_client, self.cfg.model_name, self.cfg.llm_provider

    async def _request_once(
        self,
        *,
        use_backup: bool,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        max_tokens: int,
        seed: int | None,
    ) -> str:
        client, model, provider = self._get_client(use_backup=use_backup)
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "response_format": {"type": "json_object"},
        }
        if provider == "gemini":
            kwargs["reasoning_effort"] = "minimal"
        if seed is not None and provider == "openai":
            kwargs["seed"] = seed

        response = await client.chat.completions.create(**kwargs)
        content = response.choices[0].message.content
        if not content:
            raise ValueError("Empty response from LLM.")
        return content

    async def call_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.0,
        schema_model: type[T] | None = None,
        max_tokens: int = 1024,
        seed: int | None = None,
        max_retries: int | None = None,
    ) -> dict[str, Any] | T:
        """Call LLM in JSON mode with retry, Pydantic validation, and backup fallback."""
        last_error: Exception | None = None
        use_backup = False
        retries = self.cfg.llm_max_retries if max_retries is None else max_retries
        max_attempts = max(retries + 1, 2)

        for attempt in range(max_attempts):
            try:
                raw = await self._request_once(
                    use_backup=use_backup,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    seed=seed,
                )
                data = extract_json_object(raw)
                if schema_model is not None:
                    return schema_model.model_validate(data)
                return data
            except (RateLimitError, APITimeoutError, APIConnectionError, APIStatusError) as exc:
                last_error = exc
                is_rate_limit = isinstance(exc, RateLimitError) or (
                    isinstance(exc, APIStatusError) and exc.status_code == 429
                )
                if is_rate_limit and not use_backup and self.cfg.backup_api_key:
                    use_backup = True
                    continue
                if attempt < max_attempts - 1:
                    delay = (1.2 * (attempt + 1)) if is_rate_limit else (0.3 * (attempt + 1))
                    await asyncio.sleep(delay)
                    continue
                break
            except (ValueError, json.JSONDecodeError, ValidationError) as exc:
                last_error = exc
                if attempt < retries:
                    await asyncio.sleep(0.2 * (attempt + 1))
                    continue
                break

        raise RuntimeError(f"LLM JSON call failed after retries: {last_error}") from last_error

    async def stream_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.0,
        schema_model: type[T] | None = None,
        max_tokens: int = 1024,
        seed: int | None = None,
    ):
        """
        Stream JSON response tokens via `stream=True` yielding `("chunk", delta)`
        followed by `("result", validated_dict_or_model)`. Falls back to `call_json`
        if streaming fails or retries/backup provider are needed.
        """
        try:
            client, model, provider = self._get_client(use_backup=False)
            kwargs: dict[str, Any] = {
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": temperature,
                "max_tokens": max_tokens,
                "response_format": {"type": "json_object"},
                "stream": True,
            }
            if provider == "gemini":
                kwargs["reasoning_effort"] = "minimal"
            if seed is not None and provider == "openai":
                kwargs["seed"] = seed

            stream = await client.chat.completions.create(**kwargs)
            parts: list[str] = []
            async for chunk in stream:
                delta = chunk.choices[0].delta.content if chunk.choices else None
                if delta:
                    parts.append(delta)
                    yield ("chunk", delta)

            data = extract_json_object("".join(parts))
            validated = schema_model.model_validate(data) if schema_model is not None else data
            yield ("result", validated)
            return
        except Exception:
            fallback = await self.call_json(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=temperature,
                schema_model=schema_model,
                max_tokens=max_tokens,
                seed=seed,
            )
            yield ("result", fallback)


class IncrementalMeaningExtractor:
    """
    Incremental parser for streamed detector JSON. Buffers the first `"meaning"`
    string and streams decoded text deltas as soon as `"ambiguous": false` is seen.
    """

    _AMBIG_RE = re.compile(r'"ambiguous"\s*:\s*(true|false)', re.IGNORECASE)
    _MEANING_OPEN_RE = re.compile(r'"meaning"\s*:\s*"')

    def __init__(self) -> None:
        self._raw = ""
        self._ambig_known: bool | None = None  # True/False once parsed
        self._in_meaning = False
        self._meaning_done = False
        self._escape = False
        self._scan_pos = 0
        self._pending_chars: list[str] = []

    def feed(self, chunk: str) -> str:
        """Consume a raw JSON chunk and return newly unlocked plain-text reply characters."""
        if not chunk or self._ambig_known is True or self._meaning_done:
            self._raw += chunk
            return ""

        self._raw += chunk
        if self._ambig_known is None:
            m = self._AMBIG_RE.search(self._raw)
            if m:
                self._ambig_known = m.group(1).lower() == "true"
                if self._ambig_known:
                    self._pending_chars.clear()
                    return ""

        if not self._in_meaning:
            m_open = self._MEANING_OPEN_RE.search(self._raw, self._scan_pos)
            if not m_open:
                self._scan_pos = max(0, len(self._raw) - 20)
                return ""
            self._in_meaning = True
            self._scan_pos = m_open.end()

        newly_decoded: list[str] = []
        idx = self._scan_pos
        while idx < len(self._raw):
            ch = self._raw[idx]
            idx += 1
            if self._escape:
                self._escape = False
                if ch == "n":
                    newly_decoded.append("\n")
                elif ch == "t":
                    newly_decoded.append("\t")
                elif ch == "r":
                    continue
                else:
                    newly_decoded.append(ch)
            elif ch == "\\":
                self._escape = True
            elif ch == '"':
                self._meaning_done = True
                break
            else:
                newly_decoded.append(ch)
        self._scan_pos = idx

        if newly_decoded:
            self._pending_chars.extend(newly_decoded)

        if self._ambig_known is False and self._pending_chars:
            out = "".join(self._pending_chars)
            self._pending_chars.clear()
            return out
        return ""


default_llm_client = LLMClient()
