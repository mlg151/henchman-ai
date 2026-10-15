"""Delegation execution for the orchestrator."""

from __future__ import annotations

import contextlib
import logging
import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

import anyio

from henchman.agents.orchestrator_execution import _close_stream, closing_event_stream
from henchman.agents.orchestrator_types import AgentLoopParams
from henchman.core.agent_config import AgentConfig
from henchman.core.events import AgentEvent, EventType

from .orchestrator_anchoring import (
    _enrich_completion_from_report,
    completion_evidence,
)
from .orchestrator_events import get_completion_requirement
from .pool import ActiveAgentError

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable

    from henchman.agents.ledger import TaskLedger
    from henchman.agents.metrics import OrchestratorMetrics
    from henchman.agents.orchestrator_types import CompletionStatus, DelegationParams
    from henchman.agents.pool import AgentPool
    from henchman.config.schema import Settings
    from henchman.core.agent import Agent
    from henchman.providers.base import Message


logger = logging.getLogger(__name__)


@runtime_checkable
class AgentProtocol(Protocol):
    """Protocol defining the minimum interface required for delegation.

    This ensures type safety when working with agent instances in delegation.
    """

    messages: Sequence[Message]
    """The agent's conversation history."""

    def clear_history(self: AgentProtocol) -> None:
        """Clear conversation history while preserving system prompt.

        Returns:
            None
        """
        ...


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

RECENT_CONTEXT_ENTRIES = 5
"""Number of recent shared-context entries to include in handoffs."""

MAX_SUMMARY_LENGTH = 200
"""Maximum length for summary text in handoff notes."""

RECENT_ERRORS_TO_SHOW = 10
"""Number of recent tool errors to show in delegation summaries."""

MAX_CONTENT_LENGTH = 800
"""Maximum length for shared-context summary entries."""

MAX_SHARED_CONTEXT_ENTRIES = 50
"""Maximum number of entries to keep in shared context."""

_MAX_ATTRS_IN_ERROR = 10
"""Maximum number of attributes to show in error messages."""

_MAX_REPR_LENGTH = 100
"""Maximum length for repr() output in error messages."""

SAME_AGENT_RELEVANCE_BONUS: float = 0.3
"""Bonus score added when a context entry was produced by the same specialist."""

KEYWORD_OVERLAP_WEIGHT: float = 0.7
"""Weight applied to keyword-overlap fraction in context relevance scoring."""

MAX_PARALLEL_DELEGATION_BUFFER: int = 10_000
"""Maximum event-buffer size for concurrent parallel delegations."""

_STOP_WORDS: frozenset[str] = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "by",
        "do",
        "for",
        "from",
        "has",
        "he",
        "in",
        "is",
        "it",
        "its",
        "of",
        "on",
        "or",
        "that",
        "the",
        "this",
        "to",
        "was",
        "were",
        "will",
        "with",
    },
)
"""Common words excluded when scoring context relevance."""

# Pre-compiled regex patterns for performance
_COMPLETION_REPORT_PATTERNS = {
    "status": re.compile(r"(?im)^[ \t]*STATUS:[ \t]*([^\r\n]*)"),
    "files_modified": re.compile(r"(?im)^[ \t]*FILES_MODIFIED:[ \t]*([^\r\n]*)"),
    "tests_run": re.compile(r"(?im)^[ \t]*TESTS_RUN:[ \t]*([^\r\n]*)"),
    "verification": re.compile(r"(?im)^[ \t]*VERIFICATION:[ \t]*([^\r\n]*)"),
    "blockers": re.compile(r"(?im)^[ \t]*BLOCKERS:[ \t]*([^\r\n]*)"),
    "handoff_notes": re.compile(r"(?im)^[ \t]*HANDOFF_NOTES:[ \t]*([^\r\n]*)"),
    "artifacts": re.compile(r"(?im)^[ \t]*ARTIFACTS:[ \t]*([^\r\n]*)"),
}
"""Pre-compiled regex patterns for parsing completion reports."""


# ---------------------------------------------------------------------------
# Context relevance scoring
# ---------------------------------------------------------------------------


