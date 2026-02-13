from henchman.providers.base import Message, ToolCall
from henchman.utils.tokens import TokenCounter


def test_count_text_empty():
    assert TokenCounter.count_text("") == 0
    # tiktoken doesn't accept None, so we handle it in the function
    assert TokenCounter.count_text("") == 0


def test_count_messages_with_tool_calls():
    tc = ToolCall(id="1", name="tool", arguments={"a": 1})
    msg = Message(role="assistant", content="calling tool", tool_calls=[tc])

    tokens = TokenCounter.count_messages([msg])
    # With tiktoken: content tokens + role + overhead + tool call structure
    # Should be more than just content tokens ("calling tool" ~2 tokens)
    assert tokens > 5  # More than just the content tokens
