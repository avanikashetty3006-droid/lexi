r"""Run the silent-guess baseline (/baseline) on the same rows and score it.

  python evaluation\baseline_eval.py --split dev
  python evaluation\baseline_eval.py --split test
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


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", choices=["dev", "test"], required=True)
    ap.add_argument("--base-url", default=C.DEFAULT_BASE_URL)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--sleep", type=float, default=0.5)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--rescore", action="store_true")
    ap.add_argument("--no-embeddings", action="store_true")
    args = ap.parse_args()

    prefix = f"{'dryrun_' if args.dry_run else ''}{args.split}_baseline"
    raw_path = C.RESULTS_DIR / f"{prefix}_raw.jsonl"
    summary_path = C.RESULTS_DIR / f"{prefix}_summary.json"
    if args.dry_run:
        print("!! DRY RUN: fake numbers, do NOT report them !!")

    matcher_name = "rescore"
    if args.rescore:
        rows = C.read_jsonl(raw_path)
    else:
        data = C.load_dataset(args.split)[: args.limit]
        matcher = C.MeaningMatcher(use_embeddings=not args.no_embeddings)
        matcher_name = matcher.name
        client = None if args.dry_run else httpx.Client(base_url=args.base_url)
        rows = []
        for i, row in enumerate(data, 1):
            base = {"id": row["id"], "sentence": row["sentence"], "split": row["split"],
                    "gold_ambiguous": row["ambiguous"], "gold_types": row["types"],
                    "gold_resolved": row["gold_resolved"]}
            try:
                if args.dry_run:
                    rng = random.Random("b" + row["id"])
                    pred = {"pred_ambiguous": rng.random() < 0.5, "auto_guess": "dry",
                            "auto_correct": rng.random() < 0.5}
                else:
                    res = C.api_post(client, "/baseline", {"sentence": row["sentence"]})
                    pred = {"pred_ambiguous": bool(res["ambiguous"]), "auto_guess": res["chosen_meaning"],
                            "auto_correct": matcher.is_correct(res["chosen_meaning"], row)}
            except Exception as exc:  # noqa: BLE001
                pred = {"pred_ambiguous": False, "auto_guess": "", "auto_correct": False, "error": str(exc)}
                print(f"  ERROR {row['id']}: {exc}")
            rows.append({**base, **pred})
            print(f"[{i}/{len(data)}] {row['id']}")
            if not args.dry_run:
                time.sleep(args.sleep)
        C.write_jsonl(raw_path, rows)
        C.write_review_csv(C.RESULTS_DIR / f"{prefix}_review.csv", rows)

    changed = C.apply_human_review(rows, C.RESULTS_DIR / f"{prefix}_review.csv")
    summary = M.summarize_baseline(rows)
    summary["meta"] = {"system": "baseline", "split": args.split, "dry_run": args.dry_run,
                       "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                       "dataset_sha256": C.file_sha256(C.DATA_PATH), "matcher": matcher_name,
                       "human_review_cells_applied": changed}
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps({k: summary[k] for k in ("n_rows", "f1", "false_positive_rate",
                                              "resolution_accuracy", "n_errors")}, indent=2))
    print("saved:", summary_path)


if __name__ == "__main__":
    main()
