# Improvement Summary

**Date/Time**: 2025-01-15 (automated run)

**Files Changed**:
1. `src/henchman/core/agent.py` - Modified to pass actual finish reason in FINISHED events
2. `src/henchman/api/endpoints/chat.py` - Updated to use actual finish reason from events

**Changes Made**:

1. **Fixed TODO in API endpoints**: The API endpoints now correctly extract and return the actual finish reason from agent events instead of hardcoding "stop".

2. **Enhanced agent finish reason handling**:
   - Modified `_process_streaming_response()` to capture the actual finish reason (stop, tool_calls, length, content_filter) from provider chunks
   - Added handling for `FinishReason.LENGTH` and `FinishReason.CONTENT_FILTER` cases which were previously not handled
   - Updated the method signature to return finish reason along with other accumulated data
   - Modified `run()` method to use the actual finish reason instead of generic "Agent completed execution"
   - Updated `continue_with_tool_results()` to match the new return signature

3. **API endpoint improvements**:
   - Non-streaming endpoint (`/completions`): Now extracts finish reason from the first FINISHED event
   - Streaming endpoint (`/completions/stream`): Now uses actual finish reason from event data
   - Both endpoints handle multiple FINISHED events (takes the first one with actual finish reason)

**Rationale**:
- The TODO comments indicated missing implementation for finish reason extraction
- Proper finish reason reporting is important for API clients to understand why generation stopped
- Supports all standard finish reasons: stop, tool_calls, length, content_filter
- Maintains backward compatibility while fixing the TODO

**Testing**:
- Existing tests pass (except one unrelated CLI test failure)
- Manual test confirms finish reason "stop" is correctly passed through events
- Handles edge cases like multiple FINISHED events gracefully