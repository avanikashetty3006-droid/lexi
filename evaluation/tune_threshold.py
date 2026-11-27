r"""Pick the asking threshold using the DEV split only.

Needs results/dev_lexi_raw.jsonl (from: python evaluation\run_eval.py --split dev).
Score = resolution accuracy on ambiguous rows - LAMBDA * (questions asked per row, all rows).
Higher LAMBDA means "ask less". Ties go to the lower threshold (fewer questions).
"""
from __future__ import annotations

import argparse
import csv
import json

import common as C
import metrics as M


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lam", type=float, default=0.1, help="cost per question")
    ap.add_argument("--raw", default=str(C.RESULTS_DIR / "dev_lexi_raw.jsonl"))
    args = ap.parse_args()

    rows = C.read_jsonl(C.Path(args.raw))
    if any(r["split"] != "dev" for r in rows):
        raise SystemExit("Refusing to tune: the raw file contains non-dev rows. Never tune on test.")
    C.apply_human_review(rows, C.RESULTS_DIR / "dev_lexi_review.csv")

    sweep = []
    for k in range(0, 21):
        t = round(k * 0.05, 2)
        acc = M.resolution_accuracy(rows, t)
        asks_per_row = sum(M.asked(r, t) for r in rows) / len(rows)
        sweep.append({"threshold": t, "resolution_accuracy": acc,
                      "questions_per_ambiguous_row": M.questions_per_ambiguous(rows, t),
                      "unnecessary_question_rate_on_clean": M.unnecessary_question_rate(rows, t),
                      "asks_per_row": asks_per_row, "score": (acc or 0.0) - args.lam * asks_per_row})
    best = max(sweep, key=lambda s: (round(s["score"], 6), -s["threshold"]))

    out = C.RESULTS_DIR / "threshold_sweep.csv"
    with out.open("w", encoding="utf-8", newline="") as handle:
        w = csv.DictWriter(handle, fieldnames=list(sweep[0]))
        w.writeheader()
        w.writerows(sweep)
    (C.RESULTS_DIR / "best_threshold.json").write_text(
        json.dumps({"threshold": best["threshold"], "tuned_on": "dev", "lambda": args.lam,
                    "n_dev_rows": len(rows), "dataset_sha256": C.file_sha256(C.DATA_PATH)}, indent=2),
        encoding="utf-8")
    print(f"best threshold on DEV: {best['threshold']} (score {best['score']:.3f}); sweep -> {out}")


if __name__ == "__main__":
    main()
