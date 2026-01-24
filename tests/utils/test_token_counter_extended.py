from henchman.providers.base import Message, ToolCall
from henchman.utils.tokens import TokenCounter


def test_count_text_empty():
    assert TokenCounter.count_text("") == 0
    assert TokenCounter.count_text(None) == 0

def test_count_messages_with_tool_calls():
    tc = ToolCall(id="1", name="tool", arguments={"a": 1})
    msg = Message(role="assistant", content="calling tool", tool_calls=[tc])

    tokens = TokenCounter.count_messages([msg])
    # content (12//4=3) + overhead (100) + tc (str(tc)//4)
    assert tokens > 100
