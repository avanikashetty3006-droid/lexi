from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import numpy as np
from fastapi.testclient import TestClient

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.engine.anaphora import (
    AnaphoraResolverOutput,
    PronounResolution,
    detect_anaphora,
    extract_candidate_antecedents,
    extract_pronouns,
)
from app.engine.context import ContextResolutionResult
from app.engine.detector import RawDetectionResult, RawInterpretationItem
from app.engine.embeddings import (
    analyze_semantic_space,
    cluster_by_cosine,
    compute_semantic_entropy,
    entropy_to_confidence,
    project_to_2d_pca,
)
from app.engine.pipeline import analyze_sentence
from app.main import app
from app.schemas import AnalyzeRequest, ClarificationInput, HistoryMessage, Interpretation


def _orthogonal_embed(texts: list[str]) -> np.ndarray:
    """Deterministic orthogonal unit embeddings for testing distinct interpretations."""
    dim = max(4, len(texts))
    mat = np.zeros((len(texts), dim), dtype=np.float32)
    for i, text in enumerate(texts):
        if "identical" in text.lower():
            mat[i, 0] = 1.0
        else:
            mat[i, i % dim] = 1.0
    return mat


def test_anaphora_extractors():
    sentence = "Alice told Maya that she failed the exam."
    pronouns = extract_pronouns(sentence)
    assert [p.text for p in pronouns] == ["she"]
    candidates = extract_candidate_antecedents(sentence, [])
    assert "Alice" in candidates
    assert "Maya" in candidates
    assert extract_pronouns("I watered the plant on the balcony this morning.") == []
    assert [p.text for p in extract_pronouns("This upset the client.")] == ["This"]


def test_anaphora_disagreement_vs_agreement():
    class DisagreementClient:
        async def call_json(self, *, system_prompt: str, **kwargs):
            if "Resolver A" in system_prompt:
                return AnaphoraResolverOutput(
                    resolutions=[PronounResolution(pronoun="she", antecedent="Alice", confidence=0.8)]
                )
            return AnaphoraResolverOutput(
                resolutions=[PronounResolution(pronoun="she", antecedent="Maya", confidence=0.8)]
            )

    ambig, spans, meanings = asyncio.run(
        detect_anaphora(
            sentence="Alice told Maya that she failed the exam.",
            history=[],
            llm_client=DisagreementClient(),
        )
    )
    assert ambig is True
    assert len(spans) == 1
    assert spans[0].type == "anaphoric"
    assert spans[0].span == "she"
    assert len(meanings) == 2

    class AgreementClient:
        async def call_json(self, **kwargs):
            return AnaphoraResolverOutput(
                resolutions=[PronounResolution(pronoun="it", antecedent="the trophy", confidence=0.95)]
            )

    ambig_ok, spans_ok, _ = asyncio.run(
        detect_anaphora(
            sentence="Bob polished the trophy before placing it on the shelf.",
            history=[],
            llm_client=AgreementClient(),
        )
    )
    assert ambig_ok is False
    assert spans_ok == []


def test_embeddings_clustering_entropy_and_pca():
    # Identical meanings -> 1 cluster -> 0 entropy
    same_vecs = np.array([[1.0, 0.0, 0.0], [0.99, 0.05, 0.0]], dtype=np.float32)
    clusters_same = cluster_by_cosine(same_vecs, cosine_threshold=0.80)
    assert len(clusters_same) == 1
    assert compute_semantic_entropy(clusters_same, [0.5, 0.5]) == 0.0

    # Orthogonal equal-weight meanings -> 2 clusters -> 1.0 bit entropy
    diff_vecs = np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]], dtype=np.float32)
    clusters_diff = cluster_by_cosine(diff_vecs, cosine_threshold=0.80)
    assert len(clusters_diff) == 2
    entropy = compute_semantic_entropy(clusters_diff, [0.5, 0.5])
    assert entropy == 1.0
    assert entropy_to_confidence(entropy, 2) == 0.0

    # PCA edge cases: 1, 2, 3 points
    assert project_to_2d_pca(np.array([[1.0, 2.0, 3.0]])) == [(0.0, 0.0)]
    assert len(project_to_2d_pca(diff_vecs)) == 2
    coords3 = project_to_2d_pca(np.eye(3, dtype=np.float32))
    assert len(coords3) == 3

    interps = [
        Interpretation(id="i1", meaning="Meaning A", probability=0.6),
        Interpretation(id="i2", meaning="Meaning B", probability=0.4),
    ]
    ent, smap = analyze_semantic_space(interps, embed_fn=_orthogonal_embed)
    assert ent > 0.9
    assert len(smap) == 2
    assert smap[0].id == "i1"


