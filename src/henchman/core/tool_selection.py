"""Expose context-sized tool schemas while preserving the registered catalog."""

from __future__ import annotations

import logging

from henchman.core.request_budget import PreparedRequest, prepare_request
from henchman.providers.base import ContextTooLargeError, Message, ModelProvider
from henchman.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)

# Discovery handles the remaining catalog; these keep ordinary coding actionable.
_CORE_TOOLS = (
    "delegate_task", "ask_user", "read_file", "ls", "glob", "grep",
    "shell", "edit_file", "write_file", "python_exec",
    "task_get", "task_list", "task_output", "task_stop", "goal_status",
)


def prepare_agent_request(
    provider: ModelProvider,
    messages: list[Message],
    registry: ToolRegistry,
    *,
    context_window: int,
    conversation_limit: int,
    protect_from_index: int,
) -> PreparedRequest:
    """Try all declarations, then bounded discovery if the required catalog fails.

    Searched schemas are required, so a requested tool that cannot fit produces
    explicit guidance. Optional core tools are included only when the identical
    request accounting permits them. Neither tool permissions nor history change.
    """
    declarations = registry.get_declarations()
    options = {
        "context_window": context_window,
        "conversation_limit": conversation_limit,
        "protect_from_index": protect_from_index,
    }
    try:
        return prepare_request(provider, messages, declarations, **options)
    except ContextTooLargeError:
        if not registry.supports_tool_discovery:
            raise

    by_name = {tool.name: tool for tool in declarations}
    provider_required = provider.required_tool_names()
    if any(name not in by_name for name in provider_required):
        raise ValueError("Configured tool_choice references a tool unavailable in this agent scope")
    required = list(dict.fromkeys([
        "tool_search", *provider_required, *registry.discovered_tools,
    ]))
    selected = [by_name[name] for name in required if name in by_name]
    request = prepare_request(provider, messages, selected, **options)
    for name in _CORE_TOOLS:
        if name not in by_name or name in required:
            continue
        candidate = [*selected, by_name[name]]
        try:
            expanded = prepare_request(provider, messages, candidate, **options)
        except ContextTooLargeError:
            continue
        selected, request = candidate, expanded
    logger.debug(
        "Context-sized tool catalog: %s of %s schemas, estimated input %s, output %s",
        len(request.tools), len(declarations), request.estimated_input_tokens,
        request.output_tokens,
    )
    return request
