"""Canonical label indexing built on the project's existing normalizer."""

import normalization


def unique_labels(values: list[str]) -> list[str]:
    """Return nonempty canonical labels once each, in first-seen order.

    Each input element is canonicalized with ``normalization.normalize_label``
    exactly once, at call time. Empty canonical results are skipped, and
    duplicates are collapsed on the canonical value, keeping the first-seen
    order. The input list is never mutated.

    Args:
        values: Raw label strings to canonicalize.

    Returns:
        Canonical labels, deduplicated in first-seen order.
    """
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        canonical = normalization.normalize_label(value)
        if not canonical or canonical in seen:
            continue
        seen.add(canonical)
        result.append(canonical)
    return result
