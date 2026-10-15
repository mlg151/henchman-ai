"""Tests for BUG-015: missing bounds validation on numeric config fields.

Fields like max_tokens, shell_timeout, compaction_threshold, etc. lack
Pydantic ge=/le= constraints, so zero or negative values pass validation.
"""

from __future__ import annotations

import pytest

from henchman.config.schema import (
    AgentSettings,
    ContextSettings,
    RagSettings,
    ToolSettings,
)


class TestBug015NumericBounds:
    """Numeric config fields should reject invalid values."""

    # --- ToolSettings ---

    def test_shell_timeout_must_be_positive(self) -> None:
        """shell_timeout must be >= 1."""
        with pytest.raises(ValueError):
            ToolSettings(shell_timeout=0)
        with pytest.raises(ValueError):
            ToolSettings(shell_timeout=-1)

    # --- ContextSettings ---

    def test_max_tokens_must_be_positive(self) -> None:
        """max_tokens must be >= 1."""
        with pytest.raises(ValueError):
            ContextSettings(max_tokens=0)
        with pytest.raises(ValueError):
            ContextSettings(max_tokens=-100)

    def test_compaction_threshold_bounds(self) -> None:
        """compaction_threshold must be between 0 and 1."""
        with pytest.raises(ValueError):
            ContextSettings(compaction_threshold=-0.1)
        with pytest.raises(ValueError):
            ContextSettings(compaction_threshold=1.5)

    def test_importance_threshold_bounds(self) -> None:
        """importance_threshold must be between 0 and 1."""
        with pytest.raises(ValueError):
            ContextSettings(importance_threshold=-0.1)
        with pytest.raises(ValueError):
            ContextSettings(importance_threshold=1.5)

    def test_cluster_similarity_threshold_bounds(self) -> None:
        """cluster_similarity_threshold must be between 0 and 1."""
        with pytest.raises(ValueError):
            ContextSettings(cluster_similarity_threshold=-0.1)
        with pytest.raises(ValueError):
            ContextSettings(cluster_similarity_threshold=1.5)

    # --- AgentSettings ---

    def test_max_delegation_depth_must_be_positive(self) -> None:
        """max_delegation_depth must be >= 1."""
        with pytest.raises(ValueError):
            AgentSettings(max_delegation_depth=0)
        with pytest.raises(ValueError):
            AgentSettings(max_delegation_depth=-1)

    def test_max_delegation_turns_must_be_positive(self) -> None:
        """max_delegation_turns must be >= 1."""
        with pytest.raises(ValueError):
            AgentSettings(max_delegation_turns=0)
        with pytest.raises(ValueError):
            AgentSettings(max_delegation_turns=-1)

    def test_shared_context_max_tokens_must_be_positive(self) -> None:
        """shared_context_max_tokens must be >= 1."""
        with pytest.raises(ValueError):
            AgentSettings(shared_context_max_tokens=0)
        with pytest.raises(ValueError):
            AgentSettings(shared_context_max_tokens=-1)

    # --- RagSettings ---

    def test_chunk_size_must_be_positive(self) -> None:
        """chunk_size must be >= 1."""
        with pytest.raises(ValueError):
            RagSettings(chunk_size=0)
        with pytest.raises(ValueError):
            RagSettings(chunk_size=-100)

    def test_chunk_overlap_must_not_be_negative(self) -> None:
        """chunk_overlap must be >= 0."""
        with pytest.raises(ValueError):
            RagSettings(chunk_overlap=-1)
        with pytest.raises(ValueError):
            RagSettings(chunk_overlap=-100)

    def test_top_k_must_be_positive(self) -> None:
        """top_k must be >= 1."""
        with pytest.raises(ValueError):
            RagSettings(top_k=0)
        with pytest.raises(ValueError):
            RagSettings(top_k=-1)

    # --- Valid values should still pass ---

    def test_valid_bounds_pass(self) -> None:
        """Boundary values (1, 0 for non-negative) should still pass."""
        ToolSettings(shell_timeout=1)
        ContextSettings(max_tokens=1)
        ContextSettings(compaction_threshold=0.0)
        ContextSettings(compaction_threshold=1.0)
        ContextSettings(importance_threshold=0.0)
        ContextSettings(importance_threshold=1.0)
        AgentSettings(max_delegation_depth=1)
        AgentSettings(max_delegation_turns=1)
        AgentSettings(shared_context_max_tokens=1)
        RagSettings(chunk_size=1, chunk_overlap=0)
        RagSettings(chunk_overlap=0)
        RagSettings(top_k=1)