def test_clarification_resolution_and_jsonl_logging(tmp_path):
    class ClarifyClient:
        async def call_json(self, *, schema_model=None, **kwargs):
            if schema_model is ContextResolutionResult:
                return ContextResolutionResult(
                    resolved=True,
                    resolved_meaning="Use the financial institution meaning of bank.",
                    matched_option_index=0,
                )
            raise AssertionError("Unexpected LLM call after clarification resolved.")

    log_file = tmp_path / "interactions.jsonl"
    req = AnalyzeRequest(
        sentence="Meet me at the bank.",
        history=[HistoryMessage(role="user", content="Meet me at the bank.")],
        clarification=ClarificationInput(
            question="Which bank do you mean?",
            answer="The financial bank downtown.",
        ),
    )
    res = asyncio.run(
        analyze_sentence(
            req,
            llm_client=ClarifyClient(),
            embed_fn=_orthogonal_embed,
            log_path=log_file,
            enable_logging=True,
        )
    )
    assert res.ambiguous is False
    assert res.needs_clarification is False
    assert res.resolution_basis == "clarification"
    assert res.resolved_interpretation_id == "i1"
    assert log_file.exists()

    lines = log_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["latency_ms"] == res.latency_ms
    assert entry["request"]["sentence"] == "Meet me at the bank."
    assert entry["response"]["resolution_basis"] == "clarification"


def test_history_context_sets_resolution_basis_and_threshold_controls_clarify(monkeypatch, tmp_path):
    class ContextClient:
        async def call_json(self, *, schema_model=None, **kwargs):
            return RawDetectionResult(
                ambiguous=False,
                ambiguities=[],
                interpretations=[RawInterpretationItem(id="i1", meaning="Deposit check at financial bank.")],
                clarification_question=None,
                options=[],
            )

    req = AnalyzeRequest(
        sentence="Go to the bank.",
        history=[HistoryMessage(role="user", content="I need to cash this paycheck.")],
        threshold=0.85,
    )
    res = asyncio.run(
        analyze_sentence(
            req,
            llm_client=ContextClient(),
            embed_fn=_orthogonal_embed,
            log_path=tmp_path / "ctx.jsonl",
            enable_logging=True,
        )
    )
    assert res.ambiguous is False
    assert res.resolution_basis == "context"
    assert res.threshold_used == 0.85


