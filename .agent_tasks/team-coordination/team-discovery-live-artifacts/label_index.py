"""Deduplicated canonical label collection built on the project normalizer."""

import normalization


def unique_labels(values: list[str]) -> list[str]:
    """Return nonempty canonical labels once each, in first-seen order.

    Every input value is passed through ``normalization.normalize_label``
    exactly once; empty canonical results are dropped and only the first
    occurrence of each distinct canonical value is kept. The input list is
    never modified.

    Args:
        values: Raw label strings in first-seen order.

    Returns:
        Canonical labels, deduplicated, in first-seen order.
    """
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        canonical = normalization.normalize_label(value)
        if canonical and canonical not in seen:
            seen.add(canonical)
            result.append(canonical)
    return result
