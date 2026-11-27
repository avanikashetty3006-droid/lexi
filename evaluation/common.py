"""Shared helpers for the evaluation scripts (no scoring logic here, see metrics.py)."""
from __future__ import annotations

import json
import re
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parent
DATA_PATH = EVAL_DIR / "data" / "dataset.jsonl"
RESULTS_DIR = EVAL_DIR / "results"
DEFAULT_BASE_URL = "http://localhost:8000"


def load_dataset(split: str | None = None, path: Path = DATA_PATH) -> list[dict]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if split:
        rows = [r for r in rows if r["split"] == split]
    return rows


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


_TOKEN = re.compile(r"[a-z0-9']+")


def _jaccard(a: str, b: str) -> float:
    ta, tb = set(_TOKEN.findall(a.lower())), set(_TOKEN.findall(b.lower()))
    return len(ta & tb) / len(ta | tb) if ta and tb else 0.0


class MeaningMatcher:
    """Decides which gold interpretation a system answer corresponds to.

    A system meaning counts as correct when its NEAREST gold interpretation is
    the gold_resolved one (and the similarity is above a floor). Uses
    all-MiniLM-L6-v2 when sentence-transformers is installed, otherwise a
    token-overlap fallback. Automatic matching is only a first pass: hand-check
    the rows exported to results/resolution_review.csv.
    """

    def __init__(self, use_embeddings: bool = True, floor: float = 0.45) -> None:
        self.floor = floor
        self.name = "token-overlap"
        self._model = None
        if use_embeddings:
            try:
                from sentence_transformers import SentenceTransformer

                self._model = SentenceTransformer("all-MiniLM-L6-v2")
                self.name = "all-MiniLM-L6-v2"
            except Exception:  # library missing or offline
                self._model = None

    def _sims(self, text: str, candidates: list[str]) -> list[float]:
        if self._model is None:
            return [_jaccard(text, c) for c in candidates]
        vecs = self._model.encode([text] + candidates, normalize_embeddings=True)
        return [float(vecs[0] @ v) for v in vecs[1:]]

    def is_correct(self, meaning: str | None, row: dict) -> bool:
        if not meaning or not meaning.strip():
            return False
        cands = row["gold_interpretations"]
        sims = self._sims(meaning, cands)
        best = max(range(len(cands)), key=lambda i: sims[i])
        return cands[best] == row["gold_resolved"] and sims[best] >= self.floor


# ---------- API + reproducibility helpers ----------
import csv
import hashlib
import time

import httpx


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def api_post(client: httpx.Client, path: str, payload: dict, retries: int = 2) -> dict:
    last: Exception | None = None
    for attempt in range(retries + 1):
        try:
            res = client.post(path, json=payload, timeout=60.0)
            res.raise_for_status()
            return res.json()
        except Exception as exc:  # noqa: BLE001
            last = exc
            time.sleep(1.0 * (attempt + 1))
    raise RuntimeError(f"{path} failed after retries: {last}")


def chosen_meaning(result: dict) -> str:
    """Meaning Lexi commits to: the resolved interpretation, else the most probable one."""
    interps = result.get("interpretations") or []
    rid = result.get("resolved_interpretation_id")
    for i in interps:
        if rid and i["id"] == rid:
            return i["meaning"]
    if not interps:
        return ""
    return max(interps, key=lambda i: i.get("probability", 0.0))["meaning"]


REVIEW_FIELDS = ["id", "sentence", "gold_resolved", "auto_guess", "auto_correct",
                 "clarified_meaning", "clarified_correct",
                 "human_auto_correct", "human_clarified_correct"]


def write_review_csv(path: Path, rows: list[dict]) -> None:
    """Export gold-ambiguous rows so a person can confirm the automatic matching."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        w = csv.DictWriter(handle, fieldnames=REVIEW_FIELDS)
        w.writeheader()
        for r in rows:
            if not r["gold_ambiguous"]:
                continue
            w.writerow({"id": r["id"], "sentence": r["sentence"], "gold_resolved": r["gold_resolved"],
                        "auto_guess": r.get("auto_guess", ""), "auto_correct": int(bool(r.get("auto_correct"))),
                        "clarified_meaning": r.get("clarified_meaning", ""),
                        "clarified_correct": int(bool(r.get("clarified_correct"))),
                        "human_auto_correct": "", "human_clarified_correct": ""})


def apply_human_review(rows: list[dict], path: Path) -> int:
    """Override automatic correctness with filled-in human columns (1/0). Returns rows changed."""
    if not path.exists():
        return 0
    by_id = {r["id"]: r for r in rows}
    changed = 0
    with path.open(encoding="utf-8", newline="") as handle:
        for rec in csv.DictReader(handle):
            row = by_id.get(rec["id"])
            if not row:
                continue
            for human, field in (("human_auto_correct", "auto_correct"),
                                 ("human_clarified_correct", "clarified_correct")):
                v = (rec.get(human) or "").strip()
                if v in ("0", "1"):
                    row[field] = bool(int(v))
                    changed += 1
    return changed