def _score_context_relevance(
    entry: dict[str, Any],
    task: str,
    target_role: str,
) -> float:
    """Score how relevant a shared-context entry is for a new delegation.

    The score is a float in [0.0, 1.0] composed of:

    - **0.3** if the entry was produced by the same specialist
      (``target_role`` match — prior work by the same agent is directly
      relevant).
    - **0.7 x (overlap / task_tokens)** based on keyword overlap between
      the task description and the entry's summary + files_modified text,
      after filtering common stop words.

    Args:
        entry: A shared-context dict with keys ``agent``, ``summary``,
            and ``files_modified``.
        task: The task description being delegated.
        target_role: The role ID of the specialist receiving the task.

    Returns:
        Relevance score in [0.0, 1.0].
    """
    score = 0.0

    if entry.get("agent") == target_role:
        score += SAME_AGENT_RELEVANCE_BONUS

    task_tokens = {w.lower() for w in task.split() if w.lower() not in _STOP_WORDS}
    if not task_tokens:
        return score

    entry_text = (entry.get("summary", "") or "") + " " + (entry.get("files_modified", "") or "")
    summary_tokens = {w.lower() for w in entry_text.split() if w.lower() not in _STOP_WORDS}

    overlap = task_tokens & summary_tokens
    score += KEYWORD_OVERLAP_WEIGHT * (len(overlap) / len(task_tokens))
    return score


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def _validate_agent_messages_attr(agent: Any, role: str) -> str | None:
    """Validate the messages attribute of an agent.

    Args:
        agent: The agent object to validate.
        role: The role name for error messages.

    Returns:
        Error string if invalid, None if valid.
    """
    if not hasattr(agent, "messages"):
        return (
            f"Agent '{role}' (type: {type(agent).__name__}) does not conform to "
            f"AgentProtocol. Missing required 'messages' attribute."
        )
    if agent.messages is None:
        return f"Agent '{role}' has messages=None. Expected Sequence[Message], got NoneType."
    if isinstance(agent.messages, (str, bytes)) or not isinstance(agent.messages, Sequence):
        msg_type = type(agent.messages).__name__
        return (
            f"Agent '{role}' has invalid 'messages' attribute: "
            f"expected Sequence[Message], got {msg_type}"
        )
    return None


def _validate_agent_messages_content(agent: Any, role: str) -> str | None:
    """Validate the content of the first message in the agent's messages.

    Args:
        agent: The agent object to validate.
        role: The role name for error messages.

    Returns:
        Error string if invalid, None if valid.
    """
    if not agent.messages:
        return None
    try:
        sample = agent.messages[0]
    except (IndexError, TypeError) as exc:
        return f"Agent '{role}' messages sequence is invalid: cannot access index 0: {exc}"
    if not (hasattr(sample, "role") and hasattr(sample, "content")):
        return (
            f"Agent '{role}' messages appear to not be Message instances. "
            f"First message type: {type(sample).__name__}"
        )
    return None


def _check_agent_protocol_compliance(agent: Any, role: str) -> str | None:
    """Check if an agent conforms to AgentProtocol.

    Args:
        agent: The agent object to check.
        role: The role name for error messages.

    Returns:
        Error string if non-compliant, None if compliant.
    """
    error = _validate_agent_messages_attr(agent, role)
    if error:
        return error
    if not hasattr(agent, "clear_history"):
        attrs = [a for a in dir(agent) if not a.startswith("_")][:_MAX_ATTRS_IN_ERROR]
        return (
            f"Agent '{role}' does not conform to AgentProtocol. "
            f"Missing required 'clear_history()' method. Got attributes: {attrs}..."
        )
    if not callable(agent.clear_history):
        ch_type = type(agent.clear_history).__name__
        ch_repr = repr(agent.clear_history)[:_MAX_REPR_LENGTH]
        return (
            f"Agent '{role}' clear_history attribute is not callable: "
            f"got {ch_type} (value: {ch_repr})"
        )
    return None


def _add_to_shared_context(
    shared_context: list[dict[str, Any]],
    target_role: str,
    summary: str,
    parsed: dict[str, str],
) -> None:
    """Add delegation result to shared context with size limits.

    Args:
        shared_context: The mutable shared context list to update.
        target_role: Role of the agent that completed the delegation.
        summary: Summary text from the agent.
        parsed: Parsed completion report dictionary.
    """
    if not isinstance(shared_context, list):
        msg = f"shared_context must be a list, got {type(shared_context).__name__}"
        raise TypeError(msg)
    if not isinstance(target_role, str) or not target_role.strip():
        msg = f"target_role must be a non-empty string, got {target_role!r}"
        raise ValueError(msg)
    if summary is not None and not isinstance(summary, str):
        msg = f"summary must be a string or None, got {type(summary).__name__}"
        raise TypeError(msg)
    if not isinstance(parsed, dict):
        msg = f"parsed must be a dict, got {type(parsed).__name__}"
        raise TypeError(msg)
    summary_text = summary[:MAX_CONTENT_LENGTH] if summary else ""
    files_modified = parsed.get("files_modified", "") if parsed else ""
    entry = {
        "agent": target_role,
        "summary": summary_text,
        "files_modified": files_modified,
        "timestamp": datetime.now(tz=UTC).isoformat(),
    }
    shared_context.append(entry)
    if len(shared_context) > MAX_SHARED_CONTEXT_ENTRIES:
        excess = len(shared_context) - MAX_SHARED_CONTEXT_ENTRIES
        del shared_context[:excess]


