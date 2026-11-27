from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import metrics as M


def row(gold, pred, conf=1.0, auto=True, clar=True, types=None, gtypes=None):
    return {"gold_ambiguous": gold, "pred_ambiguous": pred, "confidence": conf,
            "auto_correct": auto, "clarified_correct": clar,
            "pred_types": types or [], "gold_types": gtypes or []}


def test_confusion_and_f1_by_hand():
    rows = [row(True, True), row(True, True), row(True, False), row(False, True), row(False, False), row(False, False)]
    c = M.confusion(rows)
    assert c == {"tp": 2, "fp": 1, "fn": 1, "tn": 2}
    p, r, f1 = M.prf(2, 1, 1)
    assert round(p, 4) == round(2 / 3, 4) and round(r, 4) == round(2 / 3, 4) and round(f1, 4) == round(2 / 3, 4)
    assert M.false_positive_rate(rows) == 1 / 3


def test_threshold_controls_asking_and_resolution():
    rows = [row(True, True, conf=0.4, auto=False, clar=True),   # unsure -> ask -> correct
            row(True, True, conf=0.9, auto=True, clar=True),    # sure -> no ask -> correct
            row(False, True, conf=0.5)]                          # false alarm
    assert M.asked(rows[0], 0.7) and not M.asked(rows[1], 0.7)
    assert M.resolution_accuracy(rows, 0.7) == 1.0
    assert M.resolution_accuracy(rows, 0.0) == 0.5     # never asks -> first row wrong
    assert M.questions_per_ambiguous(rows, 0.7) == 0.5
    assert M.unnecessary_question_rate(rows, 0.7) == 1.0


def test_vote_entropy():
    assert M.vote_entropy({"i1": 0.5, "i2": 0.5}) == 1.0
    assert M.vote_entropy({"i1": 1.0, "i2": 0.0}) == 0.0
    assert M.vote_entropy({"i1": 0.5, "i2": 0.5, "unclear": 0.9}) == 1.0


def test_sus_and_tlx_known_values():
    assert M.sus_score([5, 1, 5, 1, 5, 1, 5, 1, 5, 1]) == 100.0
    assert M.sus_score([3] * 10) == 50.0
    assert M.tlx_raw([10, 20, 30, 40, 50, 60]) == 35


def test_bootstrap_ci_contains_estimate_and_is_reproducible():
    rows = [row(True, True)] * 7 + [row(True, False)] * 3
    lo, hi = M.bootstrap_ci(rows, M.detection_f1, n=300, seed=1)
    assert lo <= M.detection_f1(rows) <= hi
    assert (lo, hi) == M.bootstrap_ci(rows, M.detection_f1, n=300, seed=1)


def test_calibration_and_pearson():
    rows = [row(True, True, conf=0.2, auto=False), row(True, True, conf=0.95, auto=True)]
    cal = M.calibration(rows)
    assert cal["n"] == 2 and cal["brier"] < 0.1
    assert abs(M.pearson([1, 2, 3], [2, 4, 6]) - 1.0) < 1e-9
    assert M.pearson([1, 1, 1], [1, 2, 3]) is None


def test_per_type_recall():
    rows = [row(True, True, types=["lexical"], gtypes=["lexical"]), row(True, False, gtypes=["lexical"])]
    out = M.per_type_recall(rows)
    assert out["lexical"]["n"] == 2 and out["lexical"]["recall"] == 0.5
