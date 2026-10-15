"""Core Agent implementation for orchestrating LLM interactions."""

from __future__ import annotations

import logging
import threading
from contextlib import aclosing
from dataclasses import dataclass
from importlib import import_module
from typing import TYPE_CHECKING, Any

from henchman.core.agent_config import AgentConfig
from henchman.core.agent_stall import StallDetector
from henchman.core.agent_streaming import (
    StreamContext,
    StreamState,
    generate_stream_events,
    record_message,
)
from henchman.core.events import AgentEvent, EventType
from henchman.core.tool_selection import prepare_agent_request
from henchman.core.turn import TurnState
from henchman.providers.base import Message, ModelProvider
from henchman.tools.registry import ToolRegistry
from henchman.utils.tokens import TokenCounter, get_model_limit
from henchman.utils.validation import (
    is_valid_message_sequence,
    repair_message_sequence,
)

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

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
        "context_window",
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


def validate_context_limit(max_tokens: int) -> None:
    """Require an explicit positive integer context budget."""
    if type(max_tokens) is not int or max_tokens <= 0:
        raise ValueError("Context limit must be a positive integer")


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
    current_turn_messages: list[Message] | None = None,
) -> StreamContext:
    """Build a StreamContext from the agent's current state."""
    return StreamContext(
        provider=provider,
        api_messages=api_messages,
        history=history,
        tool_declarations=tool_registry.get_declarations(),
        source_agent=source_agent,
        current_turn_messages=current_turn_messages,
    )


async def _non_final_events(
    stream: AsyncGenerator[AgentEvent, None],
) -> AsyncGenerator[AgentEvent, None]:
    """Yield every event from *stream* except FINISHED.

    Keeps the ``while/try/async-for`` nesting in the stall loop at depth ≤ 3.
    """
    async with aclosing(stream):
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
        if self._config.context_window is not None:
            validate_context_limit(self._config.context_window)

        self._stall = StallDetector()
        model = self._config.model
        if not model and hasattr(provider, "default_model"):
            model = provider.default_model
        self._config.model = model
        self._max_tokens = _resolve_max_tokens(self._config.max_tokens, model)
        self.messages: list[Message] = []
        # Persistence must use original turn evidence, not compacted API context.
        self.current_turn_messages: list[Message] = []
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

    def set_provider(self, provider: ModelProvider, *, model: str | None = None) -> None:
        """Replace the provider and refresh model limits while retaining conversation state."""
        effective_model = model if model is not None else getattr(provider, "default_model", None)
        max_tokens = _resolve_max_tokens(self._config.max_tokens, effective_model)
        self.provider = provider
        self._config.model = effective_model
        self._max_tokens = max_tokens

    def set_context_limit(
        self, max_tokens: int, *, context_window: int | None = None,
    ) -> None:
        """Set conversation and optional request limits retained across switches."""
        validate_context_limit(max_tokens)
        if context_window is not None:
            validate_context_limit(context_window)
            self._config.context_window = context_window
        self._config.max_tokens = max_tokens
        self._max_tokens = max_tokens

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
        self.current_turn_messages = []
        # Reset turn state to be consistent with cleared history
        self.turn = TurnState()
        self._stall.reset()
        self._clear_delegation_errors()

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
        record_message(
            self.messages,
            Message(role="tool", content=result, tool_call_id=tool_call_id),
            self.current_turn_messages,
        )

    async def run(self: Agent, user_input: str) -> AsyncGenerator[AgentEvent, None]:
        """Run the agent with user input.

        Args:
            user_input: The user message to process.

        Yields:
            AgentEvent instances as the agent processes the input.
        """
        logger.debug("Agent.run: Starting with input: %s", user_input[:LOG_TRUNCATE_LENGTH])
        self._turn_number += 1
        if self.tool_registry.supports_tool_discovery:
            self.tool_registry.prioritize_tools([])
        self.turn.reset(new_start_index=len(self.messages))
        self._stall.reset()
        self._clear_delegation_errors()
        self.current_turn_messages = []
        record_message(
            self.messages, Message(role="user", content=user_input), self.current_turn_messages,
        )
        async with aclosing(self._stream_with_stall_loop()) as stream:
            async for event in stream:
                yield event
        source = self.identity.id if self.identity else None
        yield _build_outer_finished_event(self._last_stream_state, source)

    async def continue_with_tool_results(self: Agent) -> AsyncGenerator[AgentEvent, None]:
        """Continue execution after tool results have been submitted.

        Includes the same stall-detection loop used by :meth:`run` so that
        agents which narrate intent without acting are nudged to call tools.

        Yields:
            AgentEvent instances as the agent continues processing after tool
            results have been submitted.
        """
        async with aclosing(self._stream_with_stall_loop()) as stream:
            async for event in stream:
                yield event
        source = self.identity.id if self.identity else None
        yield _build_outer_finished_event(self._last_stream_state, source)

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

    async def _prepare_stream_context(self) -> tuple[StreamContext, bool]:
        """Snapshot tools and prepare one request under the active capacity policy."""
        source = self.identity.id if self.identity else None
        if self._config.context_window is not None:
            request = prepare_agent_request(
                self.provider, self.messages, self.tool_registry,
                context_window=self._config.context_window,
                conversation_limit=self._max_tokens,
                protect_from_index=self.turn.start_index,
            )
            return StreamContext(
                self.provider, request.messages, self.messages, request.tools,
                source, self.current_turn_messages, request.request_options,
            ), request.compacted
        if not is_valid_message_sequence(self.messages):
            self.messages = repair_message_sequence(self.messages)
        compacted = await self._compact_if_needed()
        api_messages = self.get_messages_for_api()
        if not is_valid_message_sequence(api_messages):
            api_messages = repair_message_sequence(api_messages)
        return _build_stream_context(
            self.provider, api_messages, self.messages,
            self.tool_registry, source, self.current_turn_messages,
        ), compacted

    async def _stream_with_stall_loop(self: Agent) -> AsyncGenerator[AgentEvent, None]:
        """Stream provider events with stall detection, retrying on stalls.

        Inner FINISHED events from ``generate_stream_events`` are suppressed
        here so that ``run()`` and ``continue_with_tool_results()`` each emit
        one authoritative FINISHED event with the response's reason and usage.
        Tool requests still require execution and a continuation by the caller.
        """
        while True:
            self._last_stream_state = None
            try:
                ctx, compacted = await self._prepare_stream_context()
                state = StreamState()
                raw_stream = generate_stream_events(ctx, state, compacted=compacted)
                stream_failed = False
                async with aclosing(_non_final_events(raw_stream)) as stream:
                    async for event in stream:
                        if event.type == EventType.ERROR:
                            stream_failed = True
                        yield event
                self._last_stream_state = state
                if stream_failed:
                    break
                nudge = await self._stall.check(
                    state.content, had_tool_calls=bool(state.tool_calls),
                )
                if nudge:
                    record_message(
                        self.messages, Message(role="user", content=nudge),
                        self.current_turn_messages,
                    )
                    continue
                break
            except Exception as exc:  # noqa: BLE001
                yield self._emit(EventType.ERROR, f"Streaming failed: {exc}")
                break

    # -- delegation error tracking ------------------------------------------

    def _clear_delegation_errors(self: Agent) -> None:
        """Start fresh diagnostics at an execution or explicit history boundary."""
        with self._delegation_tool_errors_lock:
            self._delegation_tool_errors.clear()

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
