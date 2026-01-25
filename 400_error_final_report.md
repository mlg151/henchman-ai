# 400 Error Investigation: Final Report

## Executive Summary

The 400 error "Messages with role 'tool' must be a response to a preceding message with 'tool_calls'" is caused by a bug in the context compaction algorithm. The algorithm fails to preserve atomic tool call sequences, resulting in invalid message sequences being sent to the OpenAI API.

## Root Cause

### Primary Issue: Broken Context Compaction
**File**: `src/henchman/utils/compaction.py`
**Method**: `ContextCompactor.compact()`

The compaction algorithm:
1. Treats messages as independent units
2. Prunes based on token count without considering message dependencies
3. Can preserve tool messages while discarding their corresponding assistant messages
4. Creates invalid sequences that violate OpenAI API rules

### Secondary Issues
1. **No message sequence validation**: No validation of tool call sequences before sending to API
2. **Poor error handling**: Generic 400 errors without detailed diagnostics
3. **Insufficient testing**: Lack of tests for compaction with tool call sequences

## Technical Details

### OpenAI API Requirements
For tool calls, the API requires:
1. **Strict sequencing**: Assistant message with `tool_calls` → Tool message(s) → Assistant response
2. **ID matching**: Tool message `tool_call_id` must match an ID from the preceding assistant's `tool_calls`
3. **Atomic units**: Tool call sequences cannot be split

### The Bug in Detail
When context exceeds token limit:
1. Compaction starts pruning from the beginning (oldest messages)
2. It uses a "keep from end" approach: `for msg in reversed(candidates):`
3. If budget runs out, it might keep:
   - Tool messages (recent)
   - But NOT their preceding assistant message (older)
4. Result: Tool messages without parent assistant → 400 error

## Evidence

### Test Results
```
=== Testing Compaction with Multiple Tool Calls ===

Original messages: 5
Compacted messages: 5
ERROR: Tool message at index 3 out of sequence
```

The test shows compaction can produce invalid sequences where tool messages don't follow assistant messages.

### Code Analysis
The compaction algorithm (lines 48-57):
```python
kept = []
used = 0
for msg in reversed(candidates):  # Start from most recent
    cost = TokenCounter.count_messages([msg])
    if used + cost <= budget:
        kept.append(msg)
        used += cost
    else:
        break
```

This treats each message independently, breaking tool call dependencies.

## Impact

1. **User Experience**: Random 400 errors during conversation
2. **Reliability**: Unpredictable failures when context grows
3. **Debugging Difficulty**: Hard to diagnose without detailed logging

## Recommendations

### Immediate Fix (Priority 1)
**Fix the compaction algorithm** to preserve atomic sequences:

1. **Implement sequence grouping**: Group assistant messages with their tool responses
2. **Atomic preservation**: Keep or discard entire tool call sequences
3. **Add validation**: Validate sequences before and after compaction

### Short-term Improvements (Priority 2)
1. **Add message sequence validation** before API calls
2. **Improve error messages** with context about invalid sequences
3. **Add debug logging** for message sequences sent to API

### Long-term Improvements (Priority 3)
1. **Comprehensive testing** for all compaction scenarios
2. **Better token estimation** for tool calls
3. **API compatibility layer** to handle provider differences

## Implementation Plan

### Phase 1: Fix Compaction (1-2 days)
1. Implement `_group_into_sequences()` method
2. Modify `compact()` to preserve atomic sequences
3. Add unit tests for tool call sequence preservation

### Phase 2: Add Validation (1 day)
1. Add `validate_message_sequence()` function
2. Integrate validation into Agent before API calls
3. Add descriptive error messages

### Phase 3: Improve Diagnostics (1 day)
1. Add detailed logging of message sequences
2. Create reproduction tests for edge cases
3. Update documentation

## Code Changes Required

### 1. Fix `compaction.py`
- Implement sequence-aware compaction
- Preserve tool call atomicity
- Add sequence validation

### 2. Update `agent.py`
- Add pre-API validation
- Improve error handling
- Add debug logging

### 3. Add Tests
- Test compaction with tool sequences
- Test edge cases (multiple tools, nested sequences)
- Test validation logic

## Risk Assessment

### Low Risk
- Fix is localized to compaction logic
- Backward compatible (preserves existing behavior when possible)
- Extensive testing possible

### Medium Risk
- Changes to core message handling
- Potential impact on all conversation flows
- Requires thorough testing

## Testing Strategy

1. **Unit Tests**: Test compaction with various tool call scenarios
2. **Integration Tests**: Test full agent flow with compaction
3. **Regression Tests**: Ensure existing functionality unchanged
4. **Edge Cases**: Empty tool results, multiple tools, mixed sequences

## Conclusion

The 400 error is a serious bug that breaks tool functionality when context compaction occurs. The fix requires modifying the compaction algorithm to understand and preserve message dependencies, particularly for tool call sequences. This is a high-priority fix that will significantly improve the reliability of the henchman agent.

**Recommended Action**: Implement the sequence-aware compaction fix immediately, as it addresses the root cause of the issue.