def _validate_messages_access(target_agent: Any, msg_start: int) -> None:
    """Validate that message sequence access parameters are correct.

    Args:
        target_agent: The agent whose messages to validate.
        msg_start: The start index into the messages sequence.

    Raises:
        TypeError: If msg_start or messages has wrong type.
        ValueError: If msg_start is out of bounds.
        AttributeError: If target_agent is missing messages attribute.
    """
    _validate_msg_start(msg_start)
    messages = _get_target_agent_messages(target_agent)
    _validate_msg_start_bounds(messages, msg_start)
    _validate_message_sample(messages, msg_start)


def _validate_msg_start(msg_start: int) -> None:
    """Validate the delegation message start index."""
    if not isinstance(msg_start, int):
        msg = f"msg_start must be an integer, got {type(msg_start).__name__}"
        raise TypeError(msg)
    if msg_start < 0:
        msg = f"msg_start must be non-negative, got {msg_start}"
        raise ValueError(msg)


def _get_target_agent_messages(target_agent: Any) -> Sequence[Any]:
    """Return a validated messages sequence from *target_agent*."""
    if not hasattr(target_agent, "messages"):
        msg = f"target_agent missing 'messages' attribute (type: {type(target_agent).__name__})"
        raise AttributeError(msg)
    messages = target_agent.messages
    if messages is None:
        msg = "target_agent.messages is None"
        raise ValueError(msg)
    if not isinstance(messages, Sequence):
        msg = f"target_agent.messages must be a Sequence, got {type(messages).__name__}"
        raise TypeError(msg)
    return messages


def _validate_msg_start_bounds(messages: Sequence[Any], msg_start: int) -> None:
    """Validate that *msg_start* fits within *messages*."""
    if msg_start > len(messages):
        msg = f"msg_start ({msg_start}) exceeds messages length ({len(messages)})"
        raise ValueError(msg)


def _validate_message_sample(messages: Sequence[Any], msg_start: int) -> None:
    """Validate the message located at *msg_start*, if one exists."""
    if not messages or msg_start >= len(messages):
        return
    try:
        sample_msg = messages[msg_start]
    except (IndexError, TypeError) as exc:
        msg = f"Invalid messages sequence at index {msg_start}: {exc}"
        raise TypeError(msg) from exc
    if not (hasattr(sample_msg, "role") and hasattr(sample_msg, "content")):
        msg = (
            f"messages do not appear to be Message instances. "
            f"First message type: {type(sample_msg).__name__}"
        )
        raise TypeError(msg)


def _collect_tool_errors(errors: list[Any]) -> list[str]:
    """Collect and stringify tool errors, skipping non-stringifiable items.

    Args:
        errors: Raw list of error objects.

    Returns:
        List of string-converted errors.
    """
    result: list[str] = []
    for item in errors:
        if item is not None:
            with contextlib.suppress(TypeError, ValueError):
                result.append(str(item))
    return result


def _fetch_agent_errors(target_agent: Any) -> list[str]:
    """Fetch tool errors from an agent using whichever API is available.

    Args:
        target_agent: The agent to fetch errors from.

    Returns:
        List of error strings, empty if none found.
    """
    try:
        if hasattr(target_agent, "get_delegation_errors"):
            errors = target_agent.get_delegation_errors()
        else:
            errors = getattr(target_agent, "_delegation_tool_errors", None)
            if errors is None:
                return []
        if errors is not None and isinstance(errors, list):
            return _collect_tool_errors(errors)
    except (AttributeError, TypeError, RuntimeError) as exc:
        logger.warning(
            "Failed to fetch delegation errors from agent %r: %s",
            type(target_agent).__name__,
            exc,
        )
    except Exception:  # noqa: BLE001
        # Catch-all for unexpected errors, but log with full traceback
        logger.warning(
            "Unexpected error fetching delegation errors from agent %r",
            type(target_agent).__name__,
            exc_info=True,
        )
    return []


def _get_status_value(status: Any) -> str:
    """Get a string value from a completion status safely.

    Args:
        status: The completion status object.

    Returns:
        The status value string, or "UNKNOWN_STATUS" if not extractable.
    """
    value = getattr(status, "value", None)
    if isinstance(value, str):
        return value
    with contextlib.suppress(Exception):
        if status is not None:
            return str(status)
    return "UNKNOWN_STATUS"


def _final_completion_report(target_agent: Agent, msg_start: int) -> str:
    """Read the last assistant message in this delegation, including an empty one."""
    for message in reversed(target_agent.messages[msg_start:]):
        if message.role == "assistant":
            return message.content or ""
    return ""


def _build_agent_summary(target_agent: Any, msg_start: int) -> str:
    """Build summary from agent's conversation history.

    Args:
        target_agent: The agent whose messages to summarise.
        msg_start: Index of the first relevant message.

    Returns:
        Summary string, optionally with a tool-error digest appended.
    """
    messages = target_agent.messages
    summary_parts = (m.content for m in messages[msg_start:] if m.role == "assistant" and m.content)
    summary = "\n\n".join(summary_parts)
    tool_errors = _fetch_agent_errors(target_agent)
    if tool_errors:
        recent = tool_errors[-RECENT_ERRORS_TO_SHOW:]
        error_digest = "\n--- \u26a0\ufe0f TOOL ERRORS ---\n" + "\n".join(
            f"\u2022 {e}" for e in recent
        )
        summary = f"{summary}\n{error_digest}"
    return summary