def test_threshold_reuse_cache_recomputes_clarification_without_extra_llm_calls(monkeypatch):
    from app.engine.llm import LLMClient
    from app.engine.pipeline import clear_analyze_cache

    clear_analyze_cache()
    monkeypatch.setattr("app.engine.embeddings.embed_texts", _orthogonal_embed)

    class CountingLLMClient(LLMClient):
        def __init__(self) -> None:
            super().__init__()
            self.calls = 0

        async def _request_once(self, *, system_prompt: str, user_prompt: str, **kwargs) -> str:
            self.calls += 1
            if "semantic evaluator" in system_prompt:
                # 4 out of 5 say i1, 1 says i2 -> confidence = 0.8
                seed = kwargs.get("seed") or 0
                choice = "i2" if (seed % 5 == 0) else "i1"
                return json.dumps({"choice": choice, "reason": "test"})
            return json.dumps(
                {
                    "ambiguous": True,
                    "ambiguities": [
                        {"type": "lexical", "span": "duck", "explanation": "Verb or noun."}
                    ],
                    "interpretations": [
                        {"id": "i1", "meaning": "Saw her lower her head."},
                        {"id": "i2", "meaning": "Saw her pet bird."},
                    ],
                    "clarification_question": "Did she bend down or own a bird?",
                    "options": ["Lowered head", "Pet bird"],
                }
            )

    client = CountingLLMClient()
    res_low = asyncio.run(
        analyze_sentence(
            AnalyzeRequest(sentence="I saw her duck.", threshold=0.5),
            llm_client=client,
            enable_logging=False,
        )
    )
    assert res_low.threshold_used == 0.5
    assert res_low.confidence == 0.8
    assert res_low.needs_clarification is False
    assert res_low.resolved_interpretation_id == "i1"
    calls_after_first = client.calls

    res_high = asyncio.run(
        analyze_sentence(
            AnalyzeRequest(sentence="I saw her duck.", threshold=0.95),
            llm_client=client,
            enable_logging=False,
        )
    )
    assert client.calls == calls_after_first
    assert res_high.threshold_used == 0.95
    assert res_high.confidence == 0.8
    assert res_high.needs_clarification is True
    assert res_high.resolved_interpretation_id is None
    assert res_high.clarification_question == "Did she bend down or own a bird?"
    clear_analyze_cache()


def test_conversational_greeting_no_clarification_while_monitoring_ambiguity(monkeypatch):
    from app.engine.pipeline import clear_analyze_cache

    clear_analyze_cache()

    class ChatClient:
        async def call_json(self, *, user_prompt: str, schema_model=None, **kwargs):
            payload = json.loads(user_prompt)
            if payload["sentence"].lower().startswith("hi"):
                return RawDetectionResult(
                    ambiguous=False,
                    ambiguities=[],
                    interpretations=[
                        RawInterpretationItem(id="i1", meaning="Hi there! How can I help you today?")
                    ],
                    clarification_question=None,
                    options=[],
                )
            if "choice" in getattr(schema_model, "model_fields", {}):
                return schema_model.model_validate({"choice": "unclear", "reason": "ambiguous"})
            return RawDetectionResult(
                ambiguous=True,
                ambiguities=[
                    {"type": "lexical", "span": "match", "explanation": "Sports match or fire matchstick."}
                ],
                interpretations=[
                    RawInterpretationItem(id="i1", meaning="Tell me about the sports match."),
                    RawInterpretationItem(id="i2", meaning="Tell me about the fire matchstick."),
                ],
                clarification_question="Did you mean a sports match or a matchstick?",
                options=["Sports match", "Matchstick"],
            )

    greet = asyncio.run(
        analyze_sentence(
            AnalyzeRequest(sentence="Hi, how are you?"),
            llm_client=ChatClient(),
            embed_fn=_orthogonal_embed,
            enable_logging=False,
        )
    )
    assert greet.ambiguous is False
    assert greet.needs_clarification is False
    assert greet.clarification_question is None
    assert "help" in greet.interpretations[0].meaning.lower()

    ambig = asyncio.run(
        analyze_sentence(
            AnalyzeRequest(sentence="Tell me about the match."),
            llm_client=ChatClient(),
            embed_fn=_orthogonal_embed,
            enable_logging=False,
        )
    )
    assert ambig.ambiguous is True
    assert ambig.needs_clarification is True
    assert ambig.clarification_question is not None


