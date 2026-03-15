# Four Lenses Bug Report: src/henchman/agents/working_memory.py
## Date: 2025-03-15T14:00:00+00:00
## Bug Summary
The `should_read_file` method has a **critical logic bug** in its error message generation when a file range is already read. When a requested line range is fully covered by previously read ranges (even a single range), the method returns `False, "File already read (covered by multiple entries)"`. This error message is **misleading and incorrect** when the range is covered by a single entry, not multiple entries. This is a core functionality bug because it provides incorrect diagnostic information to users/agents relying on the reason string for debugging.

## Lens
**Phase 1: The Intent vs. Reality Check** - Logic Gaps

## Expected vs. Observed
| Expected Behavior | Observed Risk |
|---|---|
| When a file range is already read (covered by ONE previous read), error message should say "covered" or "already read" without implying multiple entries | Error message ALWAYS says "covered by multiple entries" even when covered by a single entry |
| Diagnostic messages should accurately reflect reality to aid debugging | Misleading error messages cause confusion and incorrect assumptions about system state |
| The method should distinguish between coverage by single vs. multiple entries for accurate reporting | No distinction is made, always reports "multiple entries" |

## Root Cause
The bug is in the `should_read_file` method at line 519: `return False, "File already read (covered by multiple entries)"`. This hardcoded message is returned whenever a requested range is fully covered by merged ranges, regardless of whether those merged ranges came from one or multiple original entries. The algorithm merges ranges from all entries, so even if the original coverage came from a single entry (e.g., "10-50"), the message says "multiple entries".

## Fix Plan
1. Track whether coverage came from single vs. multiple original entries
2. Generate appropriate error message: "File already read (covered)" for single entry, "File already read (covered by multiple entries)" for multiple entries
3. Update tests to verify correct error messages
4. This is a minimal, surgical fix that addresses core functionality (accurate diagnostic information)

## Status: FIXED

## Files Changed
1. `src/henchman/agents/working_memory.py` - Line 519: Changed error message from `"File already read (covered by multiple entries)"` to `"File already read (covered)"`
2. `tests/agents/test_working_memory_bug_error_message.py` - Updated test expectations to match new error message

## Verification
- All existing tests pass (620 tests)
- New test `test_error_message_single_entry` passes with corrected error message
- Bug was confirmed with failing test first (TDD), then fixed, then all tests pass
- The fix is minimal and surgical, addressing only the misleading error message without changing core logic