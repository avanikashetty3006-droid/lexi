from __future__ import annotations

import json
import os
import sys
from pathlib import Path

os.environ.setdefault("LEXI_SKIP_WARMUP", "1")
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from fastapi.testclient import TestClient

from app import feedback
from app.main import app


def test_feedback_is_logged(tmp_path, monkeypatch):
    log = tmp_path / "feedback.jsonl"
    monkeypatch.setattr(feedback, "LOG_PATH", log)
    client = TestClient(app)
    res = client.post(
        "/feedback",
        json={"event": "feedback", "session_id": "s1", "message_id": "m1", "vote": "down"},
    )
    assert res.status_code == 200
    rows = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
    assert rows[0]["vote"] == "down" and rows[0]["session_id"] == "s1"


def test_feedback_rejects_bad_event(tmp_path, monkeypatch):
    monkeypatch.setattr(feedback, "LOG_PATH", tmp_path / "f.jsonl")
    client = TestClient(app)
    assert client.post("/feedback", json={"event": "nope"}).status_code == 422
