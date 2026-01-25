# Compaction Algorithm Bug Analysis

## The Problem
The compaction algorithm in `ContextCompactor.compact()` has a critical flaw when handling tool call sequences.

## Current Algorithm (lines 31-60):

1. **Separate messages**:
   - System messages (always kept)
   - Critical messages (last user message, if any)
   - Candidates (everything else)

2. **Pruning logic** (lines 48-57):
   ```python
   kept = []
   used = 0
   for msg in reversed(candidates):  # Start from the END
       cost = TokenCounter.count_messages([msg])
       if used + cost <= budget:
           kept.append(msg)
           used += cost
       else:
           break
   ```

3. **Reconstruct order** (line 60):
   ```python
   result = system_msgs + list(reversed(kept)) + critical_msgs
   ```

## The Bug

When iterating through `reversed(candidates)`, the algorithm:
1. Starts from the MOST RECENT candidate message
2. Adds messages to `kept` list in REVERSE order (most recent first)
3. Then reverses `kept` to restore chronological order

**BUT**: This breaks tool call sequences!

## Example Failure

Original sequence:
```
0: user: "Do several things"
1: assistant: (with tool_calls [call_1, call_2])
2: tool: (result for call_1)
3: tool: (result for call_2)
4: assistant: "All done"
```

Candidates = [0, 1, 2, 3, 4] (all messages except system)

Iteration (reversed order):
- msg 4: assistant "All done" → kept = [4]
- msg 3: tool (call_2) → kept = [4, 3]
- msg 2: tool (call_1) → kept = [4, 3, 2]
- msg 1: assistant (with tool_calls) → kept = [4, 3, 2, 1]
- msg 0: user → kept = [4, 3, 2, 1, 0]

After reversing: [0, 1, 2, 3, 4] ← Looks correct!

**BUT**: The algorithm stops when budget is full!

If tokens are limited, it might keep:
- msg 4: assistant "All done" → kept = [4]
- msg 3: tool (call_2) → kept = [4, 3]
- msg 2: tool (call_1) → kept = [4, 3, 2]
- STOP (budget full)

After reversing: [2, 3, 4] = [tool(call_1), tool(call_2), assistant]

**This is INVALID**: Tool messages without their preceding assistant!

## The Root Cause

The algorithm treats each message independently, not considering:
1. **Message dependencies**: Tool messages DEPEND on their preceding assistant message
2. **Atomic sequences**: Tool call sequences (assistant → tool(s)) are ATOMIC units
3. **Partial preservation**: Cannot preserve tool messages without their assistant

## Fix Required

The compaction algorithm must:
1. **Identify atomic sequences**: Group assistant messages with their tool responses
2. **Preserve or discard entire sequences**: Never split tool call sequences
3. **Maintain dependencies**: Keep message dependencies intact

## Proposed Fix

```python
def compact(self, messages: list['Message']) -> list['Message']:
    """Compact messages to fit within max_tokens.
    
    Always preserves system messages and the last user message.
    Prunes from the beginning of history (after system prompts).
    Preserves tool call sequences as atomic units.
    """
    if not messages:
        return []
    
    current_tokens = TokenCounter.count_messages(messages)
    if current_tokens <= self.max_tokens:
        return messages
    
    # 1. Group messages into atomic sequences
    sequences = self._group_into_sequences(messages)
    
    # 2. Separate system messages and critical last message
    system_msgs = [m for m in messages if m.role == "system"]
    critical_seq = None
    if messages[-1].role == "user":
        critical_seq = sequences[-1] if sequences else None
    
    # 3. Calculate budget
    fixed_cost = TokenCounter.count_messages(system_msgs)
    if critical_seq:
        fixed_cost += TokenCounter.count_messages(critical_seq.messages)
    budget = self.max_tokens - fixed_cost
    
    if budget <= 0:
        return system_msgs + (critical_seq.messages if critical_seq else [])
    
    # 4. Keep sequences from end until budget full
    kept_seqs = []
    used = 0
    for seq in reversed(sequences):
        if critical_seq and seq is critical_seq:
            continue  # Already accounted for
        
        seq_cost = TokenCounter.count_messages(seq.messages)
        if used + seq_cost <= budget:
            kept_seqs.append(seq)
            used += seq_cost
        else:
            break
    
    # 5. Reconstruct
    result = system_msgs.copy()
    for seq in reversed(kept_seqs):  # Restore chronological order
        result.extend(seq.messages)
    if critical_seq:
        result.extend(critical_seq.messages)
    
    return result

class MessageSequence:
    """Represents an atomic sequence of messages."""
    
    def __init__(self, messages: list['Message']):
        self.messages = messages
    
    @property
    def is_tool_sequence(self) -> bool:
        """Check if this is a tool call sequence."""
        return any(msg.role == "assistant" and msg.tool_calls for msg in self.messages)

def _group_into_sequences(self, messages: list['Message']) -> list['MessageSequence]:
    """Group messages into atomic sequences.
    
    Rules:
    1. Each user message starts a new sequence
    2. Assistant messages with tool_calls include all following tool messages
    3. Other messages continue the current sequence
    """
    sequences = []
    current_seq = []
    
    i = 0
    while i < len(messages):
        msg = messages[i]
        current_seq.append(msg)
        
        # Check if this starts a tool call sequence
        if msg.role == "assistant" and msg.tool_calls:
            # Include all following tool messages for these tool calls
            tool_call_ids = {tc.id for tc in msg.tool_calls}
            j = i + 1
            while j < len(messages) and messages[j].role == "tool":
                if messages[j].tool_call_id in tool_call_ids:
                    current_seq.append(messages[j])
                    j += 1
                else:
                    break
            i = j
        else:
            i += 1
        
        # Start new sequence on user message (except first in conversation)
        if msg.role == "user" and i < len(messages):
            sequences.append(MessageSequence(current_seq))
            current_seq = []
    
    if current_seq:
        sequences.append(MessageSequence(current_seq))
    
    return sequences
```

## Conclusion
The current compaction algorithm is fundamentally broken for tool call sequences. It must be fixed to preserve atomic message sequences, especially assistant → tool message chains.
