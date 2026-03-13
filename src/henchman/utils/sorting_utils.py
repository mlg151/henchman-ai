"""Sorting utility functions."""



def sort_by_importance(
    item_count: int,
    importance_scores: dict[int, float],
) -> list[int]:
    """Sort indices by importance scores (descending).

    Args:
        item_count: Number of items to sort.
        importance_scores: Importance scores for each item.

    Returns:
        List of indices sorted by importance (descending).
    """
    indices = list(range(item_count))
    indices.sort(key=lambda idx: importance_scores.get(idx, 0.0), reverse=True)
    return indices
