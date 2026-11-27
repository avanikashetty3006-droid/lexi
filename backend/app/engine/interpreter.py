from __future__ import annotations

from app.engine.detector import RawInterpretationItem
from app.schemas import Interpretation


def build_interpretations(
    raw_items: list[RawInterpretationItem],
    ambiguous: bool,
    vote_split: dict[str, float],
) -> list[Interpretation]:
    """Attach probabilities to candidate interpretations while honoring clean-sentence invariants."""
    if not ambiguous:
        meaning = raw_items[0].meaning if raw_items else ""
        return [Interpretation(id="i1", meaning=meaning, probability=1.0)]

    non_unclear_total = sum(
        prob for key, prob in vote_split.items() if key != "unclear"
    )
    n_items = len(raw_items)

    results: list[Interpretation] = []
    for item in raw_items:
        if non_unclear_total > 0:
            prob = round(vote_split.get(item.id, 0.0) / non_unclear_total, 4)
        else:
            prob = round(1.0 / n_items, 4)
        results.append(Interpretation(id=item.id, meaning=item.meaning, probability=prob))
    return results
