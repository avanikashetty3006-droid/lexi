from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.engine.confidence import compute_vote_confidence
from app.engine.detector import RawAmbiguityItem, RawDetectionResult, RawInterpretationItem, locate_span
from app.engine.pipeline import analyze_sentence
from app.main import app
from app.schemas import AnalyzeRequest, AnalyzeResponse, BaselineResponse

# 15 ambiguous (3 per type) + 5 clean sentences for Task 1 & Task 8
TEST_SENTENCES = [
    # Lexical (3)
    {"id": "lex_1", "sentence": "I saw the bat on the porch.", "ambiguous": True, "type": "lexical", "span": "bat"},
    {"id": "lex_2", "sentence": "We need a lighter tool for this job.", "ambiguous": True, "type": "lexical", "span": "lighter"},
    {"id": "lex_3", "sentence": "He left the match early.", "ambiguous": True, "type": "lexical", "span": "match"},
    # Syntactic (3)
    {"id": "syn_1", "sentence": "I saw the man with the telescope.", "ambiguous": True, "type": "syntactic", "span": "with the telescope"},
    {"id": "syn_2", "sentence": "Visiting relatives can be exhausting.", "ambiguous": True, "type": "syntactic", "span": "Visiting relatives"},
    {"id": "syn_3", "sentence": "The chicken is ready to eat.", "ambiguous": True, "type": "syntactic", "span": "ready to eat"},
    # Semantic (3)
    {"id": "sem_1", "sentence": "Every student read a book.", "ambiguous": True, "type": "semantic", "span": "Every student read a book"},
    {"id": "sem_2", "sentence": "Two engineers reviewed three specifications.", "ambiguous": True, "type": "semantic", "span": "Two engineers reviewed three specifications"},
    {"id": "sem_3", "sentence": "I didn't call you because I was busy.", "ambiguous": True, "type": "semantic", "span": "didn't call you because I was busy"},
    # Contextual (3)
    {"id": "ctx_1", "sentence": "Make the dashboard faster.", "ambiguous": True, "type": "contextual", "span": "faster"},
    {"id": "ctx_2", "sentence": "Schedule the review for next Friday.", "ambiguous": True, "type": "contextual", "span": "next Friday"},
    {"id": "ctx_3", "sentence": "The system should handle large uploads.", "ambiguous": True, "type": "contextual", "span": "large uploads"},
    # Anaphoric (3)
    {"id": "ana_1", "sentence": "Alice told Maya that she failed the exam.", "ambiguous": True, "type": "anaphoric", "span": "she"},
    {"id": "ana_2", "sentence": "The trophy didn't fit in the suitcase because it was too big.", "ambiguous": True, "type": "anaphoric", "span": "it"},
    {"id": "ana_3", "sentence": "When the manager met the intern, he smiled nervously.", "ambiguous": True, "type": "anaphoric", "span": "he"},
    # Clean / Unambiguous (5)
    {"id": "cln_1", "sentence": "She deposited the check at the bank before closing.", "ambiguous": False, "type": None, "span": ""},
    {"id": "cln_2", "sentence": "Please send the finalized PDF invoice to accounting by Friday at 5 PM.", "ambiguous": False, "type": None, "span": ""},
    {"id": "cln_3", "sentence": "Water boils at 100 degrees Celsius at standard sea-level pressure.", "ambiguous": False, "type": None, "span": ""},
    {"id": "cln_4", "sentence": "The database backup completed with zero errors at 02:00 UTC.", "ambiguous": False, "type": None, "span": ""},
    {"id": "cln_5", "sentence": "Turn off the kitchen lights before locking the front door.", "ambiguous": False, "type": None, "span": ""},
]


class FakeLLMClient:
    """Deterministic stub matching the 20 test sentences for offline contract tests."""

    def __init__(self) -> None:
        self._by_sentence = {item["sentence"]: item for item in TEST_SENTENCES}

    async def call_json(self, *, system_prompt: str, user_prompt: str, schema_model=None, **kwargs):
        import json

        payload = json.loads(user_prompt)
        sentence = payload["sentence"]

        # Anaphora resolver request
        if "resolutions" in getattr(schema_model, "model_fields", {}):
            pronouns = payload.get("pronouns", [])
            candidates = payload.get("candidates", ["candidate_a", "candidate_b"])
            idx = 0 if "Resolver A" in system_prompt else 1
            chosen = candidates[idx % len(candidates)] if candidates else "unclear"
            return schema_model.model_validate(
                {
                    "resolutions": [
                        {"pronoun": p, "antecedent": chosen, "confidence": 0.7}
                        for p in pronouns
                    ]
                }
            )

        # Clarifier request
        if "clarification_question" in getattr(schema_model, "model_fields", {}) and "ambiguous" not in getattr(schema_model, "model_fields", {}):
            return schema_model.model_validate(
                {
                    "clarification_question": "Which meaning did you intend?",
                    "options": ["First reading", "Second reading"],
                }
            )

        # Baseline request
        if "chosen_meaning" in getattr(schema_model, "model_fields", {}):
            item = self._by_sentence.get(sentence, {"ambiguous": False})
            return BaselineResponse(
                ambiguous=bool(item["ambiguous"]),
                chosen_meaning=f"Primary reading of: {sentence}",
            )

        # Vote request
        if "choice" in getattr(schema_model, "model_fields", {}):
            seed = kwargs.get("seed", 0) or 0
            choice = "i1" if seed % 2 == 0 else "i2"
            return schema_model.model_validate({"choice": choice, "reason": "Stub vote"})

        # Detect request
        item = self._by_sentence[sentence]
        if not item["ambiguous"]:
            return RawDetectionResult(
                ambiguous=False,
                ambiguities=[],
                interpretations=[RawInterpretationItem(id="i1", meaning=f"Literal meaning: {sentence}")],
                clarification_question=None,
                options=[],
            )

        return RawDetectionResult(
            ambiguous=True,
            ambiguities=[
                RawAmbiguityItem(
                    type=item["type"],
                    span=item["span"],
                    explanation=f"'{item['span']}' admits multiple readings.",
                )
            ],
            interpretations=[
                RawInterpretationItem(id="i1", meaning="First plausible reading."),
                RawInterpretationItem(id="i2", meaning="Second plausible reading."),
            ],
            clarification_question="Which meaning did you intend?",
            options=["First reading", "Second reading"],
        )