@dataclass
class _SectionFormat:
    """Format specification for a list section in delegation input.

    Groups the three formatting primitives (header, item_format, footer)
    that are always passed together to ``_append_list_section``.
    """

    header: str
    item_format: str = "- {0}"
    footer: str = ""


def _append_list_section(
    sections: list[str],
    items: list[str] | str,
    fmt: _SectionFormat,
) -> None:
    """Append a formatted list section to sections.

    Args:
        sections: The sections list to append to.
        items: Items to list (string or list of strings).
        fmt: Section format specification (header, item_format, footer).
    """
    if isinstance(items, str):
        items = [items]
    item_lines = "\n".join(fmt.item_format.format(i) for i in items)
    body = f"{fmt.header}\n{item_lines}"
    if fmt.footer:
        body = f"{body}\n{fmt.footer}"
    sections.append(body)


_DEPENDS_ON_FOOTER = "_(These tasks were completed earlier; build on their outputs.)_"


def _append_files_section(sections: list[str], brief_get: Any) -> None:
    """Append the Relevant Files section if files are present."""
    files = brief_get("files")
    if files:
        _append_list_section(sections, files, _SectionFormat("## Relevant Files", "- `{0}`"))


def _append_depends_on_section(sections: list[str], brief_get: Any) -> None:
    """Append the Depends On section if dependencies are present."""
    depends_on = brief_get("depends_on")
    if depends_on:
        _append_list_section(
            sections,
            depends_on,
            _SectionFormat("## Depends On", footer=_DEPENDS_ON_FOOTER),
        )


def _assemble_delegation_input(
    task: str,
    brief: dict[str, Any] | None,
    mission: str | None = None,
) -> str:
    """Build a self-contained input string from the structured delegation brief.

    Args:
        task: The core task description.
        brief: Optional structured fields from the Tech Lead.
        mission: Optional high-level mission statement for context.

    Returns:
        A formatted string ready to be passed as user input to the specialist.
    """
    sections: list[str] = []
    if mission:
        sections.append(f"## Mission\n{mission}")
    sections.append(f"## Task\n{task}")
    if not brief:
        return "\n\n".join(sections)
    brief_get = brief.get
    if brief_get("done_when"):
        sections.append(
            f"## Done When\n{brief_get('done_when')}\n"
            f"_(Stop working once these conditions are met.)_",
        )
    if brief_get("requirements"):
        sections.append(f"## Requirements\n{brief_get('requirements')}")
    _append_files_section(sections, brief_get)
    _append_depends_on_section(sections, brief_get)
    if brief_get("background"):
        sections.append(f"## Background\n{brief_get('background')}")
    if brief_get("context"):
        sections.append(f"## Additional Context\n{brief_get('context')}")
    return "\n\n".join(sections)


def _parse_completion_report(summary: str) -> dict[str, str]:
    """Extract structured fields from a specialist's completion report.

    Args:
        summary: Raw summary text from the specialist.

    Returns:
        Dict with extracted fields (may be empty if format not found).

    Raises:
        TypeError: If summary is not a string.
    """
    # CRITICAL BUG FIX: Type safety validation
    if not isinstance(summary, str):
        msg = f"summary must be a string, got {type(summary).__name__}"
        raise TypeError(msg)

    parsed: dict[str, str] = {}
    for key, pattern in _COMPLETION_REPORT_PATTERNS.items():
        match = pattern.search(summary)
        if match:
            parsed[key] = match.group(1).strip()
    return parsed


# ---------------------------------------------------------------------------
# AgentLoopRunner protocol
# ---------------------------------------------------------------------------


class AgentLoopRunner(Protocol):
    """Protocol for the agent loop callback."""

    def __call__(
        self: AgentLoopRunner,
        params: AgentLoopParams,
    ) -> AsyncIterator[AgentEvent]:
        """Run the agent loop.

        Args:
            params: Agent loop parameters.

        Yields:
            AgentEvents from the loop.
        """
        ...  # pragma: no cover


# ---------------------------------------------------------------------------
# Module-level delegation lifecycle helpers
# ---------------------------------------------------------------------------


def _prepare_execution(runner: DelegationRunner, params: DelegationParams) -> None:
    """Prepare agent and context for delegation execution.

    Args:
        runner: The DelegationRunner that owns this delegation.
        params: Delegation parameters (must have target_agent set).

    Raises:
        ValueError: If params.target_agent is None.
        TypeError: If target_agent doesn't conform to AgentProtocol.
        AttributeError: If clear_history is missing after protocol check.
    """
    target_agent = _get_valid_target_agent_for_execution(params)
    _clear_target_agent_history(target_agent, params.target_role)
    _populate_execution_params(runner, params, target_agent)


