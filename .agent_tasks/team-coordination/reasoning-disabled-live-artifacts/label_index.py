"""Canonical label indexing built on the project normalizer."""

import normalization


def unique_labels(values: list[str]) -> list[str]:
    """Return nonempty canonical labels once each, in first-seen order.

    Every input element is normalized exactly once via
    ``normalization.normalize_label``, called with the original element in
    list order. Elements whose canonical form is empty are dropped. The
    input list is never mutated.

    Args:
        values: Raw label strings, processed in order.

    Returns:
        Canonical labels, deduplicated in first-seen order.
    """
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        canonical = normalization.normalize_label(value)
        if not canonical or canonical in seen:
            continue
        seen.add(canonical)
        result.append(canonical)
    return result
