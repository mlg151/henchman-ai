"""Message sequence validation for OpenAI API compatibility."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from henchman.providers.base import Message


def validate_message_sequence(messages: list['Message']) -> None:
    """Validate that a message sequence follows OpenAI API rules.
    
    Raises:
        ValueError: If the sequence violates OpenAI API rules.
    """
    # Track which tool calls have been responded to
    pending_tool_calls = {}
    
    for i, msg in enumerate(messages):
        if msg.role == "tool":
            # Tool messages must follow an assistant with tool_calls
            if i == 0:
                raise ValueError(
                    f"Tool message at index {i} has no preceding message. "
                    "Tool messages must follow assistant messages with tool_calls."
                )
            
            # Find the nearest preceding assistant message with tool calls
            assistant_idx = -1
            for j in range(i-1, -1, -1):
                if messages[j].role == "assistant" and messages[j].tool_calls:
                    assistant_idx = j
                    break
            
            if assistant_idx == -1:
                raise ValueError(
                    f"Tool message at index {i} doesn't follow any assistant message with tool_calls. "
                    "Tool messages must follow assistant messages that have tool_calls."
                )
            
            # Check if this tool call ID matches one of the assistant's tool calls
            assistant_msg = messages[assistant_idx]
            tool_call_ids = {tc.id for tc in assistant_msg.tool_calls}
            
            if msg.tool_call_id not in tool_call_ids:
                raise ValueError(
                    f"Tool call ID {msg.tool_call_id} at index {i} doesn't match "
                    f"any tool call from assistant at index {assistant_idx}. "
                    f"Assistant tool call IDs: {list(tool_call_ids)}"
                )
            
            # Track that this tool call has been responded to
            if assistant_idx not in pending_tool_calls:
                pending_tool_calls[assistant_idx] = set(tool_call_ids)
            
            pending_tool_calls[assistant_idx].discard(msg.tool_call_id)
    
    # Check that all assistant tool calls have corresponding tool responses
    for i, msg in enumerate(messages):
        if msg.role == "assistant" and msg.tool_calls:
            tool_call_ids = {tc.id for tc in msg.tool_calls}
            
            # Remove tool calls that have been responded to
            if i in pending_tool_calls:
                remaining = pending_tool_calls[i]
                if remaining:
                    raise ValueError(
                        f"Assistant message at index {i} has tool calls without responses: "
                        f"{list(remaining)}. "
                        "All tool calls must be followed by tool messages with matching IDs."
                    )


def is_valid_message_sequence(messages: list['Message']) -> bool:
    """Check if a message sequence follows OpenAI API rules.
    
    Returns:
        True if the sequence is valid, False otherwise.
    """
    try:
        validate_message_sequence(messages)
        return True
    except ValueError:
        return False


def format_message_sequence_for_debug(messages: list['Message']) -> str:
    """Format message sequence for debugging purposes.
    
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

