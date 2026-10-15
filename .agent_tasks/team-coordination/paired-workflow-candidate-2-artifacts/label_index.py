import normalization


def unique_labels(values: list[str]) -> list[str]:
    """Return nonempty canonical labels once each, in first-seen order."""
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        canonical = normalization.normalize_label(value)
        if canonical and canonical not in seen:
            seen.add(canonical)
            result.append(canonical)
    return result