def _get_valid_target_agent_for_execution(params: DelegationParams) -> Any:
    """Return the validated target agent for a delegation."""
    if params.target_agent is None:
        msg = f"Cannot prepare execution for agent '{params.target_role}': target_agent is None."
        raise ValueError(msg)
    target_agent = params.target_agent
    error = _check_agent_protocol_compliance(target_agent, params.target_role)
    if error:
        raise TypeError(error)
    content_error = _validate_agent_messages_content(target_agent, params.target_role)
    if content_error:
        raise TypeError(content_error)
    return target_agent


def _clear_target_agent_history(target_agent: Any, target_role: str) -> None:
    """Clear target-agent history while preserving original error behavior."""
    try:
        target_agent.clear_history()
    except AttributeError as exc:
        msg = f"Agent '{target_role}' missing 'clear_history()': {exc}"
        raise AttributeError(msg) from exc
    except Exception as exc:
        msg = f"Failed to clear history for agent '{target_role}': {exc}"
        exc.args = (msg, *exc.args[1:]) if exc.args else (msg,)
        raise


def _populate_execution_params(
    runner: DelegationRunner,
    params: DelegationParams,
    target_agent: Any,
) -> None:
    """Populate the fully rendered task and message bounds on *params*."""
    prepared_brief = runner._prepare_delegation_context(  # noqa: SLF001
        params.target_role,
        params.brief,
        task=params.task,
    )
    params.full_task = runner._assemble_delegation_input(  # noqa: SLF001
        params.task,
        prepared_brief,
        mission=runner.ledger.goal if runner.ledger else None,
    )
    params.msg_start = len(target_agent.messages)


def _render_runtime_limits(agent: Any, max_calls: int) -> str:
    """Describe the current execution settings without changing their enforcement."""
    lines = ["## Runtime Limits for This Delegation"]
    if type(max_calls) is int:
        if max_calls > 0:
            lines.append(
                f"Tool-call stop threshold: {max_calls} individual requested calls, "
                "including failed calls. Each call in a batch counts separately; "
                "the threshold is checked after the entire batch executes. "
                "Reaching it stops this delegation before another model response. "
                "Finish verification and report before exhausting this threshold."
            )
        else:
            lines.append("Tool-call stop threshold: disabled for this execution.")
    batches = getattr(agent, "base_tool_iterations", AgentConfig().base_tool_iterations)
    if type(batches) is int and batches >= 0:
        lines.append(
            f"Tool-batch limit: {batches} executed batches. "
            "A batch contains one or more requested tool calls. "
            + ("With zero batches, no tool batch can execute. " if batches == 0 else "")
            + "A final answer without tools is allowed after the last permitted batch "
            "if the tool-call stop threshold has not been reached."
        )
    capacity = getattr(agent, "context_window", None)
    if type(capacity) is int and capacity > 0:
        lines.append(
            f"Request context capacity: {capacity} tokens, including instructions, "
            "messages, tool schemas and reserved output."
        )
    elif capacity is None:
        lines.append("Request context capacity: not explicitly configured.")
    target = getattr(agent, "max_tokens", None)
    if type(target) is int and target > 0:
        lines.append(f"Conversation compaction target: {target} tokens.")
    lines.append(
        "These are execution settings, not an exact remaining-token count. "
        "Use focused reads and concise results; reserve time for verification and your final report."
    )
    return "\n".join(lines)


async def _execute_loop(
    runner: DelegationRunner,
    params: DelegationParams,
    loop_params: AgentLoopParams | None = None,
) -> AsyncIterator[AgentEvent]:
    """Execute the agent loop for a single delegation.

    Args:
        runner: The DelegationRunner that owns this delegation.
        params: Delegation parameters with target_agent, full_task, msg_start set.

    Yields:
        AgentEvents from the specialist agent.

    Raises:
        TypeError: If runner._run_agent_loop doesn't return an async iterator.
        RuntimeError: If agent loop execution fails.
    """
    max_turns = runner.settings.agents.max_delegation_turns
    if loop_params is None:
        loop_params = AgentLoopParams()
    loop_params.agent = params.target_agent
    loop_params.depth = params.depth
    loop_params.max_turns = max_turns
    loop_params.msg_start_index = params.msg_start
    loop_params.completion_requirement = get_completion_requirement(params.brief)
    loop_params.input_text = (
        f"{params.full_task}\n\n{_render_runtime_limits(loop_params.agent, loop_params.max_turns)}"
    )
    agent_loop_result = runner._run_agent_loop(loop_params)  # noqa: SLF001
    primary_error: BaseException | None = None
    try:
        async for event in agent_loop_result:
            yield event
    except Exception as exc:
        primary_error = exc
        msg = (
            f"Failed to execute agent loop for '{params.target_role}': {type(exc).__name__}: {exc}"
        )
        raise RuntimeError(msg) from exc
    except BaseException as exc:
        primary_error = exc
        raise
    finally:
        await _close_stream(agent_loop_result, primary_error=primary_error)


