# Demo script (about 3 minutes)

1. **Problem (20 s).** "Assistants guess silently. Lexi asks, and shows why."
2. **Ambiguous sentence (60 s).** Type: "Alice told Maya that she failed the exam." Show the highlighted
   span, the two meanings with probabilities, the vote split and entropy. Answer the question with a
   quick-reply button and show the resolution.
3. **Control (30 s).** Move the threshold slider and re-analyze. Show that Lexi asks less or more.
   Override a meaning by hand.
4. **Clean sentence (20 s).** "Please send the finalized PDF invoice to accounting by Friday at 5 PM."
   No question is asked.
5. **Baseline (20 s).** Turn on compare. The baseline silently picks one meaning.
6. **Evidence (40 s).** Open the dashboard on the TEST split: F1, false-positive rate,
   resolution accuracy with confidence intervals, questions asked, failure cases, and the exploratory study.
7. **Honest limits (10 s).** Small dataset, exploratory study, the meaning map is a visualizer and not a steerable embedding.

Only show numbers that are on the dashboard.
