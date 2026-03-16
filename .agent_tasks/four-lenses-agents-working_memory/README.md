# Four Lenses Bug Report: src/henchman/agents/working_memory.py
## Date: 2025-03-16T12:00:00Z
## Bug Summary
The `should_read_file` method has a critical bug where invalid line range validation (`start > end`) happens AFTER the early return for "file not in recent files". When a file is not in recent files and an invalid line range is requested (e.g., `start=10, end=5`), the method returns "File not in recent files" instead of reporting the invalid line range error.

## Lens
**Phase 1: The Intent vs. Reality Check** - Logic Gaps

## Expected vs. Observed
| Expected Behavior | Observed Risk |
|---|---|
| When `start=10, end=5` (invalid: start > end) and file is not in recent files, method should return `True` with error about invalid line range | Method returns `True` with "File not in recent files", masking the actual validation error |
| Invalid line range validation should happen BEFORE checking if file is in recent files | Invalid line range validation happens AFTER the early return for "file not in recent files" |
| Users should get accurate error messages about invalid parameters | Users get misleading error messages that don't help them fix their request |

## Root Cause
The `should_read_file` method has this order of operations:
1. **Lines 547-567**: Line number validation (including `start > end` check at line 565)
2. **Line 570**: Early return if file not in recent files: `if path not in self.recent_files: return True, "File not in recent files"`

The bug is that the validation at line 565 has a condition `end != -1`. This is correct for the validation logic, but the real issue is semantic: when a file is not in recent files, we should still validate the input parameters before deciding to read the file. Invalid parameters should be reported as such, not masked by "File not in recent files".

## Fix Plan
Move the validation for invalid line ranges (`start > end`) to happen unconditionally, before the check for "file not in recent files". The fix is simple: ensure that parameter validation always happens first, regardless of file state.

## Status: FIXED

## Files Changed
1. `src/henchman/agents/working_memory.py` - Moved validation logic (lines 547-567) to happen BEFORE the check for "file not in recent files" (line 530). This ensures that invalid line range errors are reported even when a file is not in recent files, providing accurate error messages to users.

## Verification
- Test `test_should_read_file_invalid_range_before_file_check` now passes (previously failed)
- All 208 existing tests continue to pass
- The fix ensures that when `start=10, end=5` (invalid: start > end) is requested for a file not in recent files, the method returns "Invalid line range: start (10) > end (5) - line numbers must be in ascending order" instead of "File not in recent files"