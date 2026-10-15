"""Message sequence validation for OpenAI API compatibility."""

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from henchman.providers.base import Message

logger = logging.getLogger(__name__)


def validate_message_sequence(messages: list["Message"]) -> None:
    """Validate that a message sequence follows OpenAI API rules.

    OpenAI requires:
    1. An assistant message with tool_calls must be immediately followed
       by tool messages for ALL of its tool_call_ids (no other roles in between).
    2. Tool messages must have a tool_call_id matching the preceding assistant.
    3. Every tool_call must have exactly one tool response.

    Args:
        messages: List of Message objects to validate.

    Raises:
        ValueError: If the sequence violates OpenAI API rules.

    Returns:
        None
    """
    i = 0
    while i < len(messages):
        msg = messages[i]

        if msg.role == "assistant" and msg.tool_calls:
            # This assistant expects tool responses immediately following
            expected_ids = {tc.id for tc in msg.tool_calls}
            seen_ids: set[str] = set()
            j = i + 1

            # Consume all immediately-following tool messages
            while j < len(messages) and messages[j].role == "tool":
                tool_msg = messages[j]
                if tool_msg.tool_call_id not in expected_ids:
                    error_message = (
                        f"Tool message at index {j} has tool_call_id "
                        f"'{tool_msg.tool_call_id}' which doesn't match any "
                        f"tool call from assistant at index {i}. "
                        f"Expected one of: {list(expected_ids)}"
                    )
                    raise ValueError(
                        error_message,
                    )
                if tool_msg.tool_call_id in seen_ids:
                    error_message = (
                        f"Duplicate tool response for tool_call_id "
                        f"'{tool_msg.tool_call_id}' at index {j}."
                    )
                    raise ValueError(
                        error_message,
                    )
                seen_ids.add(tool_msg.tool_call_id)
                j += 1

            missing = expected_ids - seen_ids
            if missing:
                error_message = (
                    f"Assistant message at index {i} has tool calls without "
                    f"responses: {list(missing)}. "
                    "All tool calls must be followed by tool messages with "
                    "matching IDs."
                )
                raise ValueError(
                    error_message,
                )
            # Skip past the tool messages we consumed
            i = j
            continue

        if msg.role == "tool":
            # A tool message outside of an assistant+tool block is invalid
            error_message = (
                f"Tool message at index {i} doesn't follow any assistant "
                "message with tool_calls. "
                "Tool messages must follow assistant messages that have "
                "tool_calls."
            )
            raise ValueError(
                error_message,
            )

        i += 1


def _gather_tool_messages_for_assistant(
    messages: list["Message"],
    start_index: int,
    expected_ids: set[str],
) -> tuple[list["Message"], int, bool]:
    """Gather immediately-following tool messages for an assistant.

    Returns:
        Tuple of (list of valid tool messages, next index to process, was_repaired).
    """
    tool_msgs: list[Message] = []
    j = start_index
    repaired = False
    while j < len(messages) and messages[j].role == "tool":
        if messages[j].tool_call_id in expected_ids:
            tool_msgs.append(messages[j])
        else:
            # Orphaned tool message — drop it
            repaired = True
            logger.warning(
                "Repair: dropping orphaned tool message at index %d (tool_call_id=%s)",
                j,
                messages[j].tool_call_id,
            )
        j += 1
    return tool_msgs, j, repaired


def repair_message_sequence(messages: list["Message"]) -> list["Message"]:
    """Repair a broken message sequence so it follows OpenAI API rules.

    This removes orphaned tool messages (those without a matching preceding
    assistant message with tool_calls) and strips tool_calls from assistant
    messages whose tool responses are missing or incomplete.

    Args:
        messages: The potentially broken message sequence.

    Returns:
        A repaired message sequence that passes validation.
    """
    from henchman.providers.base import Message as Msg

    if not messages:
        return messages

    result: list[Message] = []
    repaired = False
    i = 0

    while i < len(messages):
        msg = messages[i]

        if msg.role == "assistant" and msg.tool_calls:
            expected_ids = {tc.id for tc in msg.tool_calls}
            tool_msgs, j, was_rep = _gather_tool_messages_for_assistant(
                messages, i + 1, expected_ids,
            )
            repaired = repaired or was_rep

            seen_ids = {tm.tool_call_id for tm in tool_msgs}
            missing = expected_ids - seen_ids

            if missing:
                # Incomplete tool responses — strip tool_calls entirely
                repaired = True
                logger.warning(
                    "Repair: assistant at index %d missing tool responses for "
                    "%s — stripping tool_calls",
                    i,
                    list(missing),
                )
                result.append(
                    Msg(
                        role="assistant",
                        content=msg.content or "(tool calls removed during repair)",
                        tool_calls=None,
                        tool_call_id=None,
                    ),
                )
            else:
                # Complete — keep assistant + tool messages
                result.append(msg)
                result.extend(tool_msgs)

            i = j
            continue

        if msg.role == "tool":
            # Tool message outside of an assistant+tool block — orphaned
            repaired = True
            logger.warning(
                "Repair: dropping orphaned tool message at index %d "
                "(tool_call_id=%s, no preceding assistant with tool_calls)",
                i,
                msg.tool_call_id,
            )
            i += 1
            continue

        # Normal message (user, system, assistant without tool_calls)
        result.append(msg)
        i += 1

    if repaired:
        logger.warning(
            "Message sequence repaired: %d → %d messages",
            len(messages),
            len(result),
        )

    return result


def is_valid_message_sequence(messages: list["Message"]) -> bool:
    """Check if a message sequence follows OpenAI API rules.

    Args:
        messages: List of Message objects to validate.

    Returns:
        True if the sequence is valid, False otherwise.
    """
    try:
        validate_message_sequence(messages)
    except ValueError:
        return False
    else:
        return True


def format_message_sequence_for_debug(messages: list["Message"]) -> str:
    """Format message sequence for debugging purposes.

    Args:
        messages: List of Message objects to format.

    Returns:
        A formatted string showing the message sequence.
    """
    lines = []
    for i, msg in enumerate(messages):
        tool_info = ""
        if msg.tool_calls:
            tool_info = f" tool_calls={[tc.id for tc in msg.tool_calls]}"
        elif msg.tool_call_id:
            tool_info = f" tool_call_id={msg.tool_call_id}"

        lines.append(f"{i:3d}: {msg.role:10s} content={repr(msg.content)[:50]}{tool_info}")

    return "\n".join(lines)
