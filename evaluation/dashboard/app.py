r"""Lexi evaluation dashboard.   Run:  streamlit run evaluation\dashboard\app.py"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

EVAL_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(EVAL_DIR))
import metrics as M  # noqa: E402

RES = EVAL_DIR / "results"
st.set_page_config(page_title="Lexi evaluation", layout="wide")
st.title("Lexi evaluation")
st.caption("Every number here is read from files in evaluation/results (computed, never typed in). "
           "Dry-run files are ignored.")


def load(name: str):
    p = RES / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def pct(x):
    return "n/a" if x is None else f"{x:.1%}"


def ci(c):
    return "" if not c or c[0] is None else f" [{c[0]:.1%}, {c[1]:.1%}]"


split = st.sidebar.radio("Split", ["test", "dev"], help="Report TEST numbers. DEV is for tuning only.")
lexi = load(f"{split}_lexi_summary.json")
base = load(f"{split}_baseline_summary.json")

st.header(f"1. Lexi vs silent-guess baseline ({split})")
if not lexi or not base:
    st.info("Run run_eval.py and baseline_eval.py for this split first.")
else:
    table = pd.DataFrame([
        {"Metric": "Detection F1", "Baseline": pct(base["f1"]) + ci(base["f1_ci95"]), "Lexi": pct(lexi["f1"]) + ci(lexi["f1_ci95"])},
        {"Metric": "False-positive rate (clean rows)", "Baseline": pct(base["false_positive_rate"]) + ci(base["fpr_ci95"]),
         "Lexi": pct(lexi["false_positive_rate"]) + ci(lexi["fpr_ci95"])},
        {"Metric": "Resolution accuracy (ambiguous rows)", "Baseline": pct(base["resolution_accuracy"]) + ci(base["resolution_accuracy_ci95"]),
         "Lexi": pct(lexi["resolution_accuracy"]) + ci(lexi["resolution_accuracy_ci95"])},
        {"Metric": "Questions per ambiguous row", "Baseline": "0 (never asks)", "Lexi": pct(lexi["questions_per_ambiguous_row"])},
        {"Metric": "Unnecessary questions (clean rows)", "Baseline": "0 (never asks)", "Lexi": pct(lexi["unnecessary_question_rate_on_clean"])},
    ])
    st.table(table.set_index("Metric"))
    st.caption(f"n={lexi['n_rows']} rows ({lexi['n_ambiguous']} ambiguous, {lexi['n_clean']} clean). "
               f"Threshold {lexi['threshold']}. 95% CIs are percentile bootstrap over rows. "
               f"Errors: Lexi {lexi['n_errors']}, baseline {base['n_errors']}. Meaning matcher: {lexi['meta']['matcher']} "
               f"(human-reviewed cells: {lexi['meta']['human_review_cells_applied']}).")

    st.header("2. Failure analysis by ambiguity type (Lexi)")
    pt = pd.DataFrame(lexi["per_type"]).T
    st.dataframe(pt)

    st.header("3. Is the confidence meaningful?")
    cal = lexi["calibration"]
    st.write(f"Brier score of vote confidence vs. correctness of the automatic guess: "
             f"**{cal['brier']:.3f}**" if cal["brier"] is not None else "Not enough rows.")
    st.dataframe(pd.DataFrame(cal["bins"]))
    r = lexi["entropy_vs_vote_entropy_pearson"]
    st.write("Pearson correlation of semantic entropy with plain vote entropy: "
             + ("n/a" if r is None else f"**{r:.2f}**")
             + " (a value near 1 means semantic entropy adds little beyond the vote split).")

    st.header("4. Latency")
    st.write(f"p50 {lexi['latency_ms_p50']} ms, p95 {lexi['latency_ms_p95']} ms (target: under about 6000 ms).")

    raw = RES / f"{split}_lexi_raw.jsonl"
    if raw.exists():
        rows = [json.loads(x) for x in raw.read_text(encoding="utf-8").splitlines() if x.strip()]
        fails = [x for x in rows if x["gold_ambiguous"] != x["pred_ambiguous"] or x.get("error")]
        st.header("5. Failure cases (missed ambiguity or false alarm)")
        if fails:
            st.dataframe(pd.DataFrame(fails).reindex(
                columns=["id", "sentence", "gold_ambiguous", "pred_ambiguous", "confidence", "error"]))
        else:
            st.success("No missed ambiguities or false alarms on this split.")

st.header("6. Threshold tuning (DEV only)")
sweep = RES / "threshold_sweep.csv"
if sweep.exists():
    df = pd.read_csv(sweep)
    st.line_chart(df.set_index("threshold")[["resolution_accuracy", "asks_per_row"]])
    best = load("best_threshold.json")
    st.write(f"Chosen threshold: **{best['threshold']}** (tuned on dev, lambda={best['lambda']}).")
else:
    st.info("Run tune_threshold.py after the dev run.")

st.header("7. User study (exploratory)")
resp = EVAL_DIR / "study" / "responses.csv"
if resp.exists() and resp.stat().st_size > 0:
    df = pd.read_csv(resp)
    if len(df):
        sus_cols = [f"sus_{i}" for i in range(1, 11)]
        tlx_cols = ["tlx_mental", "tlx_physical", "tlx_temporal", "tlx_performance", "tlx_effort", "tlx_frustration"]
        df["SUS"] = df[sus_cols].apply(lambda r: M.sus_score([int(x) for x in r]), axis=1)
        df["TLX"] = df[tlx_cols].apply(lambda r: M.tlx_raw([float(x) for x in r]), axis=1)
        piv = df.pivot_table(index="participant_id", columns="condition", values=["SUS", "TLX", "trust_1_7", "tasks_correct", "time_s"])
        st.dataframe(piv)
        for metric, better in (("SUS", "higher"), ("TLX", "lower"), ("trust_1_7", "higher"), ("tasks_correct", "higher")):
            try:
                d = (piv[metric]["lexi"] - piv[metric]["baseline"]).dropna().tolist()
            except KeyError:
                continue
            res = M.paired_bootstrap(d)
            st.write(f"{metric} (Lexi - baseline, {better} is better): mean diff {res['mean_diff']:.2f}, "
                     f"95% bootstrap CI [{res['ci95'][0]:.2f}, {res['ci95'][1]:.2f}], n={res['n']} participants. "
                     "Small sample: treat as exploratory.")
    else:
        st.info("No study responses yet.")
else:
    st.info("No study responses yet (evaluation/study/responses.csv).")
