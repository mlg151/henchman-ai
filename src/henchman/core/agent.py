"""Core Agent implementation for orchestrating LLM interactions."""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from importlib import import_module
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

_CONFIG_FIELDS = frozenset(
    {
        "system_prompt",
        "model",
        "base_tool_iterations",
        "intelligent_context",
        "importance_threshold",
        "cluster_similarity_threshold",
        "adaptive_compression",
        "max_protected_ratio",
        "summarize_dropped",
    },
)

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

_MISSING = object()


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


def _import_attrs(module_path: str, *attr_names: str) -> tuple[Any, ...]:
    """Import multiple attributes lazily from *module_path*."""
    module = import_module(module_path)
    return tuple(getattr(module, attr_name) for attr_name in attr_names)


def _get_instance_attr(agent: Agent, name: str, default: Any = _MISSING) -> Any:
    """Return an instance attribute without triggering Agent.__getattr__."""
    try:
        return object.__getattribute__(agent, name)
    except AttributeError:
        if default is _MISSING:
            raise
        return default


def _build_compactor(config: AgentConfig, max_tokens: int) -> Any:
    """Build the appropriate compactor instance.

    Args:
        config: Agent configuration.
        max_tokens: Maximum token limit.

    Returns:
        A ContextCompactor or IntelligentContextManager instance.
    """
    context_compactor = _import_attrs(
        "henchman.utils.compaction",
        "ContextCompactor",
    )[0]
    intelligent_context_params_class = _import_attrs(
        "henchman.utils.intelligent_context_config",
        "IntelligentContextParams",
    )[0]
    intelligent_context_manager = _import_attrs(
        "henchman.utils.intelligent_context",
        "IntelligentContextManager",
    )[0]

    if config.intelligent_context:
        params = intelligent_context_params_class(
            max_tokens=max_tokens,
            max_protected_ratio=config.max_protected_ratio,
            importance_threshold=config.importance_threshold,
            cluster_similarity_threshold=config.cluster_similarity_threshold,
            adaptive_compression=config.adaptive_compression,
        )
        return intelligent_context_manager(params=params)
    return context_compactor(
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


# ---------------------------------------------------------------------------
# Attribute-delegation helpers (support __getattr__ / __setattr__)
# ---------------------------------------------------------------------------


def _getattr_config_field(agent: Agent, name: str) -> Any:
    """Delegate a config-field read to _config or the pending-config buffer."""
    config = _get_instance_attr(agent, "_config", None)
    if config is not None:
        return getattr(config, name)
    pending_config = _get_instance_attr(agent, "_pending_config", None)
    if pending_config is not None and name in pending_config:
        return pending_config[name]
    msg = (
        f"'{type(agent).__name__}' object has no attribute '{name}' "
        "(config not initialized yet)"
    )
    raise AttributeError(msg)


def _getattr_stall_field(agent: Agent, name: str) -> Any:
    """Delegate a stall-field read to _stall."""
    stall = _get_instance_attr(agent, "_stall", None)
    if stall is not None:
        return getattr(stall, _STALL_FIELDS[name])
    msg = (
        f"'{type(agent).__name__}' object has no attribute '{name}' "
        "(stall detector not initialized yet)"
    )
    raise AttributeError(msg)


def _getattr_alias_field(agent: Agent, name: str) -> Any:
    """Delegate an alias read to the target instance attribute."""
    target_name = _INSTANCE_ALIASES[name]
    try:
        return object.__getattribute__(agent, target_name)
    except AttributeError:
        msg = (
            f"'{type(agent).__name__}' object has no attribute '{name}' "
            f"(target '{target_name}' not initialized yet)"
        )
        raise AttributeError(msg) from None


def _set_attr_config(agent: Agent, name: str, value: Any) -> None:
    """Write a config field to _config, or buffer it in _pending_config."""
    config = _get_instance_attr(agent, "_config", None)
    if config is not None:
        setattr(config, name, value)
        return
    pending_config = _get_instance_attr(agent, "_pending_config", None)
    if pending_config is None:
        pending_config = {}
        object.__setattr__(agent, "_pending_config", pending_config)
    pending_config[name] = value


def _set_attr_stall(agent: Agent, name: str, value: Any) -> None:
    """Write a stall field to _stall, or fall back to a plain instance attr."""
    stall = _get_instance_attr(agent, "_stall", None)
    if stall is not None:
        setattr(stall, _STALL_FIELDS[name], value)
        return
    object.__setattr__(agent, name, value)


def _set_attr_alias(agent: Agent, name: str, value: Any) -> None:
    """Write through an instance alias to the target attribute."""
    target_name = _INSTANCE_ALIASES[name]
    if hasattr(agent, target_name):
        setattr(agent, target_name, value)
    else:
        object.__setattr__(agent, name, value)


def _flush_pending_config(agent: Agent) -> None:
    """Transfer buffered config values to _config, then delete the buffer."""
    config = _get_instance_attr(agent, "_config", None)
    pending_config = _get_instance_attr(agent, "_pending_config", None)
    if config is None or pending_config is None:
        return
    for key, value in pending_config.items():
        if key in _CONFIG_FIELDS:
            setattr(config, key, value)
    object.__delattr__(agent, "_pending_config")


# ---------------------------------------------------------------------------
# Compaction helpers
# ---------------------------------------------------------------------------


def _simple_compact(
    config: AgentConfig,
    max_tokens: int,
    messages: list[Message],
    turn_start_index: int,
    protected_count: int,
) -> tuple[list[Message], int]:
    """Apply straightforward compaction without a prior token-limit check.

    Returns:
        (compacted_messages, new_turn_start_index)
    """
    compactor = _build_compactor(config, max_tokens)
    protect_idx = (
        max(0, len(messages) - protected_count)
        if protected_count > 0
        else turn_start_index
    )
    result = compactor.compact(messages, protect_from_index=protect_idx)
    if not is_valid_message_sequence(result):
        result = repair_message_sequence(result)
    new_start = max(0, len(result) - protected_count)
    return result, new_start


async def _try_summarized_compact(
    request: SummarizedCompactRequest,
) -> tuple[bool, list[Message], int]:
    """Try LLM-assisted summarisation compaction.

    Returns:
        (was_compacted, new_messages, new_turn_start_index)
    """
    compaction_params_class, compact_messages = _import_attrs(
        "henchman.utils.compaction",
        "CompactionParams",
        "compact_messages",
    )
    params = compaction_params_class(
        messages=request.messages,
        max_tokens=request.max_tokens,
        provider=request.provider,
        summarize=True,
        protect_from_index=request.turn_start_index,
        max_protected_ratio=request.max_protected_ratio,
    )
    result = await compact_messages(params)
    if not result.was_compacted:
        return False, request.messages, request.turn_start_index
    msgs = result.messages
    if not is_valid_message_sequence(msgs):
        msgs = repair_message_sequence(msgs)
    new_start = max(0, len(msgs) - request.protected_count)
    return True, msgs, new_start


@dataclass(frozen=True)
class SummarizedCompactRequest:
    """Input parameters for summarized compaction."""

    messages: list[Message]
    max_tokens: int
    provider: ModelProvider
    turn_start_index: int
    max_protected_ratio: float
    protected_count: int


# ---------------------------------------------------------------------------
# Streaming helpers
# ---------------------------------------------------------------------------


def _build_stream_context(
    provider: ModelProvider,
    api_messages: list[Message],
    history: list[Message],
    tool_registry: ToolRegistry,
    source_agent: str | None,
) -> StreamContext:
    """Build a StreamContext from the agent's current state."""
    return StreamContext(
        provider=provider,
        api_messages=api_messages,
        history=history,
        tool_declarations=tool_registry.get_declarations(),
        source_agent=source_agent,
    )


async def _non_final_events(
    stream: AsyncIterator[AgentEvent],
) -> AsyncIterator[AgentEvent]:
    """Yield every event from *stream* except FINISHED.

    Keeps the ``while/try/async-for`` nesting in the stall loop at depth ≤ 3.
    """
    async for event in stream:
        if event.type != EventType.FINISHED:
            yield event


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

        # Apply any pending config values that were set before _config was initialized
        self._transfer_pending_config()

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
        # Eagerly initialize delegation error tracking to avoid TOCTOU race
        # in record_delegation_errors() when called from concurrent threads.
        self._delegation_tool_errors: list[str] = []
        self._delegation_tool_errors_lock = threading.Lock()
        if self._config.system_prompt:
            self.messages.append(Message(role="system", content=self._config.system_prompt))

    # -- dynamic attribute delegation ----------------------------------------

    def __getattr__(self: Agent, name: str) -> Any:
        """Delegate attribute access to _config, _stall, or instance aliases.

        Provides backward-compatible access to configuration fields,
        stall detector state, and convenience aliases without repetitive
        property definitions.
        """
        try:
            return object.__getattribute__(self, name)
        except AttributeError:
            pass

        if name in _CONFIG_FIELDS:
            return _getattr_config_field(self, name)
        if name in _STALL_FIELDS:
            return _getattr_stall_field(self, name)
        if name in _INSTANCE_ALIASES:
            return _getattr_alias_field(self, name)
        msg = f"'{type(self).__name__}' object has no attribute '{name}'"
        raise AttributeError(msg)

    def __setattr__(self: Agent, name: str, value: Any) -> None:
        """Delegate attribute writes to _config, _stall, or instance aliases."""
        if name == "_config":
            super().__setattr__(name, value)
            if value is not None and hasattr(self, "_pending_config"):
                _flush_pending_config(self)
            return

        if name in _CONFIG_FIELDS:
            _set_attr_config(self, name, value)
        elif name in _STALL_FIELDS:
            _set_attr_stall(self, name, value)
        elif name in _INSTANCE_ALIASES:
            _set_attr_alias(self, name, value)
        else:
            super().__setattr__(name, value)

    def _transfer_pending_config(self: Agent) -> None:
        """Transfer pending config values to _config and clean up."""
        _flush_pending_config(self)

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
        self.messages, self.turn.start_index = _simple_compact(
            self._config, self._max_tokens, self.messages,
            self.turn.start_index, protected_count,
        )
        return True

    async def _try_summarized_compact(self: Agent, protected_count: int = 0) -> bool:
        """Backward-compatible wrapper around module-level summarized compaction.

        Args:
            protected_count: Number of tail messages to preserve.

        Returns:
            ``True`` when summarized compaction changed the message history.
        """
        compacted, msgs, new_start = await _try_summarized_compact(
            SummarizedCompactRequest(
                messages=self.messages,
                max_tokens=self._max_tokens,
                provider=self.provider,
                turn_start_index=self.turn.start_index,
                max_protected_ratio=self._config.max_protected_ratio,
                protected_count=protected_count,
            ),
        )
        if compacted:
            self.messages = msgs
            self.turn.start_index = new_start
        return compacted

    async def _apply_compaction_if_needed(self: Agent) -> bool:
        """Backward-compat alias for :meth:`_compact_if_needed`."""
        return await self._compact_if_needed()

    # -- public API ----------------------------------------------------------

    def clear_history(self: Agent) -> None:
        """Clear the conversation history, keeping the system prompt.

        Also resets the turn state to ensure consistency.

        Returns:
            None
        """
        self.messages = [m for m in self.messages if m.role == "system"]
        # Reset turn state to be consistent with cleared history
        self.turn = TurnState()

    def get_messages_for_api(self: Agent) -> list[Message]:
        """Get messages for the API, with compaction if needed.

        Returns:
            List of messages, potentially compacted to fit within max_tokens.
        """
        compactor = _build_compactor(self._config, self._max_tokens)
        result: list[Message] = compactor.compact(
            self.messages,
            protect_from_index=self.turn.start_index,
        )
        return result

    def submit_tool_result(self: Agent, tool_call_id: str, result: str) -> None:
        """Submit a tool result to continue the conversation.

        Args:
            tool_call_id: The ID of the tool call to associate the result with.
            result: The result content from the tool execution.

        Returns:
            None
        """
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

        Yields:
            AgentEvent instances as the agent continues processing after tool
            results have been submitted.
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
        if self._config.summarize_dropped:
            compacted, msgs, new_start = await _try_summarized_compact(
                SummarizedCompactRequest(
                    messages=self.messages,
                    max_tokens=self._max_tokens,
                    provider=self.provider,
                    turn_start_index=self.turn.start_index,
                    max_protected_ratio=self._config.max_protected_ratio,
                    protected_count=protected_count,
                ),
            )
            if compacted:
                self.messages = msgs
                self.turn.start_index = new_start
                return True
        compactor = _build_compactor(self._config, self._max_tokens)
        self.messages = compactor.compact(
            self.messages,
            protect_from_index=self.turn.start_index,
        )
        if not is_valid_message_sequence(self.messages):
            self.messages = repair_message_sequence(self.messages)
        self.turn.start_index = max(0, len(self.messages) - protected_count)
        return True

    async def _stream_with_stall_loop(self: Agent) -> AsyncIterator[AgentEvent]:
        """Stream provider events with stall detection, retrying on stalls.

        Inner FINISHED events from ``generate_stream_events`` are suppressed
        here so that ``run()`` can emit a single, authoritative FINISHED event
        with the full payload (finish_reason + usage).  Callers should treat
        the FINISHED event from ``run()`` as the canonical end-of-turn signal.
        """
        while True:
            try:
                if not is_valid_message_sequence(self.messages):
                    self.messages = repair_message_sequence(self.messages)
                compacted = await self._compact_if_needed()
                api_messages = self.get_messages_for_api()
                if not is_valid_message_sequence(api_messages):
                    api_messages = repair_message_sequence(api_messages)
                state = StreamState()
                source = self.identity.id if self.identity else None
                ctx = _build_stream_context(
                    self.provider, api_messages, self.messages,
                    self.tool_registry, source,
                )
                raw_stream = generate_stream_events(ctx, state, compacted=compacted)
                async for event in _non_final_events(raw_stream):
                    yield event
                self._last_stream_state = state
                nudge = await self._stall.check(
                    state.content, had_tool_calls=bool(state.tool_calls),
                )
                if nudge:
                    self.messages.append(Message(role="user", content=nudge))
                    continue
                break
            except Exception as exc:  # noqa: BLE001
                yield self._emit(EventType.ERROR, f"Streaming failed: {exc}")
                break

    # -- delegation error tracking ------------------------------------------

    def record_delegation_errors(self: Agent, errors: list[str]) -> None:
        """Record tool errors from a delegation for inclusion in summaries.

        Thread-safe: uses a lock initialized in ``__init__`` to avoid TOCTOU
        races when called from concurrent threads.

        Args:
            errors: List of error messages to record.

        Returns:
            None
        """
        with self._delegation_tool_errors_lock:
            self._delegation_tool_errors.extend(errors)

    def get_delegation_errors(self: Agent) -> list[str]:
        """Get recorded delegation tool errors.

        Returns:
            List of error messages recorded via record_delegation_errors().
        """
        return self._delegation_tool_errors