async def _finalize_execution(
    runner: DelegationRunner,
    params: DelegationParams,
) -> AsyncIterator[AgentEvent]:
    """Process delegation results and emit the completion event.

    Args:
        runner: The DelegationRunner that owns this delegation.
        params: Delegation parameters with target_agent and msg_start set.

    Yields:
        AGENT_COMPLETED event with results.

    Raises:
        ValueError: If params.target_agent is None.
    """
    if params.target_agent is None:
        msg = f"Cannot finalize: agent '{params.target_role}' target_agent is None."
        raise ValueError(msg)
    summary, parsed, status = runner._process_delegation_results(  # noqa: SLF001
        params.target_role,
        params.target_agent,
        params.msg_start,
    )
    _add_to_shared_context(
        runner.shared_context,
        params.target_role,
        summary,
        parsed,
    )
    status_value = _get_status_value(status)
    yield AgentEvent(
        type=EventType.AGENT_COMPLETED,
        data={
            **parsed,
            "agent": params.target_role,
            "summary": summary,
            "status": status_value,
            **completion_evidence(params.target_agent),
        },
        source_agent="orchestrator",
    )


# ---------------------------------------------------------------------------
# DelegationRunner class
# ---------------------------------------------------------------------------


class DelegationRunner:
    """Executes delegations from the orchestrator to specialist agents.

    Args:
        pool: Agent pool for resolving target agents.
        settings: Application settings (max depth, max turns).
        shared_context: Shared mutable context list.
        metrics: Metrics instance for delegation counting.
        run_agent_loop: Callback to run the core agent loop.
        assess_completion: Callback to assess agent completion status.
    """

    def __init__(  # noqa: PLR0913
        self: DelegationRunner,
        pool: AgentPool,
        settings: Settings,
        shared_context: list[dict[str, Any]],
        metrics: OrchestratorMetrics,
        run_agent_loop: AgentLoopRunner,
        assess_completion: Callable[[Agent], CompletionStatus],
    ) -> None:
        self.pool = pool
        self.settings = settings
        self.shared_context = shared_context
        self.metrics = metrics
        self._run_agent_loop = run_agent_loop
        self._assess_completion = assess_completion
        self.ledger: TaskLedger | None = None

    # -- Main entry point -------------------------------------------------

    async def run_delegation(
        self: DelegationRunner,
        params: DelegationParams,
    ) -> AsyncIterator[AgentEvent]:
        """Execute a delegation to a specialist agent.

        Args:
            params: Delegation parameters containing target role, task,
                brief, and depth.

        Yields:
            AgentEvents from the specialist agent.
        """
        try:
            get_completion_requirement(params.brief)
        except ValueError as exc:
            yield self._make_error_event(str(exc))
            return
        if self._is_delegation_depth_exceeded(params.depth):
            async for event in self._yield_depth_exceeded_error():
                yield event
            return
        target_role = params.target_role
        target_agent = await self._resolve_target_agent(target_role)
        if isinstance(target_agent, AgentEvent):
            yield target_agent
            return
        params.target_agent = target_agent
        loop_params = AgentLoopParams(agent=target_agent)
        try:
            with self.pool.claim_agent(target_agent, owner=loop_params):
                stream = self._run_claimed_delegation(params, loop_params)
                async with closing_event_stream(stream) as events:
                    async for event in events:
                        yield event
        except ActiveAgentError as exc:
            yield self._make_error_event(str(exc))

    async def _run_claimed_delegation(
        self,
        params: DelegationParams,
        loop_params: AgentLoopParams,
    ) -> AsyncIterator[AgentEvent]:
        """Prepare, execute and finalize while holding the target reservation."""
        target_role = params.target_role
        try:
            _prepare_execution(self, params)
        except (ValueError, AttributeError, TypeError, RuntimeError) as exc:
            yield self._make_error_event(
                f"Failed to prepare '{target_role}': {type(exc).__name__}: {exc}",
            )
            return
        yield AgentEvent(
            type=EventType.AGENT_STARTED,
            data={"agent": target_role},
            source_agent="orchestrator",
        )
        stream = self._execute_and_finalize(params, loop_params)
        primary_error: BaseException | None = None
        try:
            async for event in stream:
                yield event
        except BaseException as exc:
            primary_error = exc
            raise
        finally:
            await _close_stream(stream, primary_error=primary_error)

    async def _resolve_target_agent(
        self: DelegationRunner,
        target_role: str,
    ) -> Agent | AgentEvent:
        """Resolve a target agent or return an error event to emit."""
        target_agent_result = await self._get_target_agent_with_error_handling(target_role)
        if isinstance(target_agent_result, AgentEvent):
            return self._normalize_target_agent_error(target_agent_result, target_role)
        return target_agent_result

    def _normalize_target_agent_error(
        self: DelegationRunner,
        event: AgentEvent,
        target_role: str,
    ) -> AgentEvent:
        """Normalize non-error resolution events into explicit error events."""
        if event.type == EventType.ERROR:
            return event
        return self._make_error_event(
            f"Unexpected event type '{event.type}' when getting agent '{target_role}'",
        )

    async def _execute_and_finalize(
        self: DelegationRunner,
        params: DelegationParams,
        loop_params: AgentLoopParams | None = None,
    ) -> AsyncIterator[AgentEvent]:
        """Execute the agent loop and finalize delegation results.

        Args:
            params: Delegation parameters.

        Yields:
            AgentEvents from execution and finalization.
        """
        target_role = params.target_role
        stream = _execute_loop(self, params, loop_params)
        primary_error: BaseException | None = None
        try:
            async for event in stream:
                yield event
        except Exception as exc:  # noqa: BLE001
            primary_error = exc
            yield self._make_error_event(
                f"Failed to execute delegation for '{target_role}': {type(exc).__name__}: {exc}",
            )
            return
        except BaseException as exc:
            primary_error = exc
            raise
        finally:
            await _close_stream(stream, primary_error=primary_error)
        try:
            async with closing_event_stream(_finalize_execution(self, params)) as events:
                async for event in events:
                    yield event
        except Exception as exc:  # noqa: BLE001
            yield self._make_error_event(
                f"Failed to finalize delegation for '{target_role}': {type(exc).__name__}: {exc}",
            )

    def _make_error_event(
        self: DelegationRunner,
        message: str,
    ) -> AgentEvent:
        """Create an ERROR AgentEvent with the given message.

        Args:
            message: The error message.

        Returns:
            An ERROR AgentEvent.
        """
        return AgentEvent(
            type=EventType.ERROR,
            data=message,
            source_agent="orchestrator",
        )

    # -- Delegation sub-steps ---------------------------------------------

    def _is_delegation_depth_exceeded(self: DelegationRunner, depth: int) -> bool:
        """Check if delegation depth exceeds configured limit.

        Args:
            depth: Current recursion depth.

        Returns:
            True if depth exceeds limit, False otherwise.
        """
        return depth > self.settings.agents.max_delegation_depth

    async def _yield_depth_exceeded_error(
        self: DelegationRunner,
    ) -> AsyncIterator[AgentEvent]:
        """Yield error event for exceeded delegation depth.

        Yields:
            ERROR event with depth limit message.
        """
        yield AgentEvent(
            type=EventType.ERROR,
            data=(
                f"Error: Maximum delegation depth "
                f"({self.settings.agents.max_delegation_depth}) exceeded."
            ),
            source_agent="orchestrator",
        )

    async def _get_target_agent_with_error_handling(
        self: DelegationRunner,
        target_role: str,
    ) -> Agent | AgentEvent:
        """Get target agent with proper error handling.

        Args:
            target_role: The role ID of the specialist.

        Returns:
            Agent instance if found and valid, otherwise AgentEvent with error.
        """
        try:
            agent = self.pool.get_agent(target_role)
            error = _check_agent_protocol_compliance(agent, target_role)
        except Exception as exc:  # noqa: BLE001
            msg = f"Failed to get agent '{target_role}': {type(exc).__name__}: {exc}"
            return self._make_error_event(msg)
        else:
            if error:
                return self._make_error_event(error)
            return agent

    # -- Context preparation ----------------------------------------------

    def _inject_handoff_notes(
        self: DelegationRunner,
        brief: dict[str, Any],
        task: str = "",
        target_role: str = "",
    ) -> None:
        """Inject the most relevant prior-agent work notes into the brief.

        Entries are scored by keyword overlap with *task* and same-agent
        bonus (see :func:`_score_context_relevance`), then the top
        ``RECENT_CONTEXT_ENTRIES`` are injected.  This ensures that the
        specialist receives context that is actually relevant to the current
        task rather than just the most recent activity.

        Args:
            brief: The brief dict to update in-place.
            task: The task description being delegated (used for scoring).
            target_role: The specialist's role ID (used for scoring).
        """
        if not self.shared_context:
            return
        scored = sorted(
            self.shared_context,
            key=lambda e: _score_context_relevance(e, task, target_role),
            reverse=True,
        )
        relevant = scored[:RECENT_CONTEXT_ENTRIES]
        handoff_lines = [
            f"- **{entry['agent']}**: {entry['summary'][:MAX_SUMMARY_LENGTH]}" for entry in relevant
        ]
        handoff_notes = "### Prior agent work\n" + "\n".join(handoff_lines)
        existing_bg = brief.get("background") or ""
        brief["background"] = f"{existing_bg}\n\n{handoff_notes}" if existing_bg else handoff_notes

    def _inject_failure_context(
        self: DelegationRunner,
        brief: dict[str, Any],
        target_role: str,
    ) -> None:
        """Inject prior failure context if the agent failed before.

        Args:
            brief: The brief dict to update in-place.
            target_role: The role ID to look up prior failures for.
        """
        if not self.ledger:
            return
        prior_failures = [
            d for d in self.ledger.delegations if d.agent == target_role and d.status == "FAILED"
        ]
        if not prior_failures:
            return
        last_fail = prior_failures[-1]
        fail_note = (
            f"### Prior Attempt Failed\n"
            f"A previous delegation to you for "
            f'"{last_fail.task}" ended with status FAILED. '
            f"Avoid repeating the same approach."
        )
        existing_bg = brief.get("background") or ""
        brief["background"] = f"{existing_bg}\n\n{fail_note}" if existing_bg else fail_note

    def _prepare_delegation_context(
        self: DelegationRunner,
        target_role: str,
        brief: dict[str, Any] | None,
        task: str = "",
    ) -> dict[str, Any]:
        """Prepare context for delegation by adding handoff and failure notes.

        Args:
            target_role: The role ID of the specialist.
            brief: Original delegation brief.
            task: The task description (forwarded to relevance scoring).

        Returns:
            Updated brief with handoff notes and failure context added.
        """
        brief = dict(brief) if brief else {}
        self._inject_handoff_notes(brief, task=task, target_role=target_role)
        self._inject_failure_context(brief, target_role)
        return brief

    # -- Result processing ------------------------------------------------

    def _process_delegation_results(
        self: DelegationRunner,
        _target_role: str,
        target_agent: Agent,
        msg_start: int,
    ) -> tuple[str, dict[str, str], CompletionStatus]:
        """Process delegation results and prepare completion data.

        Args:
            target_role: The role ID of the specialist.
            target_agent: The agent that executed the delegation.
            msg_start: Index where the agent's messages started.

        Returns:
            Tuple of (summary, parsed_completion_report, completion_status).
        """
        _validate_messages_access(target_agent, msg_start)
        summary = _build_agent_summary(target_agent, msg_start)
        parsed = self._parse_completion_report(_final_completion_report(target_agent, msg_start))
        base_status = self._assess_completion(target_agent)
        status = _enrich_completion_from_report(base_status, parsed)
        return summary, parsed, status

    # -- Static helpers ---------------------------------------------------

    @staticmethod
    def _assemble_delegation_input(
        task: str,
        brief: dict[str, Any] | None,
        mission: str | None = None,
    ) -> str:
        """Build a self-contained input string from the structured delegation brief.

        Args:
            task: The core task description.
            brief: Optional structured fields from the Tech Lead.
            mission: Optional high-level mission statement for context.

        Returns:
            A formatted string ready to be passed as user input to the specialist.
        """
        return _assemble_delegation_input(task, brief, mission=mission)

    @staticmethod
    def _parse_completion_report(summary: str) -> dict[str, str]:
        """Extract structured fields from a specialist's completion report.

        Args:
            summary: Raw summary text from the specialist.

        Returns:
            Dict with extracted fields (may be empty if format not found).
        """
        return _parse_completion_report(summary)

    # -- Parallel delegation ----------------------------------------------

    async def run_parallel_delegations(
        self: DelegationRunner,
        params_list: list[DelegationParams],
    ) -> AsyncIterator[AgentEvent]:
        """Run multiple independent delegations concurrently.

        Each delegation in *params_list* is started as a separate task.
        Events from all delegations are merged into a single stream in
        arrival order.

        .. note::
            Each entry in *params_list* should target a **distinct**
            ``target_role``.  Delegating to the same agent twice in
            parallel would cause both tasks to call ``clear_history()``
            on the same agent instance, corrupting both conversations.

        Args:
            params_list: List of delegation parameters to run concurrently.

        Yields:
            AgentEvent: Events from all delegations merged by arrival order.
        """
        # Use a large but bounded buffer to prevent memory exhaustion while
        # avoiding deadlock. The consumer runs after the task group exits,
        # so producers could fill the buffer before consumption starts.
        # 10,000 events should be sufficient for most practical use cases.
        send_stream, recv_stream = anyio.create_memory_object_stream[AgentEvent](
            max_buffer_size=MAX_PARALLEL_DELEGATION_BUFFER,
        )

        async def _run_one(params: DelegationParams) -> None:
            """Run a single delegation and forward its events to the stream."""
            async for event in self.run_delegation(params):
                await send_stream.send(event)

        async with anyio.create_task_group() as tg:
            for p in params_list:
                tg.start_soon(_run_one, p)

        await send_stream.aclose()

        async with recv_stream:
            async for event in recv_stream:
                yield event
