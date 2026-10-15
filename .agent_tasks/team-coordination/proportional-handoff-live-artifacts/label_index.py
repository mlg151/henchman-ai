"""Canonical label indexing built on the project normalizer."""

import normalization


def unique_labels(values: list[str]) -> list[str]:
    """Return nonempty canonical labels once each, in first-seen order.

    Each raw value is passed exactly once to ``normalization.normalize_label``,
    looked up as a module attribute at call time. Empty canonical results are
    dropped; duplicates are removed by canonical value. The input list is
    never mutated.

    Args:
        values: Raw label strings in encounter order.

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
