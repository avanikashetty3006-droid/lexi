# Lexi: report (Resurrect 2026, problem 6, with problem 3 and a lite problem 5)

> Rule for this file: every number must be copied from `evaluation/results/*_summary.json`
> or the dashboard. Do not type numbers from memory. Anything marked TODO is not done yet.

## 1. What Lexi is
A chat assistant that asks instead of guessing when a sentence is ambiguous, and shows why.
Pipeline: detect (temperature 0) -> 5 votes (temperature 0.8) -> embed and cluster the meanings ->
decide by a user-tunable threshold -> clarify -> resolve. No model is trained from scratch.

## 2. Definitions (problem 6 asks for these)
**Ambiguous.** A sentence, read in its conversation context, that has two or more
*plausible, meaningfully different* readings, where acting on the wrong one would change what a
helpful assistant should do. Types: lexical, syntactic, semantic (scope), contextual (underspecified), anaphoric.

**Not ambiguous (clean).** One reading is clearly most natural for a normal reader, even if a
dictionary lists other senses ("She deposited the check at the bank"). Vague or general sentences are
not ambiguous unless a missing detail changes the action. Our dataset includes *hard negatives*
(sentences that look ambiguous but are not).

**Correct resolution.** After the user's clarification answer (or from context alone), the meaning
Lexi commits to is the same as the gold meaning (`gold_resolved`).

## 3. What "better" means (success criteria, decided before running)
1. Detection F1 higher than the silent-guess baseline.
2. Low false-positive rate on clean rows, including hard negatives.
3. Higher resolution accuracy than the baseline, with few unnecessary questions.
4. Confidence is meaningful: higher confidence goes with a more often correct automatic guess.
5. In a small study, effort and trust are equal or better than the baseline.

## 4. Metrics, why each fits, and its limits
| Metric | What it measures | Why we use it | Limits |
|---|---|---|---|
| Detection precision, recall, F1 | Flagging ambiguous vs clean rows | Standard for a yes/no detector; F1 balances missed ambiguity and false alarms | Depends on our labels, which are subjective (see 6) |
| False-positive rate on clean rows | How often Lexi cries wolf | Directly tied to annoying the user | Small clean set, wide interval |
| Resolution accuracy | Final meaning equals gold meaning | The point of the system | Automatic matching is approximate; we hand-check (see 5) |
| Questions per ambiguous row, unnecessary-question rate | Cost to the user | Asking more must pay off | Counts questions, not how annoying they are |
| Brier score and confidence bins | Whether vote confidence predicts correctness | Needed to justify "confidence" | Few rows per bin |
| Semantic entropy vs vote entropy (Pearson r) | Whether semantic entropy adds information | Checks that the entropy number is not redundant | Interpretations per sentence are only 2-4 |
| Latency p50 and p95 | Speed | Target: under about 6 s | Depends on provider and network |
| SUS, raw NASA-TLX, trust (1-7), task success | Usability, effort, trust | Standard scales | Tiny sample, exploratory only |

Uncertainty: 95% percentile bootstrap over rows (1000 resamples, seed 0).

## 5. Method (reproducible)
- Dataset: `evaluation/data/dataset.jsonl` (TODO: size, clean share, multi-turn count; copy from `python evaluation\validate_dataset.py`). Split into dev and test. The threshold is tuned on **dev only**; test is run once.
- Baseline: one prompt that silently picks a meaning (`POST /baseline`), same model, same rows, never asks.
- Same settings for both: provider and model recorded in each summary file; temperature 0 (detect, baseline), 0.8 (votes), 5 votes, seed 42.
- Meaning matching: a system answer is correct if its nearest gold interpretation (MiniLM cosine) is `gold_resolved`. All gold-ambiguous rows are exported to `results/*_review.csv`; TODO: two people fill the human columns, and the scripts re-score with `--rescore`. Report how many cells changed.
- Commands: see the README section "Run the evaluation".

## 6. Label quality
TODO: a second person labels at least 50 rows blind. Report Cohen's kappa for ambiguous vs clean, and list disagreements.
Disputed example: "The trophy didn't fit in the suitcase because it was too big." The pronoun "it" is grammatically open, but every reasonable reader resolves it to the trophy, because a suitcase cannot fail to hold something by being too big. Under our definition (a reasonable reader could pick 2+ meanings given the context) it is therefore labelled **clean** (row `hn01`, dev split). It also serves as a hard negative: a system that flags it counts as a false positive. Team confirmation: [TO FILL: names and date once the team agrees].

## 7. Results
TODO. Paste from the dashboard: table of Lexi vs baseline on TEST with confidence intervals, per-type recall, calibration, latency.
Include failure cases and say what went wrong, with examples.

## 8. Problem 3 (human-agent interaction)
Interaction features: highlighted span, interpretations with probabilities, vote split and entropy, override, threshold slider, baseline compare, thumbs on questions. User actions are logged with POST /feedback.
Study: within-subjects, see `evaluation/study/protocol.md`. TODO: results. Call them exploratory (n = TODO).

## 9. Problem 5 (lite)
Lexi embeds the candidate meanings with all-MiniLM-L6-v2 and draws a 2D PCA "meaning map". This is a **visualizer, not a steerable embedding model**; we do not claim to solve problem 5.
Faithfulness: with 3 points a 2D projection is exact, so it proves nothing. TODO: report explained variance for 4-point cases and the correlation between 2D distances and cosine distances over many sentences. The PCA axes are recomputed per sentence, so positions cannot be compared across sentences.
Cosine clustering threshold: TODO say how it was chosen (and that it was not chosen on test rows).

## 10. Limitations
- Gemini and Groq ignore our seed; runs can vary slightly. We pin the model name and report it.
- If the backup provider answers after a rate limit, a run can mix two models; check `provider` in the logs.
- Small dataset and small study; results are indicative, not definitive.
