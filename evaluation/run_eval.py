r"""Run Lexi (/analyze) on the labelled dataset and score it.

Examples (Windows cmd, from the repo root, backend running on port 8000):
  python evaluation\run_eval.py --split dev
  python evaluation\tune_threshold.py
  python evaluation\run_eval.py --split test          (uses the dev-tuned threshold)
  python evaluation\run_eval.py --split test --rescore  (re-score after human review, no API calls)
"""
from __future__ import annotations

import argparse
import json
import random
import time
from datetime import datetime, timezone

import httpx

import common as C
import metrics as M


def dry_row(row: dict) -> dict:
    """Deterministic fake predictions. ONLY to test the pipeline; results are meaningless."""
    rng = random.Random(row["id"])
    pred = row["ambiguous"] if rng.random() < 0.8 else not row["ambiguous"]
    conf = round(rng.uniform(0.4, 1.0), 2) if pred else 1.0
    return {"pred_ambiguous": pred, "pred_types": row["types"] if pred else [], "confidence": conf,
            "semantic_entropy": round(rng.uniform(0, 1), 3), "vote_split": {"i1": conf, "i2": round(1 - conf, 2)},
            "latency_ms": rng.randint(800, 4000), "auto_guess": "dry", "auto_correct": rng.random() < 0.6,
            "clarified_meaning": "dry", "clarified_correct": rng.random() < 0.9}


def run_row(client: httpx.Client, matcher: C.MeaningMatcher, row: dict, threshold: float) -> dict:
    res = C.api_post(client, "/analyze", {"sentence": row["sentence"], "history": row["history"],
                                          "domain": "general", "threshold": threshold})
    guess = C.chosen_meaning(res)
    out = {
        "pred_ambiguous": bool(res["ambiguous"]),
        "pred_types": sorted({a["type"] for a in res.get("ambiguities", [])}),
        "confidence": res["confidence"],
        "semantic_entropy": res["uncertainty"]["semantic_entropy"],
        "vote_split": res["uncertainty"]["vote_split"],
        "latency_ms": res["latency_ms"],
        "auto_guess": guess,
        "auto_correct": matcher.is_correct(guess, row),
    }
    # Ask the clarification for EVERY gold-ambiguous row Lexi flagged, so the threshold can be
    # swept later without re-running the model.
    if row["ambiguous"] and res["ambiguous"]:
        q = res.get("clarification_question") or "Which meaning did you intend?"
        res2 = C.api_post(client, "/analyze", {
            "sentence": row["sentence"], "history": row["history"], "domain": "general",
            "threshold": threshold, "clarification": {"question": q, "answer": row["clarification_answer"]}})
        m = C.chosen_meaning(res2)
        out["clarified_meaning"] = m
        out["clarified_correct"] = matcher.is_correct(m, row)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", choices=["dev", "test"], required=True)
    ap.add_argument("--threshold", type=float, default=None)
    ap.add_argument("--base-url", default=C.DEFAULT_BASE_URL)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--sleep", type=float, default=0.5, help="pause between rows (rate limits)")
    ap.add_argument("--dry-run", action="store_true", help="fake predictions to test the pipeline")
    ap.add_argument("--rescore", action="store_true", help="re-score saved raw results, no API calls")
    ap.add_argument("--no-embeddings", action="store_true")
    args = ap.parse_args()

    prefix = f"{'dryrun_' if args.dry_run else ''}{args.split}_lexi"
    raw_path = C.RESULTS_DIR / f"{prefix}_raw.jsonl"
    summary_path = C.RESULTS_DIR / f"{prefix}_summary.json"
    best_path = C.RESULTS_DIR / "best_threshold.json"

    threshold = args.threshold
    if threshold is None:
        if args.split == "test":
            if not best_path.exists():
                raise SystemExit("TEST needs a threshold tuned on DEV. Run tune_threshold.py first "
                                 "or pass --threshold. (Never tune on the test split.)")
            threshold = json.loads(best_path.read_text())["threshold"]
        else:
            threshold = 0.7
    if args.dry_run:
        print("!! DRY RUN: fake numbers, do NOT report them !!")

    if args.rescore:
        rows = C.read_jsonl(raw_path)
        matcher_name = "rescore"
    else:
        data = C.load_dataset(args.split)[: args.limit]
        matcher = C.MeaningMatcher(use_embeddings=not args.no_embeddings)
        matcher_name = matcher.name
        meta = {}
        client = None if args.dry_run else httpx.Client(base_url=args.base_url)
        if client is not None:
            try:
                meta = client.get("/health", timeout=10).json()
            except Exception as exc:  # noqa: BLE001
                raise SystemExit(f"Backend not reachable at {args.base_url}: {exc}")
        rows = []
        for i, row in enumerate(data, 1):
            base = {"id": row["id"], "sentence": row["sentence"], "split": row["split"],
                    "gold_ambiguous": row["ambiguous"], "gold_types": row["types"],
                    "gold_resolved": row["gold_resolved"]}
            try:
                pred = dry_row(row) if args.dry_run else run_row(client, matcher, row, threshold)
            except Exception as exc:  # noqa: BLE001
                pred = {"pred_ambiguous": False, "pred_types": [], "confidence": 1.0, "error": str(exc)}
                print(f"  ERROR {row['id']}: {exc}")
            rows.append({**base, **pred})
            print(f"[{i}/{len(data)}] {row['id']} pred_ambiguous={pred['pred_ambiguous']} "
                  f"conf={pred.get('confidence')}")
            if not args.dry_run:
                time.sleep(args.sleep)
        C.write_jsonl(raw_path, rows)
        C.write_review_csv(C.RESULTS_DIR / f"{prefix}_review.csv", rows)

    changed = C.apply_human_review(rows, C.RESULTS_DIR / f"{prefix}_review.csv")
    summary = M.summarize_lexi(rows, threshold)
    summary["meta"] = {
        "system": "lexi", "split": args.split, "dry_run": args.dry_run,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "dataset_sha256": C.file_sha256(C.DATA_PATH),
        "matcher": matcher_name, "human_review_cells_applied": changed,
        "backend": locals().get("meta", {}) if not args.rescore else {},
    }
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps({k: summary[k] for k in ("n_rows", "f1", "false_positive_rate", "resolution_accuracy",
                                              "questions_per_ambiguous_row", "n_errors")}, indent=2))
    print("saved:", summary_path)


if __name__ == "__main__":
    main()
