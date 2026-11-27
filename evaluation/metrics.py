"""Pure scoring functions (no network). Unit-tested in tests/test_metrics.py.

Raw row fields used (written by run_eval.py / baseline_eval.py):
  gold_ambiguous, gold_types, pred_ambiguous, pred_types, confidence,
  semantic_entropy, vote_split, latency_ms, auto_correct, clarified_correct
"""
from __future__ import annotations

import math
import random
from statistics import mean
from typing import Callable

TYPES = ["lexical", "syntactic", "semantic", "contextual", "anaphoric"]


# ---------- basic helpers ----------
def safe_div(a: float, b: float) -> float | None:
    return a / b if b else None


def prf(tp: int, fp: int, fn: int) -> tuple[float | None, float | None, float | None]:
    p = safe_div(tp, tp + fp)
    r = safe_div(tp, tp + fn)
    f1 = None if p is None or r is None or (p + r) == 0 else 2 * p * r / (p + r)
    return p, r, f1


def confusion(rows: list[dict]) -> dict[str, int]:
    tp = sum(1 for r in rows if r["gold_ambiguous"] and r["pred_ambiguous"])
    fp = sum(1 for r in rows if not r["gold_ambiguous"] and r["pred_ambiguous"])
    fn = sum(1 for r in rows if r["gold_ambiguous"] and not r["pred_ambiguous"])
    tn = sum(1 for r in rows if not r["gold_ambiguous"] and not r["pred_ambiguous"])
    return {"tp": tp, "fp": fp, "fn": fn, "tn": tn}


def detection_f1(rows: list[dict]) -> float | None:
    c = confusion(rows)
    return prf(c["tp"], c["fp"], c["fn"])[2]


def false_positive_rate(rows: list[dict]) -> float | None:
    c = confusion(rows)
    return safe_div(c["fp"], c["fp"] + c["tn"])


def vote_entropy(vote_split: dict[str, float]) -> float:
    """Shannon entropy (bits) of the vote split, ignoring 'unclear'."""
    probs = [p for k, p in vote_split.items() if k != "unclear" and p > 0]
    total = sum(probs)
    if total <= 0:
        return 0.0
    return -sum((p / total) * math.log2(p / total) for p in probs)


def bootstrap_ci(rows: list, stat: Callable[[list], float | None], n: int = 1000,
                 seed: int = 0, alpha: float = 0.05) -> tuple[float | None, float | None]:
    """Percentile bootstrap over rows (resample rows with replacement)."""
    if not rows:
        return None, None
    rng = random.Random(seed)
    vals = []
    for _ in range(n):
        sample = [rows[rng.randrange(len(rows))] for _ in range(len(rows))]
        v = stat(sample)
        if v is not None:
            vals.append(v)
    if not vals:
        return None, None
    vals.sort()
    lo = vals[int((alpha / 2) * (len(vals) - 1))]
    hi = vals[int((1 - alpha / 2) * (len(vals) - 1))]
    return lo, hi


def percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    s = sorted(values)
    k = (len(s) - 1) * q
    f, c = math.floor(k), math.ceil(k)
    return s[f] if f == c else s[f] + (s[c] - s[f]) * (k - f)


def pearson(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) < 3:
        return None
    mx, my = mean(xs), mean(ys)
    sx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    sy = math.sqrt(sum((y - my) ** 2 for y in ys))
    if sx == 0 or sy == 0:
        return None
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / (sx * sy)


# ---------- Lexi ----------
def asked(row: dict, threshold: float) -> bool:
    return bool(row["pred_ambiguous"]) and row["confidence"] < threshold


def final_correct(row: dict, threshold: float) -> bool:
    """Is Lexi's final meaning right when it asks iff confidence < threshold?"""
    if asked(row, threshold):
        return bool(row.get("clarified_correct"))
    return bool(row.get("auto_correct"))


def resolution_accuracy(rows: list[dict], threshold: float) -> float | None:
    amb = [r for r in rows if r["gold_ambiguous"]]
    return mean(final_correct(r, threshold) for r in amb) if amb else None


def questions_per_ambiguous(rows: list[dict], threshold: float) -> float | None:
    amb = [r for r in rows if r["gold_ambiguous"]]
    return mean(asked(r, threshold) for r in amb) if amb else None


def unnecessary_question_rate(rows: list[dict], threshold: float) -> float | None:
    clean = [r for r in rows if not r["gold_ambiguous"]]
    return mean(asked(r, threshold) for r in clean) if clean else None


def per_type_recall(rows: list[dict]) -> dict[str, dict]:
    out = {}
    for t in TYPES:
        sub = [r for r in rows if r["gold_ambiguous"] and t in r["gold_types"]]
        detected = sum(1 for r in sub if r["pred_ambiguous"])
        type_ok = sum(1 for r in sub if r["pred_ambiguous"] and t in (r.get("pred_types") or []))
        out[t] = {"n": len(sub), "detected": detected, "type_match": type_ok,
                  "recall": safe_div(detected, len(sub))}
    return out


