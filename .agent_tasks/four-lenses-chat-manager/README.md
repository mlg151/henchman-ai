# Four Lenses Bug Report: src/henchman/chat/manager.py
## Date: 2026-03-19T01:00:27.555248+00:00
## Bug Summary
In `_process_stream` method, when a tool execution fails, the error message is sent to the user via `bot.send_message()`. If this send operation fails (e.g., network error, rate limit), the agent is never notified of the failure via `agent.submit_tool_result()`, causing the agent to hang indefinitely waiting for a tool result.

## Lens
**Phase 1: The Intent vs. Reality Check** - Logic Gaps

## Expected vs. Observed
| Expected Behavior | Observed Risk |
|---|---|
| Agent should always receive tool result (success or error) | Agent hangs if error message cannot be sent to user |
| Tool execution failures should be robust to downstream errors | Failure in error reporting breaks the agent loop |
| Error handling should be atomic: either both notify user AND agent, or neither | Partial failure leaves agent in inconsistent state |

## Root Cause
Lines 335-342 in `_process_stream`: The `try` block only covers tool execution. If `bot.send_message()` fails in the `except` block, `agent.submit_tool_result()` is never called. The agent remains blocked waiting for a tool result that will never arrive.

## Fix Plan
1. Wrap the entire error handling logic (lines 335-342) in a nested try-except.
2. Ensure `agent.submit_tool_result()` is called even if sending the error message fails.
3. Log the secondary failure separately.

## Status: FIXED

## Files Changed
1. `src/henchman/chat/manager.py`:
   - Added nested try-except in `_process_stream` method (lines 335-352)
   - Wrapped `bot.send_message()` call in error handling block
   - Ensured `agent.submit_tool_result()` is always called even if sending error message fails
   - Added warning log for secondary failure when sending error message fails

2. `tests/chat/test_chat.py`:
   - Added `test_tool_error_send_message_failure` test method
   - Test verifies that agent receives tool result even when error message sending fails
   - Test uses mock bot that fails on second `send_message()` call
   - Test confirms `agent.submit_tool_result()` is called despite the failure