def test_analyze_stream_sse_events(monkeypatch, tmp_path):
    from fastapi.testclient import TestClient
    from app.main import app

    class StreamClient:
        async def call_json(self, *, schema_model=None, **kwargs):
            if "choice" in getattr(schema_model, "model_fields", {}):
                return schema_model.model_validate({"choice": "unclear", "reason": "ambiguous"})
            if "clarification_question" in getattr(schema_model, "model_fields", {}) and "ambiguous" not in getattr(schema_model, "model_fields", {}):
                return schema_model.model_validate(
                    {"clarification_question": "Baseball bat or animal?", "options": ["Baseball bat", "Animal"]}
                )
            return RawDetectionResult(
                ambiguous=True,
                ambiguities=[{"type": "lexical", "span": "bat", "explanation": "Two meanings."}],
                interpretations=[
                    RawInterpretationItem(id="i1", meaning="Baseball bat."),
                    RawInterpretationItem(id="i2", meaning="Flying mammal."),
                ],
                clarification_question="Baseball bat or animal?",
                options=["Baseball bat", "Animal"],
            )

    fake_settings = type(
        "FakeSettings",
        (),
        {
            "llm_provider": "gemini",
            "model_name": "gemini-3.1-flash-lite",
            "threshold": 0.7,
            "n_samples": 5,
            "temperature_detect": 0.0,
            "temperature_vote": 0.8,
            "seed": 42,
            "interactions_log_path": tmp_path / "stream_interactions.jsonl",
        },
    )()
    monkeypatch.setattr("app.engine.pipeline.default_llm_client", StreamClient())
    monkeypatch.setattr("app.engine.embeddings.embed_texts", _orthogonal_embed)
    monkeypatch.setattr("app.engine.pipeline.settings", fake_settings)

    client = TestClient(app)
    res = client.post("/analyze/stream", json={"sentence": "I saw the bat."})
    assert res.status_code == 200
    assert "text/event-stream" in res.headers["content-type"]

    body = res.text
    assert "event: stage" in body
    assert "event: vote" in body
    assert "event: token" in body
    assert "event: done" in body
    assert "Baseball bat or animal?" in body


def test_greeting_fast_path_zero_llm_calls():
    class FailIfCalledClient:
        async def call_json(self, **kwargs):
            raise AssertionError("LLM should not be called for trivial greetings!")

    for text in ["hey", "Hello!", "thanks", "Good morning!"]:
        res = asyncio.run(
            analyze_sentence(
                AnalyzeRequest(sentence=text),
                llm_client=FailIfCalledClient(),
                enable_logging=False,
            )
        )
        assert res.ambiguous is False
        assert res.confidence == 1.0
        assert res.needs_clarification is False
        assert res.ambiguities == []
        assert res.uncertainty.semantic_entropy == 0.0
        assert res.latency_ms < 50


def test_clarifier_skipped_when_confident():
    long_opt = "A" * 110

    class ConfidentClient:
        async def call_json(self, *, schema_model=None, **kwargs):
            if "choice" in getattr(schema_model, "model_fields", {}):
                return schema_model.model_validate({"choice": "i1", "reason": "clear winner"})
            if "clarification_question" in getattr(schema_model, "model_fields", {}) and "ambiguous" not in getattr(schema_model, "model_fields", {}):
                raise AssertionError("prepare_clarification should not call LLM when confidence >= threshold!")
            return RawDetectionResult(
                ambiguous=True,
                ambiguities=[{"type": "lexical", "span": "bat", "explanation": "Two meanings."}],
                interpretations=[
                    RawInterpretationItem(id="i1", meaning="Baseball bat."),
                    RawInterpretationItem(id="i2", meaning="Flying mammal."),
                ],
                clarification_question="Which one?",
                options=[long_opt, "Short option"],
            )

    res = asyncio.run(
        analyze_sentence(
            AnalyzeRequest(sentence="I saw the bat.", threshold=0.7),
            llm_client=ConfidentClient(),
            embed_fn=_orthogonal_embed,
            enable_logging=False,
        )
    )
    assert res.confidence == 1.0
    assert res.needs_clarification is False
    assert res.resolved_interpretation_id == "i1"


