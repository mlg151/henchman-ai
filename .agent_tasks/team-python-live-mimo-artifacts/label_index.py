"""First-seen-order index of canonical project labels."""

import normalization


def unique_labels(values: list[str]) -> list[str]:
    """Return nonempty canonical labels once each, in first-seen order.

    Every raw input is passed exactly once, in input order, to
    ``normalization.normalize_label``. Deduplication is performed on the
    canonical result. The input list is never mutated.

    Args:
        values: Raw label strings in first-seen order.

    Returns:
        Nonempty canonical labels, deduplicated, in first-seen order.
    """
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        canonical = normalization.normalize_label(value)
        if canonical and canonical not in seen:
            seen.add(canonical)
            result.append(canonical)
    return result