def _fake_embed(texts: list[str]):
    import numpy as np

    dim = max(4, len(texts))
    mat = np.zeros((len(texts), dim), dtype=np.float32)
    for i in range(len(texts)):
        mat[i, i % dim] = 1.0
    return mat


def test_locate_span_exact_and_case_insensitive():
    sentence = "Alice told Maya that She failed."
    span, start, end = locate_span(sentence, "she")
    assert span == "She"
    assert sentence[start:end] == "She"


def test_compute_vote_confidence():
    split, conf, winner = compute_vote_confidence(["i1", "i1", "i2", "unclear", "i1"], ["i1", "i2"])
    assert split == {"i1": 0.6, "i2": 0.2, "unclear": 0.2}
    assert conf == 0.6
    assert winner == "i1"


@pytest.mark.parametrize("case", TEST_SENTENCES, ids=[c["id"] for c in TEST_SENTENCES])
def test_pipeline_contract_20_sentences(case):
    import asyncio

    fake_client = FakeLLMClient()
    req = AnalyzeRequest(sentence=case["sentence"], threshold=0.7)
    res: AnalyzeResponse = asyncio.run(
        analyze_sentence(
            req,
            llm_client=fake_client,
            embed_fn=_fake_embed,
            enable_logging=False,
        )
    )

    assert res.sentence == case["sentence"]
    assert res.threshold_used == 0.7
    assert res.ambiguous is case["ambiguous"]

    if not case["ambiguous"]:
        assert res.ambiguities == []
        assert len(res.interpretations) == 1
        assert res.interpretations[0].id == "i1"
        assert res.interpretations[0].probability == 1.0
        assert res.uncertainty.semantic_entropy == 0.0
        assert res.needs_clarification is False
        assert res.clarification_question is None
        assert res.options == []
    else:
        assert len(res.ambiguities) >= 1
        span = res.ambiguities[0]
        assert case["sentence"][span.start : span.end] == span.span
        assert len(res.interpretations) >= 2
        assert res.uncertainty.semantic_entropy > 0.0
        assert len(res.semantic_map) == len(res.interpretations)
        assert res.needs_clarification is True
        assert res.clarification_question is not None
        assert len(res.options) >= 2


def test_fastapi_endpoints_with_mocked_llm(monkeypatch, tmp_path):
    fake_client = FakeLLMClient()
    monkeypatch.setattr("app.engine.pipeline.default_llm_client", fake_client)
    monkeypatch.setattr("app.engine.baseline.default_llm_client", fake_client)
    monkeypatch.setattr("app.engine.embeddings.embed_texts", _fake_embed)
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
            "interactions_log_path": tmp_path / "api_interactions.jsonl",
        },
    )()
    monkeypatch.setattr("app.config.settings", fake_settings)
    monkeypatch.setattr("app.engine.pipeline.settings", fake_settings)
    monkeypatch.setattr("app.main.settings", fake_settings)

    client = TestClient(app)

    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"

    clean = client.post("/analyze", json={"sentence": TEST_SENTENCES[-1]["sentence"], "threshold": 0.65})
    assert clean.status_code == 200
    body = clean.json()
    assert body["ambiguous"] is False
    assert body["threshold_used"] == 0.65
    assert body["needs_clarification"] is False

    base = client.post("/baseline", json={"sentence": TEST_SENTENCES[0]["sentence"]})
    assert base.status_code == 200
    assert "chosen_meaning" in base.json()


@pytest.mark.skipif(
    os.getenv("RUN_LIVE_TESTS") != "1",
    reason="Set RUN_LIVE_TESTS=1 with an API key in .env to run live LLM evaluation.",
)
def test_live_20_sentences_clean_precision():
    import asyncio

    clean_false_positives = 0
    ambig_detected = 0

    for case in TEST_SENTENCES:
        res = asyncio.run(analyze_sentence(AnalyzeRequest(sentence=case["sentence"])))
        if not case["ambiguous"] and res.ambiguous:
            clean_false_positives += 1
        if case["ambiguous"] and res.ambiguous:
            ambig_detected += 1

    assert clean_false_positives <= 1, f"Too many clean false positives: {clean_false_positives}/5"
    assert ambig_detected >= 11, f"Low ambiguous recall: {ambig_detected}/15"
