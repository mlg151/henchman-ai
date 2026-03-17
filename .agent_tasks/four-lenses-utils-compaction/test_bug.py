"""Test to demonstrate the bug in _truncate_protected_zone_messages."""

from henchman.providers.base import Message, ToolCall
from henchman.utils.compaction import ContextCompactor
from henchman.utils.tokens import TokenCounter

def test_truncation_underestimates_token_reduction():
    """Test that token reduction is underestimated due to integer division."""
    # Create a compactor with small protected zone
    compactor = ContextCompactor(max_tokens=150, max_protected_ratio=0.3)
    # max_protected_tokens = 150 * 0.3 = 45
    
    # Create protected messages that exceed the budget
    # Tool message with content that will be truncated
    tool_msg = Message(
        role="tool", 
        content="x" * 600,  # 600 chars, ~150 tokens at 4 chars/token
        tool_call_id="tc1"
    )
    
    messages = [
        Message(role="system", content="System prompt"),
        Message(role="user", content="User request"),
        Message(
            role="assistant", 
            content="I'll help",
            tool_calls=[ToolCall(id="tc1", name="test", arguments={})]
        ),
        tool_msg,  # Protected (from index 2)
    ]
    
    total_tokens = TokenCounter.count_messages(messages)
    print(f"Total tokens: {total_tokens}")
    print(f"Max tokens: {compactor.max_tokens}")
    print(f"Max protected tokens: {compactor.max_protected_tokens}")
    
    # The protected zone (assistant + tool) should be truncated
    # But the bug might cause it to remain over budget
    
    result = compactor.compact(messages, protect_from_index=2)
    result_tokens = TokenCounter.count_messages(result)
    
    print(f"\nResult tokens: {result_tokens}")
    print(f"Within max_tokens? {result_tokens <= compactor.max_tokens}")
    
    # Check if protected zone was properly truncated
    protected_msgs = result[2:]  # From protect_from_index=2
    protected_tokens = TokenCounter.count_messages(protected_msgs)
    print(f"Protected zone tokens: {protected_tokens}")
    print(f"Within max_protected_tokens? {protected_tokens <= compactor.max_protected_tokens}")
    
    # The bug: integer division in trimmed_tokens calculation
    # trimmed_tokens = (len(content) - len(truncated_msg.content or "")) // CHARS_PER_TOKEN_ESTIMATE
    # If we trim 7 chars: 7 // 4 = 1 token, but 7 chars might be 2 tokens
    # Cumulative error could keep protected zone over budget

if __name__ == "__main__":
    test_truncation_underestimates_token_reduction()