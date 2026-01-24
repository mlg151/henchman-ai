from henchman.providers.base import Message
from henchman.utils.compaction import ContextCompactor
from henchman.utils.tokens import TokenCounter


def test_token_counter():
    text = "12345678" # 8 chars
    assert TokenCounter.count_text(text) == 2

    msgs = [Message(role="user", content=text)]
    assert TokenCounter.count_messages(msgs) == 2

def test_compaction():
    # Setup messages
    sys_msg = Message(role="system", content="sys_1234") # 2 tokens (8 chars)
    old_msg = Message(role="user", content="old_1234") # 2 tokens
    mid_msg = Message(role="assistant", content="mid_1234") # 2 tokens
    last_msg = Message(role="user", content="last1234") # 2 tokens

    msgs = [sys_msg, old_msg, mid_msg, last_msg]
    # Total 8 tokens

    # Compact to 6 tokens
    # Should keep sys (2) + last (2).
    # Budget = 6 - 4 = 2.
    # Candidates: mid, old.
    # Reversed candidates: mid, old.
    # Try mid (2): fits. budget 0.
    # Try old (2): fails.
    # Result: sys, mid, last.

    compactor = ContextCompactor(max_tokens=6)
    compacted = compactor.compact(msgs)

    assert len(compacted) == 3
    assert compacted[0] == sys_msg
    assert compacted[-1] == last_msg
    assert mid_msg in compacted
    assert old_msg not in compacted

def test_compaction_no_pruning_needed():
    msgs = [Message(role="user", content="short")]
    compactor = ContextCompactor(max_tokens=100)
    assert compactor.compact(msgs) == msgs

def test_compaction_last_not_user():
    sys = Message(role="system", content="sys_1234")
    msg1 = Message(role="user", content="old_1234")
    msg2 = Message(role="assistant", content="last1234")

    msgs = [sys, msg1, msg2]
    # Compact to 2 tokens (8 chars) -> budget for candidates.
    # system (2) is kept. msg2 is last but NOT user, so it's a candidate?
    # Wait, my logic: critical_msgs only adds if role == user.
    # So msg2 is a candidate.
    # budget = 2 - 2(sys) = 0.
    # msg2 will be pruned if it doesn't fit.

    compactor = ContextCompactor(max_tokens=2)
    compacted = compactor.compact(msgs)
    assert len(compacted) == 1
    assert compacted[0] == sys

def test_compaction_full_budget():
    sys = Message(role="system", content="1234")
    msg1 = Message(role="user", content="1234")
    msg2 = Message(role="user", content="12345678")

    msgs = [sys, msg1, msg2]
    # budget = 2 (8 chars)
    # sys(1) + msg2(2) = 3 > budget.
    # Reversed candidates: [msg1]
    # msg1 (1) fits.
    # Used = 1.

    compactor = ContextCompactor(max_tokens=2)
    # This should trigger budget limit
    compacted = compactor.compact(msgs)
    assert len(compacted) == 2
