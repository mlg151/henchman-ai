"""First-seen unique canonical labels built on the project normalizer."""

import normalization


def unique_labels(values: list[str]) -> list[str]:
    """Return nonempty canonical labels once each, in first-seen order.

    Every input value is canonicalized exactly once via
    ``normalization.normalize_label``. Canonical results that are empty
    strings are dropped. The input list is not mutated.

    Args:
        values: Raw label strings in the order they were seen.

    Returns:
        Canonical labels, deduplicated, preserving first-seen order.
    """
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        canonical = normalization.normalize_label(value)
        if canonical and canonical not in seen:
            seen.add(canonical)
            result.append(canonical)
    return result