def calibration(rows: list[dict], bins: int = 3) -> dict:
    """Does higher vote confidence mean the automatic guess is right more often?
    Uses gold-ambiguous rows that Lexi flagged ambiguous."""
    sub = [r for r in rows if r["gold_ambiguous"] and r["pred_ambiguous"] and "auto_correct" in r]
    if not sub:
        return {"n": 0, "brier": None, "bins": []}
    brier = mean((r["confidence"] - float(bool(r["auto_correct"]))) ** 2 for r in sub)
    edges = [i / bins for i in range(bins + 1)]
    out = []
    for i in range(bins):
        lo, hi = edges[i], edges[i + 1]
        b = [r for r in sub if (lo <= r["confidence"] < hi) or (i == bins - 1 and r["confidence"] == 1.0)]
        out.append({"range": f"{lo:.2f}-{hi:.2f}", "n": len(b),
                    "mean_confidence": mean(r["confidence"] for r in b) if b else None,
                    "accuracy": mean(bool(r["auto_correct"]) for r in b) if b else None})
    return {"n": len(sub), "brier": brier, "bins": out}


def summarize_lexi(rows: list[dict], threshold: float, n_boot: int = 1000) -> dict:
    c = confusion(rows)
    p, r, f1 = prf(c["tp"], c["fp"], c["fn"])
    lat = [x["latency_ms"] for x in rows if x.get("latency_ms") is not None]
    amb_pred = [x for x in rows if x["pred_ambiguous"] and x.get("semantic_entropy") is not None]
    ve = [vote_entropy(x.get("vote_split") or {}) for x in amb_pred]
    se = [x["semantic_entropy"] for x in amb_pred]
    return {
        "n_rows": len(rows),
        "n_ambiguous": sum(1 for x in rows if x["gold_ambiguous"]),
        "n_clean": sum(1 for x in rows if not x["gold_ambiguous"]),
        "threshold": threshold,
        "confusion": c,
        "precision": p, "recall": r, "f1": f1,
        "f1_ci95": bootstrap_ci(rows, detection_f1, n_boot),
        "false_positive_rate": false_positive_rate(rows),
        "fpr_ci95": bootstrap_ci(rows, false_positive_rate, n_boot),
        "resolution_accuracy": resolution_accuracy(rows, threshold),
        "resolution_accuracy_ci95": bootstrap_ci(rows, lambda s: resolution_accuracy(s, threshold), n_boot),
        "questions_per_ambiguous_row": questions_per_ambiguous(rows, threshold),
        "unnecessary_question_rate_on_clean": unnecessary_question_rate(rows, threshold),
        "per_type": per_type_recall(rows),
        "calibration": calibration(rows),
        "latency_ms_p50": percentile(lat, 0.5),
        "latency_ms_p95": percentile(lat, 0.95),
        "entropy_vs_vote_entropy_pearson": pearson(se, ve),
        "n_errors": sum(1 for x in rows if x.get("error")),
    }


# ---------- Baseline (silent guess, never asks) ----------
def summarize_baseline(rows: list[dict], n_boot: int = 1000) -> dict:
    c = confusion(rows)
    p, r, f1 = prf(c["tp"], c["fp"], c["fn"])
    amb = [x for x in rows if x["gold_ambiguous"]]
    acc = lambda s: (mean(bool(x.get("auto_correct")) for x in s if x["gold_ambiguous"])
                     if any(x["gold_ambiguous"] for x in s) else None)
    return {
        "n_rows": len(rows), "n_ambiguous": len(amb),
        "confusion": c, "precision": p, "recall": r, "f1": f1,
        "f1_ci95": bootstrap_ci(rows, detection_f1, n_boot),
        "false_positive_rate": false_positive_rate(rows),
        "fpr_ci95": bootstrap_ci(rows, false_positive_rate, n_boot),
        "resolution_accuracy": acc(rows),
        "resolution_accuracy_ci95": bootstrap_ci(rows, acc, n_boot),
        "questions_per_ambiguous_row": 0.0,
        "n_errors": sum(1 for x in rows if x.get("error")),
    }


# ---------- User study ----------
def sus_score(answers: list[int]) -> float:
    """Standard SUS: 10 items rated 1-5; odd items score (x-1), even items (5-x); total*2.5."""
    if len(answers) != 10:
        raise ValueError("SUS needs exactly 10 answers")
    total = sum((a - 1) if i % 2 == 0 else (5 - a) for i, a in enumerate(answers))
    return total * 2.5


def tlx_raw(scales: list[float]) -> float:
    """Raw (unweighted) NASA-TLX: mean of the 6 subscales (each 0-100)."""
    if len(scales) != 6:
        raise ValueError("NASA-TLX needs 6 subscale ratings")
    return mean(scales)


def paired_bootstrap(diffs: list[float], n: int = 5000, seed: int = 0) -> dict:
    """Mean paired difference with a percentile bootstrap 95% CI. Exploratory for small n."""
    if not diffs:
        return {"n": 0, "mean_diff": None, "ci95": (None, None)}
    rng = random.Random(seed)
    means = sorted(mean(rng.choices(diffs, k=len(diffs))) for _ in range(n))
    return {"n": len(diffs), "mean_diff": mean(diffs),
            "ci95": (means[int(0.025 * (n - 1))], means[int(0.975 * (n - 1))])}