def test_incremental_stream_tokens_clean_response(monkeypatch, tmp_path):
    from fastapi.testclient import TestClient
    from app.engine.llm import IncrementalMeaningExtractor
    from app.main import app

    ext = IncrementalMeaningExtractor()
    chunks = [
        '{"ambiguous": false, ',
        '"ambiguities": [], ',
        '"interpretations": [{"id": "i1", "meaning": "Hello! ',
        'How can I help?"}], ',
        '"clarification_question": null, "options": []}',
    ]
    out = [ext.feed(c) for c in chunks]
    assert "".join(out) == "Hello! How can I help?"
    assert out[2] == "Hello! "
    assert out[3] == "How can I help?"

    class IncrementalStreamClient:
        async def stream_json(self, *, schema_model=None, **kwargs):
            for c in chunks:
                yield ("chunk", c)
            yield (
                "result",
                RawDetectionResult(
                    ambiguous=False,
                    ambiguities=[],
                    interpretations=[RawInterpretationItem(id="i1", meaning="Hello! How can I help?")],
                    clarification_question=None,
                    options=[],
                ),
            )

    fake_settings = type(
        "FakeSettings",
        (),
        {
            "llm_provider": "gemini",
            "model_name": "gemini-3.1-flash-lite",
            "threshold": 0.7,
            "n_samples": 5,
            "temperature_detect": 0.0,
            "temperature_vote": 0.8,
            "seed": 42,
            "interactions_log_path": tmp_path / "inc_stream.jsonl",
        },
    )()
    monkeypatch.setattr("app.engine.pipeline.default_llm_client", IncrementalStreamClient())
    monkeypatch.setattr("app.engine.pipeline.settings", fake_settings)

    client = TestClient(app)
    res = client.post("/analyze/stream", json={"sentence": "Explain binary search briefly."})
    assert res.status_code == 200
    assert res.text.count("event: token") == 2
    assert '"Hello! "' in res.text
    assert '"How can I help?"' in res.text
    assert res.text.count("How can I help?") == 4  # 1 token + 1 detected + 2 in done (interp + map)


def test_build_completion_kwargs_groq_reasoning_vs_llama():
    from app.engine.llm import build_completion_kwargs

    oss_kwargs = build_completion_kwargs(
        model="openai/gpt-oss-20b",
        provider="groq",
        system_prompt="sys",
        user_prompt="usr",
        temperature=0.7,
        max_tokens=80,
        seed=42,
    )
    assert oss_kwargs["reasoning_effort"] == "low"
    assert oss_kwargs["max_tokens"] >= 1024

    llama_kwargs = build_completion_kwargs(
        model="llama-3.3-70b-versatile",
        provider="groq",
        system_prompt="sys",
        user_prompt="usr",
        temperature=0.7,
        max_tokens=80,
        seed=42,
    )
    assert "reasoning_effort" not in llama_kwargs
    assert llama_kwargs["max_tokens"] == 80

    gemini_kwargs = build_completion_kwargs(
        model="gemini-3.1-flash-lite",
        provider="gemini",
        system_prompt="sys",
        user_prompt="usr",
        temperature=0.0,
        max_tokens=600,
        seed=42,
    )
    assert gemini_kwargs["reasoning_effort"] == "minimal"
    assert gemini_kwargs["max_tokens"] == 600


def test_call_json_gemini_rate_limit_fallback_to_groq_reasoning():
    import httpx
    from openai import RateLimitError
    from app.engine.llm import LLMClient

    captured_backup_kwargs: list[dict] = []

    class FailingPrimaryCompletions:
        async def create(self, **kwargs):
            req = httpx.Request("POST", "https://example.com/v1/chat/completions")
            resp = httpx.Response(429, request=req)
            raise RateLimitError("rate limited", response=resp, body=None)

    class SucceedingBackupCompletions:
        async def create(self, **kwargs):
            captured_backup_kwargs.append(kwargs)
            msg = type("Msg", (), {"content": '{"ambiguous": false}'})()
            choice = type("Choice", (), {"message": msg})()
            return type("Resp", (), {"choices": [choice]})()

    fake_cfg = type(
        "FakeCfg",
        (),
        {
            "llm_provider": "gemini",
            "model_name": "gemini-3.1-flash-lite",
            "api_key": "primary-key",
            "base_url": "https://example.com",
            "backup_provider": "groq",
            "backup_model": "openai/gpt-oss-20b",
            "backup_api_key": "backup-key",
            "backup_base_url": "https://api.groq.com/openai/v1",
            "llm_timeout_seconds": 10.0,
            "llm_max_retries": 2,
        },
    )()

    client = LLMClient(cfg=fake_cfg)
    client._primary_client = type(
        "FakePrimaryClient",
        (),
        {"chat": type("Chat", (), {"completions": FailingPrimaryCompletions()})()},
    )()
    client._backup_client = type(
        "FakeBackupClient",
        (),
        {"chat": type("Chat", (), {"completions": SucceedingBackupCompletions()})()},
    )()

    result = asyncio.run(
        client.call_json(
            system_prompt="sys",
            user_prompt="usr",
            max_tokens=80,
        )
    )
    assert result == {"ambiguous": False}
    assert len(captured_backup_kwargs) == 1
    assert captured_backup_kwargs[0]["model"] == "openai/gpt-oss-20b"
    assert captured_backup_kwargs[0]["reasoning_effort"] == "low"
    assert captured_backup_kwargs[0]["max_tokens"] >= 1024


