"""First-seen deduplication of canonical project labels."""

import normalization


def unique_labels(values: list[str]) -> list[str]:
    """Return nonempty canonical labels once each, in first-seen order.

    Each input is passed exactly once through ``normalization.normalize_label``
    (casefolding and whitespace collapsing included). Empty canonical results
    are dropped and duplicates removed; the input list is not modified.

    Args:
        values: Raw label strings, in presentation order.

    Returns:
        Canonical labels with empty results dropped and duplicates removed,
        preserving first-seen order.
    """
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        canonical = normalization.normalize_label(value)
        if canonical and canonical not in seen:
            seen.add(canonical)
            result.append(canonical)
    return result
