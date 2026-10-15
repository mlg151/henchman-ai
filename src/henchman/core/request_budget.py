"""Project a conversation into a bounded request without altering its evidence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from henchman.providers.base import ContextTooLargeError, Message, ModelProvider, ToolDeclaration
from henchman.utils.tokens import TokenCounter
from henchman.utils.validation import is_valid_message_sequence


@dataclass(frozen=True)
class PreparedRequest:
    """One projection and the exact output options reserved for its provider call."""

    messages: list[Message]
    tools: list[ToolDeclaration]
    request_options: dict[str, Any]
    estimated_input_tokens: int
    output_tokens: int
    compacted: bool


def _protection_start(messages: list[Message], requested: int) -> int:
    if 0 <= requested < len(messages):
        return requested
    # Standalone continuations may have no TurnState. Keep the latest exchange.
    return next(
        (i for i in range(len(messages) - 1, -1, -1) if messages[i].role == "user"),
        0,
    )


def prepare_request(
    provider: ModelProvider,
    messages: list[Message],
    tools: list[ToolDeclaration],
    *,
    context_window: int,
    conversation_limit: int,
    protect_from_index: int,
) -> PreparedRequest:
    """Drop old atomic groups until input plus reserved output fits the estimate.

    System instructions and the complete current turn are mandatory. The
    conversation limit is a soft target for these messages; the selected request
    capacity is checked separately. Neither message bodies nor history are edited.
    Provider token estimates cannot guarantee a server's tokenizer/template count.
    """
    if type(context_window) is not int or context_window <= 0:
        raise ValueError("Context window must be a positive integer")
    if not is_valid_message_sequence(messages):
        raise ValueError("Cannot budget an invalid message sequence")
    output = provider.prepare_output_budget(min(4096, max(1, context_window // 4)))
    start = _protection_start(messages, protect_from_index)
    # Only remove prefixes at user-turn boundaries. Existing compaction grouping
    # ends groups on user messages, which could retain an answer without its task.
    cutoffs = [0, *(i for i in range(1, start) if messages[i].role == "user"), start]
    model = getattr(provider, "default_model", None)

    for cutoff in dict.fromkeys(cutoffs):
        projection = [
            message for i, message in enumerate(messages)
            if message.role == "system" or i >= cutoff
        ]
        input_tokens = provider.estimate_input_tokens(projection, tools)
        fits = input_tokens + output.output_tokens <= context_window
        target_met = TokenCounter.count_messages(projection, model=model) <= conversation_limit
        if fits and (target_met or cutoff == start):
            if not is_valid_message_sequence(projection):
                raise ValueError("Context projection would break a tool-call sequence")
            return PreparedRequest(
                projection, tools, output.request_options, input_tokens,
                output.output_tokens, len(projection) < len(messages),
            )

    raise ContextTooLargeError(
        f"Required request exceeds the context window ({context_window} tokens): "
        f"estimated input {input_tokens} + reserved output {output.output_tokens}. "
        "Reduce the current prompt, tool results, tool schemas or output cap, "
        "or select a larger context length."
    )
