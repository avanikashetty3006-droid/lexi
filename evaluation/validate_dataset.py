r"""Checks evaluation/data/dataset.jsonl.  Run:  python evaluation\\validate_dataset.py"""
from __future__ import annotations

import sys
from collections import Counter

from common import load_dataset

TYPES = {"lexical", "syntactic", "semantic", "contextual", "anaphoric"}
FIELDS = {"id", "sentence", "history", "ambiguous", "types", "gold_interpretations",
          "clarification_answer", "gold_resolved", "source", "split"}


def main() -> int:
    rows = load_dataset()
    errors: list[str] = []
    ids = Counter(r["id"] for r in rows)
    for i, r in ids.items():
        if i and r > 1:
            errors.append(f"duplicate id: {i}")
    for r in rows:
        rid = r.get("id", "?")
        missing = FIELDS - set(r)
        if missing:
            errors.append(f"{rid}: missing fields {sorted(missing)}")
            continue
        if r["split"] not in ("dev", "test"):
            errors.append(f"{rid}: split must be dev or test")
        if r["source"] not in ("own", "public"):
            errors.append(f"{rid}: source must be own or public")
        if r["ambiguous"]:
            if len(r["gold_interpretations"]) < 2:
                errors.append(f"{rid}: ambiguous row needs 2+ gold_interpretations")
            if r["gold_resolved"] not in r["gold_interpretations"]:
                errors.append(f"{rid}: gold_resolved must be one of gold_interpretations")
            if not r["types"] or set(r["types"]) - TYPES:
                errors.append(f"{rid}: bad types {r['types']}")
            if not r["clarification_answer"].strip():
                errors.append(f"{rid}: ambiguous row needs clarification_answer")
        else:
            if r["types"] or len(r["gold_interpretations"]) != 1:
                errors.append(f"{rid}: clean row needs types=[] and exactly 1 gold interpretation")
    n = len(rows)
    clean = sum(1 for r in rows if not r["ambiguous"])
    multi = sum(1 for r in rows if r["history"])
    print(f"rows={n} clean={clean} ({clean / n:.0%}) multi-turn={multi}")
    print("splits:", dict(Counter(r["split"] for r in rows)))
    print("types :", dict(Counter(t for r in rows for t in r["types"])))
    if n < 200:
        print(f"NOTE: {n} rows. The plan needs ~200 verified rows (about 1/3 clean, 20 multi-turn).")
    for e in errors:
        print("ERROR:", e)
    print("OK" if not errors else f"{len(errors)} error(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
