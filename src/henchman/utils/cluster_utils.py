"""Utility functions for cluster operations.

Extracted to eliminate duplicate code between IntelligentContextManager
and MessageCompactor.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from henchman.utils.intelligent_context import IntelligentContextConfig


class ClusterUtils:
    """Utility class for cluster operations."""

    @staticmethod
    def calculate_cluster_importance(
        clusters: list[list[int]],
        importance_scores: dict[int, float],
        config: "IntelligentContextConfig",
    ) -> dict[int, float]:
        """Calculate importance score for each cluster.

        Args:
            clusters: List of message clusters.
            importance_scores: Importance scores for individual messages.
            config: Configuration for cluster importance calculation.

        Returns:
            Dictionary mapping cluster indices to importance scores.
        """
        cluster_importance: dict[int, float] = {}

        for cluster_idx, cluster in enumerate(clusters):
            if not cluster:
                cluster_importance[cluster_idx] = 0.0
                continue

            total_score = 0.0
            valid_scores = 0

            for msg_idx in cluster:
                if msg_idx in importance_scores:
                    total_score += importance_scores[msg_idx]
                    valid_scores += 1

            avg_score = total_score / valid_scores if valid_scores > 0 else 0.0

            # Boost score for larger clusters (more context)
            size_factor = min(len(cluster) / 10.0, 1.0) * config.cluster_size_boost_factor
            cluster_score = min(1.0, avg_score + size_factor)

            cluster_importance[cluster_idx] = cluster_score

        return cluster_importance
