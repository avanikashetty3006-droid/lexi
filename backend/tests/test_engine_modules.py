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