def test_extended_greeting_fast_path_zero_llm_calls(monkeypatch):
    from app.engine.llm import LLMClient

    monkeypatch.setattr("app.engine.embeddings.embed_texts", _orthogonal_embed)

    class FailIfCalledLLM(LLMClient):
        async def _request_once(self, **kwargs) -> str:
            raise AssertionError("Greeting fast-path should never call LLM")

    client = FailIfCalledLLM()
    for greeting in ("heyy", "hiiii!", "okay", "Good Morning"):
        res = asyncio.run(
            analyze_sentence(
                AnalyzeRequest(sentence=greeting),
                llm_client=client,
                embed_fn=_orthogonal_embed,
                enable_logging=False,
            )
        )
        assert res.ambiguous is False
        assert res.confidence == 1.0
        assert res.needs_clarification is False


def test_cached_clarification_option_fast_path(monkeypatch):
    from app.engine.llm import LLMClient
    from app.engine.pipeline import clear_analyze_cache

    clear_analyze_cache()
    monkeypatch.setattr("app.engine.embeddings.embed_texts", _orthogonal_embed)

    class SpyClient(LLMClient):
        def __init__(self) -> None:
            super().__init__()
            self.calls = 0

        async def _request_once(self, *, system_prompt: str, user_prompt: str, **kwargs) -> str:
            self.calls += 1
            if "semantic evaluator" in system_prompt:
                return json.dumps({"choice": "unclear", "reason": "ambiguous"})
            if "clarification" in system_prompt.lower() and "resolved_meaning" in system_prompt.lower():
                raise AssertionError("Exact option click should resolve from cache without LLM")
            return json.dumps(
                {
                    "ambiguous": True,
                    "ambiguities": [
                        {"type": "lexical", "span": "bat", "explanation": "Animal or sports bat."}
                    ],
                    "interpretations": [
                        {"id": "i1", "meaning": "I saw a flying mammal."},
                        {"id": "i2", "meaning": "I saw a sports bat."},
                    ],
                    "clarification_question": "Animal or sports equipment?",
                    "options": ["Animal bat", "Sports bat"],
                }
            )

    client = SpyClient()
    first = asyncio.run(
        analyze_sentence(
            AnalyzeRequest(sentence="I saw a bat."),
            llm_client=client,
            enable_logging=False,
        )
    )
    assert first.needs_clarification is True
    calls_before_click = client.calls

    resolved = asyncio.run(
        analyze_sentence(
            AnalyzeRequest(
                sentence="I saw a bat.",
                history=[
                    HistoryMessage(role="user", content="I saw a bat."),
                    HistoryMessage(role="assistant", content="Animal or sports equipment?"),
                ],
                clarification=ClarificationInput(
                    question="Animal or sports equipment?",
                    answer="Animal bat",
                ),
            ),
            llm_client=client,
            enable_logging=False,
        )
    )
    assert client.calls == calls_before_click
    assert resolved.ambiguous is False
    assert resolved.confidence == 1.0
    assert resolved.resolution_basis == "clarification"
    assert resolved.interpretations[0].meaning == "I saw a flying mammal."


