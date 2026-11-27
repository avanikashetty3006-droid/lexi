# Lexi API contract (v1.1)

Changing this file means telling the whole team first.
v1.1 adds `POST /feedback` (the only change from v1.0). `/analyze` and `/baseline` are unchanged.

## POST /analyze

Request:
```json
{
  "sentence": "str",
  "history": [{"role": "user|assistant", "content": "str"}],
  "domain": "general|requirements",
  "threshold": 0.7,
  "clarification": {"question": "str", "answer": "str"}
}
```
`threshold` and `clarification` are optional.

Response:
```json
{
  "sentence": "str",
  "ambiguous": true,
  "confidence": 0.0,
  "ambiguities": [{"type": "lexical|syntactic|semantic|contextual|anaphoric",
                   "span": "str", "start": 0, "end": 0, "explanation": "str"}],
  "interpretations": [{"id": "i1", "meaning": "str", "probability": 0.0}],
  "uncertainty": {"vote_split": {"i1": 0.0}, "semantic_entropy": 0.0},
  "semantic_map": [{"id": "i1", "x": 0.0, "y": 0.0, "label": "str"}],
  "needs_clarification": false,
  "clarification_question": "str or null",
  "options": ["str"],
  "resolved_interpretation_id": "str or null",
  "resolution_basis": "none|context|clarification",
  "threshold_used": 0.7,
  "latency_ms": 0
}
```
Clean sentence: `ambiguous=false`, `ambiguities=[]`, exactly one interpretation with probability 1.0, no question.
`vote_split` may also contain the key `"unclear"`.

## POST /baseline
Request `{"sentence": "str"}`. Response `{"ambiguous": bool, "chosen_meaning": "str"}`.
The baseline commits silently to one meaning and never asks.

## POST /feedback  (new in v1.1)
Stores one user-interaction event in `backend/logs/feedback.jsonl`. Used by the user study and dashboard.
```json
{
  "event": "override|feedback|slider",
  "session_id": "str (optional)",
  "sentence": "str (optional)",
  "message_id": "str (optional)",
  "vote": "up|down (feedback events)",
  "original_id": "str (override events)",
  "chosen_id": "str (override events)",
  "chosen_meaning": "str (override events, max 1000 chars)",
  "threshold": 0.7
}
```
Response `{"status": "ok"}`. The frontend never blocks on this call.

## Dataset row (evaluation/data/dataset.jsonl)
```json
{"id": "str", "sentence": "str", "history": [], "ambiguous": true, "types": ["str"],
 "gold_interpretations": ["str"], "clarification_answer": "str", "gold_resolved": "str",
 "source": "own|public", "split": "dev|test"}
```
Conventions used by the evaluation: `gold_interpretations` are full-sentence paraphrases, and for
ambiguous rows `gold_resolved` is exactly one of them (the one the speaker meant).
For clean rows `types` is `[]`, there is exactly one gold interpretation and `clarification_answer` is `""`.
