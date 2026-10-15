"""Configuration dataclass for the Agent."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class AgentConfig:
    """Groups Agent initialization parameters into a single object.

    Attributes:
        system_prompt: Optional system prompt for the agent.
        max_tokens: Maximum tokens for context. 0 means auto-detect from model.
        context_window: Hard requested capacity including request overhead and output;
            None preserves legacy model-derived behavior.
        model: Model name for determining context limits.
        summarize_dropped: Whether to summarize dropped messages during compaction.
        base_tool_iterations: Base limit for tool call iterations per turn.
        max_protected_ratio: Max ratio of context to protect from compaction.
        intelligent_context: Whether to use intelligent context management.
        importance_threshold: Minimum importance score to preserve a message.
        cluster_similarity_threshold: Similarity threshold for clustering messages.
        adaptive_compression: Whether to use adaptive compression techniques.
    """

    system_prompt: str = ""
    max_tokens: int = 0
    model: str | None = None
    summarize_dropped: bool = True
    base_tool_iterations: int = 25
    max_protected_ratio: float = 0.3
    intelligent_context: bool = False
    importance_threshold: float = 0.5
    cluster_similarity_threshold: float = 0.7
    adaptive_compression: bool = True
    context_window: int | None = None
