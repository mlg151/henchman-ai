"""Core Agent implementation for orchestrating LLM interactions."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from henchman.core.agent_config import AgentConfig
from henchman.core.agent_stall import StallDetector
from henchman.core.agent_streaming import (
    StreamContext,
    StreamState,
    generate_stream_events,
)
from henchman.core.events import AgentEvent, EventType
from henchman.core.turn import TurnState
from henchman.providers.base import Message, ModelProvider
from henchman.tools.registry import ToolRegistry
from henchman.utils.tokens import TokenCounter, get_model_limit
from henchman.utils.validation import (
    is_valid_message_sequence,
    repair_message_sequence,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from henchman.agents.identity import AgentIdentity

logger = logging.getLogger(__name__)

# Re-export for backward compatibility
StreamingAccumulationState = StreamState

# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

DEFAULT_MAX_TOKENS = 8000
DEFAULT_TOKEN_RATIO = 0.85
LOG_TRUNCATE_LENGTH = 100

_CONFIG_FIELDS = frozenset({
    "system_prompt", "model", "base_tool_iterations",
    "intelligent_context", "importance_threshold",
    "cluster_similarity_threshold", "adaptive_compression",
    "max_protected_ratio", "summarize_dropped",
})

_STALL_FIELDS: dict[str, str] = {
    "_stall_nudge_count": "nudge_count",
    "_stall_failure": "failure",
    "stall_detection_enabled": "enabled",
    "_max_stall_nudges": "_max_nudges",
}

_INSTANCE_ALIASES: dict[str, str] = {
    "history": "messages",
    "tools": "tool_registry",
    "max_tokens": "_max_tokens",
}


# ---------------------------------------------------------------------------
# Module-level helpers (avoids Feature Envy + reduces method count)
# ---------------------------------------------------------------------------


def _resolve_max_tokens(configured: int, model: str | None) -> int:
    """Resolve the effective max_tokens value.

    Args:
        configured: User-specified max tokens. 0 means auto-detect.
        model: Model name for looking up context limits.

    Returns:
        Effective max token limit.
    """
    if configured > 0:
        return configured
    if model:
        return int(get_model_limit(model) * DEFAULT_TOKEN_RATIO)
    return DEFAULT_MAX_TOKENS


def _build_compactor(config: AgentConfig, max_tokens: int) -> Any:
    """Build the appropriate compactor instance.

    Args:
        config: Agent configuration.
        max_tokens: Maximum token limit.

    Returns:
        A ContextCompactor or IntelligentContextManager instance.
    """
    from henchman.utils.compaction import ContextCompactor  # noqa: PLC0415
    from henchman.utils.intelligent_context import IntelligentContextManager  # noqa: PLC0415

    if config.intelligent_context:
        return IntelligentContextManager(
            max_tokens=max_tokens,
            max_protected_ratio=config.max_protected_ratio,
            importance_threshold=config.importance_threshold,
            cluster_similarity_threshold=config.cluster_similarity_threshold,
            adaptive_compression=config.adaptive_compression,
        )
    return ContextCompactor(
        max_tokens=max_tokens,
        max_protected_ratio=config.max_protected_ratio,
    )


def _build_outer_finished_event(
    state: StreamState | None,
    source_agent: str | None,
) -> AgentEvent:
    """Build the outer FINISHED event emitted at the end of run().

    Args:
        state: Last stream state, or None.
        source_agent: Agent identity ID for the event.

    Returns:
        AgentEvent with finish reason and optional usage data.
    """
    fr = state.finish_reason if state else None
    finish_data: str | dict[str, Any] = fr.value if fr else "Agent completed execution"
    if state and state.usage:
        finish_data = {"finish_reason": finish_data, "usage": state.usage}
    return AgentEvent(type=EventType.FINISHED, data=finish_data, source_agent=source_agent)


class Agent:
    """Orchestrates interactions between user, LLM, and tools."""

    DEFAULT_MAX_TOKENS = DEFAULT_MAX_TOKENS
    DEFAULT_TOKEN_RATIO = DEFAULT_TOKEN_RATIO

    def __init__(
        self: Agent,
        provider: ModelProvider,
        *,
        tool_registry: ToolRegistry | None = None,
        config: AgentConfig | None = None,
        identity: AgentIdentity | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the Agent.

        Args:
            provider: The model provider to use for LLM interactions.
            tool_registry: Registry of available tools. Creates empty one if None.
            config: Agent configuration. If None, built from **kwargs.
            identity: Optional identity of the agent.
            **kwargs: Backward-compatible config fields (system_prompt, max_tokens, etc.).
        """
        self.provider = provider
        self.tool_registry = tool_registry if tool_registry is not None else ToolRegistry()
        self.identity = identity
        self._config = config if config is not None else AgentConfig(**kwargs)
        self._stall = StallDetector()
        model = self._config.model
        if not model and hasattr(provider, "default_model"):
            model = provider.default_model
        self._config.model = model
        self._max_tokens = _resolve_max_tokens(self._config.max_tokens, model)
        self.messages: list[Message] = []
        self.turn = TurnState()
        self.unlimited_mode = False
        self._turn_number = 0
        self._last_stream_state: StreamState | None = None
        if self._config.system_prompt:
            self.messages.append(Message(role="system", content=self._config.system_prompt))

    # -- dynamic attribute delegation ----------------------------------------

    def __getattr__(self: Agent, name: str) -> Any:
        """Delegate attribute access to _config, _stall, or instance aliases.

        Provides backward-compatible access to configuration fields,
        stall detector state, and convenience aliases without repetitive
        property definitions.
        """
        if name in _CONFIG_FIELDS:
            return getattr(self._config, name)
        if name in _STALL_FIELDS:
            return getattr(self._stall, _STALL_FIELDS[name])
        if name in _INSTANCE_ALIASES:
            return object.__getattribute__(self, _INSTANCE_ALIASES[name])
        msg = f"'{type(self).__name__}' object has no attribute '{name}'"
        raise AttributeError(msg)

    def __setattr__(self: Agent, name: str, value: Any) -> None:
        """Delegate attribute writes to _config, _stall, or instance aliases."""
        if name in _CONFIG_FIELDS and "_config" in self.__dict__:
            setattr(self._config, name, value)
        elif name in _STALL_FIELDS and "_stall" in self.__dict__:
            setattr(self._stall, _STALL_FIELDS[name], value)
        elif name in _INSTANCE_ALIASES and _INSTANCE_ALIASES[name] in self.__dict__:
            self.__dict__[_INSTANCE_ALIASES[name]] = value
        else:
            super().__setattr__(name, value)

    async def _check_for_stalling(
        self: Agent,
        content: str,
        *,
        had_tool_calls: bool,
    ) -> str | None:
        """Backward-compat: Check for stalling patterns in response."""
        return await self._stall.check(content, had_tool_calls=had_tool_calls)

    async def _apply_simple_compaction(self: Agent, protected_count: int = 0) -> bool:
        """Apply context compaction directly, bypassing token check.

        Args:
            protected_count: Number of messages to protect from compaction.
        """
        compactor = _build_compactor(self._config, self._max_tokens)

        # Calculate protect_from_index based on protected_count to match test expectations
        protect_idx = max(0, len(self.messages) - protected_count) if protected_count > 0 else self.turn.start_index  # noqa: E501

        self.messages = compactor.compact(self.messages, protect_from_index=protect_idx)
        if not is_valid_message_sequence(self.messages):
            self.messages = repair_message_sequence(self.messages)

        self.turn.start_index = max(0, len(self.messages) - protected_count)
        return True

    async def _apply_compaction_if_needed(self: Agent) -> bool:
        """Backward-compat alias for :meth:`_compact_if_needed`."""
        return await self._compact_if_needed()

    # -- public API ----------------------------------------------------------

    def clear_history(self: Agent) -> None:
        """Clear the conversation history, keeping the system prompt."""
        self.messages = [m for m in self.messages if m.role == "system"]

    def get_messages_for_api(self: Agent) -> list[Message]:
        """Get messages for the API, with compaction if needed.

        Returns:
            List of messages, potentially compacted to fit within max_tokens.
        """
        compactor = _build_compactor(self._config, self._max_tokens)
        result: list[Message] = compactor.compact(
            self.messages, protect_from_index=self.turn.start_index,
        )
        return result

    def submit_tool_result(self: Agent, tool_call_id: str, result: str) -> None:
        """Submit a tool result to continue the conversation."""
        self.messages.append(
            Message(role="tool", content=result, tool_call_id=tool_call_id),
        )

    async def run(self: Agent, user_input: str) -> AsyncIterator[AgentEvent]:
        """Run the agent with user input.

        Args:
            user_input: The user message to process.

        Yields:
            AgentEvent instances as the agent processes the input.
        """
        logger.debug("Agent.run: Starting with input: %s", user_input[:LOG_TRUNCATE_LENGTH])
        self._turn_number += 1
        self.turn.reset(new_start_index=len(self.messages))
        self.messages.append(Message(role="user", content=user_input))
        async for event in self._stream_with_stall_loop():
            yield event
        source = self.identity.id if self.identity else None
        yield _build_outer_finished_event(self._last_stream_state, source)

    async def continue_with_tool_results(self: Agent) -> AsyncIterator[AgentEvent]:
        """Continue execution after tool results have been submitted.

        Includes the same stall-detection loop used by :meth:`run` so that
        agents which narrate intent without acting are nudged to call tools.
        """
        async for event in self._stream_with_stall_loop():
            yield event

    # -- private helpers -----------------------------------------------------

    def _emit(self: Agent, event_type: EventType, data: Any = None) -> AgentEvent:
        """Create an AgentEvent with the correct source_agent."""
        return AgentEvent(
            type=event_type,
            data=data,
            source_agent=self.identity.id if self.identity else None,
        )

    async def _compact_if_needed(self: Agent) -> bool:
        """Apply compaction to messages if they exceed the token limit.

        Returns:
            True if compaction was applied, False otherwise.
        """
        model = self._config.model
        if self.turn.start_index < len(self.messages):
            protected = self.messages[self.turn.start_index :]
            self.turn.protected_tokens = TokenCounter.count_messages(protected, model=model)
        if TokenCounter.count_messages(self.messages, model=model) <= self._max_tokens:
            return False
        protected_count = max(0, len(self.messages) - self.turn.start_index)
        if self._config.summarize_dropped and await self._try_summarized_compact(protected_count):
            return True
        compactor = _build_compactor(self._config, self._max_tokens)
        self.messages = compactor.compact(
            self.messages, protect_from_index=self.turn.start_index,
        )
        if not is_valid_message_sequence(self.messages):
            self.messages = repair_message_sequence(self.messages)
        self.turn.start_index = max(0, len(self.messages) - protected_count)
        return True

    async def _try_summarized_compact(self: Agent, protected_count: int) -> bool:
        """Try compaction with LLM summarization.

        Args:
            protected_count: Number of messages protected from compaction.

        Returns:
            True if summarization compaction was applied.
        """
        from henchman.utils.compaction import compact_with_summarization  # noqa: PLC0415

        result = await compact_with_summarization(
            messages=self.messages, max_tokens=self._max_tokens,
            provider=self.provider, summarize=True,
            protect_from_index=self.turn.start_index,
            max_protected_ratio=self._config.max_protected_ratio,
        )
        if not result.was_compacted:
            return False
        msgs = result.messages
        if not is_valid_message_sequence(msgs):
            msgs = repair_message_sequence(msgs)
        self.messages = msgs
        self.turn.start_index = max(0, len(msgs) - protected_count)
        return True

    def _build_stream_context(self: Agent, api_messages: list[Message]) -> StreamContext:
        """Build a StreamContext for the current state."""
        return StreamContext(
            provider=self.provider,
            api_messages=api_messages,
            history=self.messages,
            tool_declarations=self.tool_registry.get_declarations(),
            source_agent=self.identity.id if self.identity else None,
        )

    async def _stream_with_stall_loop(self: Agent) -> AsyncIterator[AgentEvent]:
        """Stream provider events with stall detection, retrying on stalls."""
        while True:
            try:
                if not is_valid_message_sequence(self.messages):
                    self.messages = repair_message_sequence(self.messages)
                compacted = await self._compact_if_needed()
                api_messages = self.get_messages_for_api()
                if not is_valid_message_sequence(api_messages):
                    api_messages = repair_message_sequence(api_messages)
                state = StreamState()
                ctx = self._build_stream_context(api_messages)
                async for event in generate_stream_events(ctx, state, compacted=compacted):
                    yield event
                self._last_stream_state = state
                nudge = await self._stall.check(state.content, had_tool_calls=bool(state.tool_calls))  # noqa: E501
                if nudge:
                    self.messages.append(Message(role="user", content=nudge))
                    continue
                break
            except Exception as exc:  # noqa: BLE001
                yield self._emit(EventType.ERROR, f"Streaming failed: {exc}")
                break
