"""Test for reasoning_content bug in intelligent context manager.

This test demonstrates the bug where reasoning_content is lost during
message truncation.
"""

from henchman.providers.base import Message
from henchman.utils.intelligent_context import IntelligentContextManager


def test_reasoning_content_preserved_when_no_truncation_needed():
    """Test that reasoning_content is preserved when message doesn't need truncation."""
    # Create a message with reasoning_content
    original_message = Message(
        role="assistant",
        content="This is a short message that doesn't need truncation.",
        reasoning_content="I think this is a short message because it has few tokens."
    )

    # Create config with high max_tokens so no truncation needed
    from henchman.utils.intelligent_context_config import IntelligentContextConfig
    config = IntelligentContextConfig(max_tokens=8000, safety_limit_ratio=0.75)
    manager = IntelligentContextManager(config=config)

    # This message shouldn't need truncation (it's short)
    result = manager.enforce_safety_limits([original_message])

    assert len(result) == 1
    assert result[0].reasoning_content == original_message.reasoning_content
    assert result[0].content == original_message.content
    assert result[0].role == original_message.role


def test_reasoning_content_lost_when_truncation_needed():
    """Test that reasoning_content is lost when message needs truncation (THE BUG)."""
    # Create a long message that will need truncation
    # Make it very long to ensure it exceeds safety limit
    long_content = "This is a very long message " * 1000  # ~25,000 chars
    original_message = Message(
        role="assistant",
        content=long_content,
        reasoning_content="I'm thinking about this long message and its content."
    )

    # Create config with low max_tokens to force truncation
    from henchman.utils.intelligent_context_config import IntelligentContextConfig
    config = IntelligentContextConfig(max_tokens=1000, safety_limit_ratio=0.75)
    manager = IntelligentContextManager(config=config)

    # This message should need truncation (it's very long)
    result = manager.enforce_safety_limits([original_message])

    assert len(result) == 1

    # THE BUG: reasoning_content should be preserved but it's None
    # This test will FAIL with the current code
    assert result[0].reasoning_content == original_message.reasoning_content, \
        f"reasoning_content was lost! Expected: {original_message.reasoning_content}, Got: {result[0].reasoning_content}"

    # Content should be truncated (shorter than original)
    assert len(result[0].content or "") < len(original_message.content or "")
    assert result[0].role == original_message.role


def test_reasoning_content_with_tool_calls():
    """Test reasoning_content preservation with tool calls."""
    from henchman.providers.base import ToolCall

    original_message = Message(
        role="assistant",
        content="I need to call a tool to get information.",
        reasoning_content="I should use the get_info tool because the user asked for data.",
        tool_calls=[
            ToolCall(
                id="call_123",
                name="get_info",
                arguments={"query": "test"}
            )
        ]
    )

    # Create config with low max_tokens to force truncation
    from henchman.utils.intelligent_context_config import IntelligentContextConfig
    config = IntelligentContextConfig(max_tokens=1000, safety_limit_ratio=0.75)
    manager = IntelligentContextManager(config=config)

    # Create a long content to force truncation
    long_content = "Very long content " * 1000
    original_message.content = long_content

    result = manager.enforce_safety_limits([original_message])

    assert len(result) == 1

    # THE BUG: reasoning_content should be preserved
    assert result[0].reasoning_content == original_message.reasoning_content, \
        f"reasoning_content was lost even with tool calls! Expected: {original_message.reasoning_content}, Got: {result[0].reasoning_content}"

    # Tool calls should be preserved
    assert result[0].tool_calls == original_message.tool_calls
