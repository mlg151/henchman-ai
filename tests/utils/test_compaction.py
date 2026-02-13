from henchman.providers.base import Message
from henchman.utils.compaction import ContextCompactor
from henchman.utils.tokens import TokenCounter


def test_token_counter():
    text = "12345678"  # 8 chars
    # tiktoken counts actual tokens (varies by content)
    # Simple digits should be ~2-3 tokens
    tokens = TokenCounter.count_text(text)
    assert tokens >= 1 and tokens <= 5

    msgs = [Message(role="user", content=text)]
    # Messages include overhead for structure
    msg_tokens = TokenCounter.count_messages(msgs)
    assert msg_tokens > tokens  # Should include overhead


def test_compaction():
    # Setup messages with longer content for tiktoken
    sys_msg = Message(role="system", content="You are a helpful assistant.")
    old_msg = Message(role="user", content="This is an old message that should be pruned.")
    mid_msg = Message(role="assistant", content="This is a response to the old message.")
    last_msg = Message(role="user", content="This is the latest message that should be kept.")

    msgs = [sys_msg, old_msg, mid_msg, last_msg]

    # Get actual token count
    total_tokens = TokenCounter.count_messages(msgs)

    # Compact to half the tokens - should drop old_msg
    compactor = ContextCompactor(max_tokens=total_tokens // 2)
    compacted = compactor.compact(msgs)

    # System and last user should always be preserved
    assert sys_msg in compacted
    assert compacted[-1] == last_msg
    # The old message should be pruned to make room
    assert len(compacted) < len(msgs)


def test_compaction_no_pruning_needed():
    msgs = [Message(role="user", content="short")]
    compactor = ContextCompactor(max_tokens=100)
    assert compactor.compact(msgs) == msgs


def test_compaction_last_not_user():
    sys = Message(role="system", content="You are a helpful assistant.")
    msg1 = Message(role="user", content="This is a user message.")
    msg2 = Message(role="assistant", content="This is an assistant response.")

    msgs = [sys, msg1, msg2]

    # Get system message tokens
    sys_tokens = TokenCounter.count_messages([sys])

    # Compact to just system message size - should drop msg1 and msg2
    compactor = ContextCompactor(max_tokens=sys_tokens + 5)
    compacted = compactor.compact(msgs)
    # Should at minimum keep system message
    assert sys in compacted


def test_compaction_full_budget():
    sys = Message(role="system", content="System prompt.")
    msg1 = Message(role="user", content="First user message.")
    msg2 = Message(role="user", content="Second user message which is longer.")

    msgs = [sys, msg1, msg2]

    # Compact with a budget that forces some pruning
    total_tokens = TokenCounter.count_messages(msgs)
    compactor = ContextCompactor(max_tokens=total_tokens - 10)
    compacted = compactor.compact(msgs)

    # System should always be preserved
    assert sys in compacted
    # Last message should be preserved when it's a user message
    assert msg2 in compacted

    # Test with a tight budget that requires dropping middle message
    # but can still fit system + last user with some truncation
    sys_tokens = TokenCounter.count_messages([sys])
    msg2_tokens = TokenCounter.count_messages([msg2])
    tight_budget = sys_tokens + msg2_tokens + 5  # Just enough for sys + msg2
    compactor = ContextCompactor(max_tokens=tight_budget)
    compacted = compactor.compact(msgs)

    # Should have system and last user, possibly msg1 dropped
    assert any(m.role == "system" for m in compacted)
    # Last user message should be preserved
    assert any("Second user" in (m.content or "") for m in compacted)