def test_clarifier_reminds_user_of_earlier_resolved_meaning():
    from app.engine.clarifier import enrich_clarification_with_history

    question, options = enrich_clarification_with_history(
        question="Did you mean a flying mammal or a baseball bat?",
        options=["Flying mammal", "Baseball bat"],
        interpretations=[
            Interpretation(id="i1", meaning="I saw a flying mammal.", probability=0.5),
            Interpretation(id="i2", meaning="I saw a baseball bat.", probability=0.5),
        ],
        history=[
            HistoryMessage(role="user", content="I saw a bat on the porch."),
            HistoryMessage(
                role="assistant",
                content="Got it: I saw a flying mammal. (resolved by your answer)",
            ),
            HistoryMessage(role="user", content="And another bat flew by!"),
        ],
    )
    assert "Earlier in this chat you meant" in question
    assert "I saw a flying mammal" in question
    assert options[0] == "Flying mammal (same as earlier)"
    assert options[1] == "Baseball bat"


def test_stream_anaphora_dual_resolvers(monkeypatch, tmp_path):
    from fastapi.testclient import TestClient
    from app.engine.anaphora import AnaphoraResolverOutput, PronounResolution
    from app.main import app

    class AnaphoraStreamClient:
        async def call_json(self, *, system_prompt: str, schema_model=None, **kwargs):
            if schema_model is AnaphoraResolverOutput:
                if "Resolver A" in system_prompt:
                    return AnaphoraResolverOutput(
                        resolutions=[PronounResolution(pronoun="she", antecedent="Alice", confidence=0.6)]
                    )
                return AnaphoraResolverOutput(
                    resolutions=[PronounResolution(pronoun="she", antecedent="Maya", confidence=0.6)]
                )
            if "choice" in getattr(schema_model, "model_fields", {}):
                return schema_model.model_validate({"choice": "unclear", "reason": "ambiguous"})
            if "clarification_question" in getattr(schema_model, "model_fields", {}) and "ambiguous" not in getattr(schema_model, "model_fields", {}):
                return schema_model.model_validate(
                    {"clarification_question": "Did she mean Alice or Maya?", "options": ["Alice", "Maya"]}
                )
            return RawDetectionResult(
                ambiguous=True,
                ambiguities=[{"type": "anaphoric", "span": "she", "explanation": "Alice or Maya."}],
                interpretations=[
                    RawInterpretationItem(id="i1", meaning="Alice failed the exam."),
                    RawInterpretationItem(id="i2", meaning="Maya failed the exam."),
                ],
                clarification_question="Did she mean Alice or Maya?",
                options=["Alice", "Maya"],
            )

    fake_settings = type(
        "FakeSettings",
        (),
        {
            "llm_provider": "gemini",
            "model_name": "gemini-3.1-flash-lite",
            "threshold": 0.7,
            "n_samples": 5,
            "temperature_detect": 0.0,
            "temperature_vote": 0.8,
            "seed": 42,
            "interactions_log_path": tmp_path / "anaphora_stream.jsonl",
        },
    )()
    monkeypatch.setattr("app.engine.pipeline.default_llm_client", AnaphoraStreamClient())
    monkeypatch.setattr("app.engine.embeddings.embed_texts", _orthogonal_embed)
    monkeypatch.setattr("app.engine.pipeline.settings", fake_settings)

    client = TestClient(app)
    res = client.post("/analyze/stream", json={"sentence": "Alice told Maya that she failed the exam."})
    assert res.status_code == 200
    body = res.text
    assert '"step": "resolving_anaphora"' in body
    assert "event: resolver" in body
    assert "Resolver A (syntax)" in body
    assert "Resolver B (semantics)" in body
    assert '"antecedent": "Alice"' in body
    assert '"antecedent": "Maya"' in body
    assert "event: done" in body
