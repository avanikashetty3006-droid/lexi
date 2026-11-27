# User study protocol (exploratory)

**Question.** Does asking a clarifying question and showing why (Lexi) give equal or better
effort and trust than a chat that silently picks a meaning (baseline)?

**Design.** Within-subjects: each of 6-10 participants uses BOTH versions. Alternate which
version comes first (order = lexi_first / baseline_first) to cancel practice effects.

**Tasks.** 6 short tasks per version (12 total). Each task gives the participant a goal that
needs a sentence with a hidden intended meaning, for example "Ask the assistant to schedule a
review for the Friday you mean". Use different sentences in each version. Include 2 clean tasks
per version, so we can see unnecessary questions.

**Per participant per version, record (one row in responses.csv):**
- `tasks_correct` / `tasks_total`: did the final meaning match the participant's intended meaning.
- `time_s`: total time on the tasks.
- `sus_1..sus_10`: System Usability Scale items, 1-5 (scored with the standard formula).
- `tlx_*`: six NASA-TLX subscales, 0-100 (raw TLX = mean of the six). Lower is less effort.
- `trust_1_7`: "I trusted the assistant's understanding of my sentences", 1 = not at all, 7 = completely.
- `preferred` (once, at the end): lexi / baseline / none.

**Analysis.** Per-participant difference (Lexi minus baseline), mean with a 95% bootstrap CI
(evaluation/metrics.py: paired_bootstrap). With 6-10 people this is **exploratory**: report the
numbers and intervals, do not claim statistical significance.

**Limits to state in the report.** Tiny sample; participants are classmates, not representative;
tasks are written by us; novelty effects; one session per person.

**Ethics.** Get verbal consent, no personal data in responses.csv (use P01, P02, ...),
participants may stop at any time.
