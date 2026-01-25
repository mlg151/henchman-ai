# 400 Error Analysis: "Messages with role 'tool' must be a response to a preceding message with 'tool_calls'"

## Root Cause Identified

**Primary Issue**: The context compaction algorithm in `ContextCompactor.compact()` fails to preserve atomic tool call sequences.

**Location**: `src/henchman/utils/compaction.py`, lines 48-57

**The Bug**: When pruning messages to fit token limits, the algorithm:
1. Treats each message independently
2. Can preserve tool messages while discarding their parent assistant messages
3. Creates invalid sequences that violate OpenAI API rules

## Detailed Analysis

### How the Bug Occurs
1. Conversation grows beyond token limit
2. Compaction starts pruning from oldest messages
3. Algorithm uses "keep from end" approach
4. If token budget runs out:
   - Recent tool messages might be kept
   - Older assistant messages might be discarded
   - Result: Tool messages without preceding assistant → 400 error

### Evidence from Tests
Test `test_compaction_with_multiple_tools()` shows:
- Original: [user, assistant(with tools), tool, tool, assistant]
- After compaction: Can become [tool, tool, assistant] (INVALID!)

### OpenAI API Requirements Violated
1. **Sequence rule**: Tool messages must immediately follow assistant with tool_calls
2. **ID rule**: Tool message tool_call_id must match assistant's tool call ID
3. **Atomicity rule**: Tool call sequences cannot be split

## Immediate Workaround

Disable automatic compaction until fix is implemented:
```python
# In agent.py, increase max_tokens to avoid compaction
agent = Agent(provider=provider, max_tokens=100000)
```

## Recommended Fix

### 1. Fix Compaction Algorithm
Modify `ContextCompactor.compact()` to:
- Group messages into atomic sequences
- Preserve or discard entire tool call sequences
- Never split assistant → tool message chains

### 2. Add Sequence Validation
Add validation before API calls:
```python
def validate_message_sequence(messages: list[Message]) -> bool:
    # Check tool messages follow assistant with tool_calls
    # Check tool_call_id matching
    # Check no orphaned tool messages
```

### 3. Improve Error Handling
Add detailed error messages showing:
- Invalid message sequence
- Missing tool call IDs
- Suggested fixes

## Files to Modify

1. `src/henchman/utils/compaction.py` - Fix compaction logic
2. `src/henchman/core/agent.py` - Add validation
3. `tests/utils/test_compaction.py` - Add tool sequence tests
4. `tests/core/test_agent.py` - Add validation tests

## Testing Strategy

1. **Unit tests**: Compaction with tool sequences
2. **Integration tests**: Full agent flow with compaction
3. **Edge cases**: Multiple tools, empty results, mixed sequences
4. **Regression tests**: Existing functionality unchanged

## Timeline

**Immediate** (1-2 days): Fix compaction algorithm
**Short-term** (1 day): Add validation and error handling
**Long-term** (ongoing): Comprehensive testing and monitoring

## Status

**Severity**: High - Breaks core functionality
**Priority**: P1 - Fix immediately
**Impact**: All users with long conversations using tools
